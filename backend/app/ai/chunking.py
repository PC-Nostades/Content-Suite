"""Chunking semántico del Manual de Marca, derivado del schema.

**Por qué no chunking de tamaño fijo**, en orden de importancia:

1. **Sin metadata limpia no hay pre-filtrado.** Un chunk que mezcla el final de
   "tono de voz" con el inicio de "paleta de color" no puede etiquetarse como
   `text` ni como `visual`. Y sin ese filtro, una consulta del Módulo III sobre el
   tamaño del logo devuelve reglas de léxico. Este es el argumento decisivo.
2. **Rompe unidades atómicas.** Un corte puede dejar `#2E7D32` en un chunk y
   "nunca sobre tipografía" en el siguiente: el Módulo III auditaría mal.
3. **Destruye listas.** `forbidden_terms` con 15 entradas se parte y se recuperan
   8 de 15. Para una regla `hard` eso es un falso negativo inaceptable.
4. **El documento ya viene estructurado.** Aplicarle chunking fijo es tirar a la
   basura una estructura que el LLM ya entregó. Aquí el chunking semántico no es
   heurístico ni caro: es determinista y se deriva del schema.

Cada `content` lleva el breadcrumb embebido en el propio texto (*contextual
retrieval*): mejora el recall porque el embedding "sabe" de qué sección viene.
"""

from dataclasses import dataclass, field

from app.ai.schemas.brand_manual import BrandManual, Rule
from app.core.enums import Channel, Modality, RuleType, Severity

#: Si una sección supera este tamaño se parte por ventanas de ítems COMPLETOS,
#: nunca a mitad de un ítem. Un término prohibido cortado por la mitad es peor
#: que no tenerlo.
MAX_CHUNK_CHARS = 2800


@dataclass
class ChunkData:
    """Un chunk listo para embeber y persistir."""

    chunk_index: int
    section: str
    rule_type: RuleType
    modality: Modality
    severity: Severity
    heading: str
    content: str
    rule_ids: list[str] = field(default_factory=list)
    channel_scope: list[str] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        """Estimación por caracteres (~4 por token en español).

        Deliberadamente aproximado: contar tokens de verdad exigiría una llamada
        a la API por chunk, y el free tier permite 20 al día. El valor solo se usa
        para diagnóstico, nunca para decidir cortes.
        """
        return max(1, len(self.content) // 4)


def _breadcrumb(brand: str, section: str, rule_type: RuleType, modality: Modality, severity: Severity) -> str:
    ruta = section.replace(".", " > ")
    return (
        f"[MARCA: {brand}] [SECCIÓN: {ruta}] [TIPO: {rule_type.value}] "
        f"[MODALIDAD: {modality.value}] [SEVERIDAD: {severity.value}]"
    )


def _render_rule_items(rules: list[Rule]) -> list[str]:
    """Serializa cada regla como un ítem INDIVISIBLE.

    Devuelve una lista (y no un bloque único) para que `_split_items` pueda
    partir una sección larga sin cortar una regla por la mitad. Una regla partida
    pierde su `check_hint` o su id, y entonces el Módulo III no puede ni
    verificarla ni citarla.

    El `check_hint` va SIEMPRE en el texto recuperado: sin él el chunk describe la
    regla pero no permite auditarla.
    """
    items = []
    for r in rules:
        lineas = [
            f"- [{r.id} | {r.severity.value}] {r.statement}",
            f"  Verificación: {r.check_hint}",
        ]
        if r.good_example:
            lineas.append(f"  Correcto: {r.good_example}")
        if r.bad_example:
            lineas.append(f"  Incorrecto: {r.bad_example}")
        items.append("\n".join(lineas))
    return items


def _render_rules(rules: list[Rule]) -> str:
    """Versión en un solo bloque, para secciones donde las reglas son accesorias."""
    return "\n".join(_render_rule_items(rules))


def _dominant_severity(rules: list[Rule]) -> Severity:
    return Severity.hard if any(r.severity == Severity.hard for r in rules) else Severity.soft


def _channels_of(rules: list[Rule]) -> list[str]:
    canales: set[str] = set()
    for r in rules:
        canales.update(c.value for c in r.channel_scope)
    return sorted(canales)


def _split_items(items: list[str], header: str, max_chars: int) -> list[str]:
    """Agrupa ítems en bloques que no superen `max_chars`, sin partir ninguno.

    Repite el encabezado en cada bloque para que un chunk recuperado suelto siga
    siendo interpretable.
    """
    bloques: list[str] = []
    actual: list[str] = []
    largo = len(header)

    for item in items:
        if actual and largo + len(item) > max_chars:
            bloques.append(header + "\n".join(actual))
            actual, largo = [], len(header)
        actual.append(item)
        largo += len(item) + 1

    if actual:
        bloques.append(header + "\n".join(actual))
    return bloques


def chunk_manual(manual: BrandManual) -> list[ChunkData]:
    """Convierte un manual en ~22-28 chunks con metadata de pre-filtrado."""
    marca = manual.strategy.brand_name
    chunks: list[ChunkData] = []

    def add(
        section: str,
        rule_type: RuleType,
        modality: Modality,
        heading: str,
        cuerpo: str,
        *,
        severity: Severity = Severity.soft,
        rule_ids: list[str] | None = None,
        channels: list[str] | None = None,
    ) -> None:
        cabecera = _breadcrumb(marca, section, rule_type, modality, severity)
        for bloque in _split_items([cuerpo], f"{cabecera}\n\n{heading}\n\n", MAX_CHUNK_CHARS):
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    section=section,
                    rule_type=rule_type,
                    modality=modality,
                    severity=severity,
                    heading=heading,
                    content=bloque,
                    rule_ids=rule_ids or [],
                    channel_scope=channels or [],
                )
            )

    def add_list(
        section: str,
        rule_type: RuleType,
        modality: Modality,
        heading: str,
        items: list[str],
        *,
        severity: Severity = Severity.soft,
        rule_ids: list[str] | None = None,
        channels: list[str] | None = None,
    ) -> None:
        """Como `add`, pero parte listas largas por ítems completos."""
        cabecera = _breadcrumb(marca, section, rule_type, modality, severity)
        for bloque in _split_items(items, f"{cabecera}\n\n{heading}\n\n", MAX_CHUNK_CHARS):
            chunks.append(
                ChunkData(
                    chunk_index=len(chunks),
                    section=section,
                    rule_type=rule_type,
                    modality=modality,
                    severity=severity,
                    heading=heading,
                    content=bloque,
                    rule_ids=rule_ids or [],
                    channel_scope=channels or [],
                )
            )

    s = manual.strategy

    # ----------------------------------------------------------- Estrategia
    add(
        "estrategia.posicionamiento", RuleType.strategy, Modality.both,
        "POSICIONAMIENTO Y PROPUESTA DE VALOR",
        "\n".join([
            f"Marca: {s.brand_name}",
            f"Categoría: {s.category}",
            f"Misión: {s.mission}",
            f"Posicionamiento: {s.positioning_statement}",
            f"Propuesta de valor: {s.value_proposition}",
            "",
            "Diferenciadores:",
            *(f"- {d}" for d in s.differentiators),
        ]),
    )

    add(
        "estrategia.personalidad", RuleType.strategy, Modality.both,
        "PERSONALIDAD Y ARQUETIPO",
        "\n".join([
            f"Arquetipo de marca: {s.brand_archetype}",
            f"Rasgos de personalidad: {', '.join(s.personality_traits)}",
            "",
            "LO QUE LA MARCA NO ES:",
            *(f"- {c}" for c in s.competitor_contrast),
        ]),
    )

    # ------------------------------------------------------------ Audiencia
    for aud in manual.audiences:
        add(
            f"audiencia.{aud.label.lower().replace(' ', '_')}", RuleType.audience, Modality.both,
            f"AUDIENCIA — {aud.label}",
            "\n".join([
                f"Rango de edad: {aud.age_range}",
                f"Descripción: {aud.description}",
                "",
                "Psicografía:", *(f"- {p}" for p in aud.psychographics),
                "",
                "Qué busca resolver:", *(f"- {j}" for j in aud.jobs_to_be_done),
                "",
                "Frustraciones:", *(f"- {p}" for p in aud.pain_points),
                "",
                "Códigos culturales:", *(f"- {c}" for c in aud.cultural_codes),
                "",
                f"Canales donde está: {', '.join(c.value for c in aud.media_habits)}",
            ]),
            channels=[c.value for c in aud.media_habits],
        )

    v = manual.verbal

    # ------------------------------------------------------ Identidad verbal
    add(
        "identidad_verbal.tono", RuleType.tone, Modality.text,
        "TONO DE VOZ — ATRIBUTOS",
        "\n\n".join(
            f"{t.name} (intensidad {t.intensity}/5)\n"
            f"  {t.definition}\n"
            f"  SUENA ASÍ: {t.sounds_like}\n"
            f"  NO SUENA ASÍ: {t.does_not_sound_like}"
            for t in v.tone_attributes
        ),
    )

    vs = v.voice_spectrum
    add(
        "identidad_verbal.espectro_voz", RuleType.tone, Modality.text,
        "ESPECTRO DE VOZ",
        "\n".join([
            "Escala 0-100 entre los dos extremos de cada eje:",
            f"- Formal (0) ←→ Casual (100): {vs.formal_vs_casual}",
            f"- Serio (0) ←→ Juguetón (100): {vs.serious_vs_playful}",
            f"- Respetuoso (0) ←→ Irreverente (100): {vs.respectful_vs_irreverent}",
            f"- Factual (0) ←→ Entusiasta (100): {vs.factual_vs_enthusiastic}",
        ]),
    )

    add_list(
        "identidad_verbal.lexico_preferido", RuleType.lexicon, Modality.text,
        "LÉXICO PREFERIDO — usar estos términos",
        [f'- Usa "{p.use}" en vez de: {", ".join(p.instead_of)}. Motivo: {p.rationale}'
         for p in v.preferred_terms],
    )

    add_list(
        "identidad_verbal.lexico_prohibido", RuleType.lexicon, Modality.text,
        "LÉXICO PROHIBIDO — nunca usar estos términos",
        [f'- PROHIBIDO "{t.term}" [{t.severity.value}, match={t.match_mode}] '
         f'→ usar "{t.replacement}". Motivo: {t.reason}'
         for t in v.forbidden_terms],
        severity=_dominant_severity_terms(v.forbidden_terms),
    )

    add_list(
        "identidad_verbal.claims_prohibidos", RuleType.compliance, Modality.both,
        "CLAIMS PROHIBIDOS — riesgo regulatorio",
        [f'- PROHIBIDO "{t.term}" [{t.severity.value}, match={t.match_mode}] '
         f'→ usar "{t.replacement}". Motivo: {t.reason}'
         for t in v.forbidden_claims],
        severity=_dominant_severity_terms(v.forbidden_claims),
    )

    g = v.grammar_style
    add(
        "identidad_verbal.gramatica_estilo", RuleType.grammar, Modality.text,
        "GRAMÁTICA Y ESTILO",
        "\n".join([
            f"Variante de idioma: {g.locale}",
            f"Persona gramatical: {g.person}",
            f"Máximo de palabras por oración: {g.max_sentence_words}",
            f"Máximo de oraciones por párrafo: {g.max_paragraph_sentences}",
            f"Nivel de lectura: {g.reading_level}",
            f"Política de emojis: {g.emoji_policy}"
            + (f" (permitidos: {' '.join(g.allowed_emojis)})" if g.allowed_emojis else ""),
            f"Signos de exclamación: {g.exclamation_policy}",
            f"Anglicismos: {g.anglicism_policy}",
            f"Números y unidades: {g.numbers_and_units}",
            "",
            "Reglas de capitalización:",
            *(f"- {r}" for r in g.capitalization_rules),
        ]),
    )

    add(
        "identidad_verbal.pilares", RuleType.messaging, Modality.text,
        "PILARES DE MENSAJE",
        "\n\n".join(
            f"{p.name}\n  {p.description}\n"
            f"  Pruebas: {'; '.join(p.proof_points)}\n"
            f"  Titulares de ejemplo: {' | '.join(p.sample_headlines)}"
            for p in v.messaging_pillars
        )
        + f"\n\nTaglines: {' | '.join(v.taglines)}"
        + f"\n\nBoilerplate: {v.boilerplate}",
    )

    for cg in v.channel_guidelines:
        add(
            f"identidad_verbal.canal.{cg.channel.value}", RuleType.channel, Modality.text,
            f"GUÍA DE CANAL — {cg.channel.value}",
            "\n".join([
                f"Longitud máxima: {cg.max_chars} caracteres",
                f"Estructura: {cg.structure}",
                f"Estilo de CTA: {cg.cta_style}",
                f"Política de hashtags: {cg.hashtag_policy}",
                f"Ajuste de tono: {cg.tone_adjustment}",
            ]),
            channels=[cg.channel.value],
        )

    add_list(
        "identidad_verbal.reglas", RuleType.tone, Modality.text,
        "REGLAS VERIFICABLES DE TEXTO",
        _render_rule_items(v.verbal_rules),
        severity=_dominant_severity(v.verbal_rules),
        rule_ids=[r.id for r in v.verbal_rules],
        channels=_channels_of(v.verbal_rules),
    )

    vi = manual.visual

    # ------------------------------------------------------ Identidad visual
    add(
        "identidad_visual.paleta", RuleType.color, Modality.visual,
        "PALETA DE COLOR",
        "\n\n".join(
            f"{c.name} — {c.hex} ({c.role})\n"
            f"  Uso: {c.usage_notes}\n"
            f"  Área máxima: {c.max_area_pct}% de la pieza\n"
            f"  Combina con: {', '.join(c.pairs_well_with) or 'sin restricción'}\n"
            f"  NUNCA combinar con: {', '.join(c.never_pair_with) or 'sin restricción'}"
            for c in vi.color_palette
        )
        + (
            "\n\nCOLORES PROHIBIDOS:\n"
            + "\n".join(f"- {c.name} ({c.hex}): {c.usage_notes}" for c in vi.forbidden_colors)
            if vi.forbidden_colors else ""
        ),
        severity=Severity.hard,
    )

    add(
        "identidad_visual.tipografia", RuleType.typography, Modality.visual,
        "TIPOGRAFÍA",
        "\n\n".join(
            f"{t.family} ({t.role}) — fallback: {t.fallback}\n"
            f"  Pesos: {', '.join(t.weights)}\n"
            f"  Tamaño mínimo digital: {t.min_size_px_digital} px · impreso: {t.min_size_pt_print} pt\n"
            f"  Interlineado: {t.line_height} · Tracking: {t.letter_spacing}\n"
            f"  Reglas de caja: {t.case_rules}"
            for t in vi.typography
        )
        + (f"\n\nTIPOGRAFÍAS PROHIBIDAS: {', '.join(vi.forbidden_fonts)}" if vi.forbidden_fonts else ""),
        severity=Severity.hard,
    )

    lg = vi.logo
    add(
        "identidad_visual.logo", RuleType.logo, Modality.visual,
        "LOGOTIPO — uso y protección",
        "\n".join([
            f"Variantes aprobadas: {', '.join(lg.approved_variants)}",
            f"Zona de resguardo: {lg.clear_space_multiplier}x la altura del logo, libre de elementos.",
            f"Tamaño mínimo digital: {lg.min_size_px_digital} px · impreso: {lg.min_size_mm_print} mm",
            f"Ocupación mínima relativa: el logo debe ocupar al menos el "
            f"{lg.min_relative_width_pct}% del ancho de la pieza.",
            f"Ubicaciones permitidas: {', '.join(lg.allowed_placements)}",
            f"Fondos permitidos: {', '.join(lg.allowed_backgrounds)}",
            "",
            "PROHIBIDO:",
            *(f"- {u}" for u in lg.forbidden_usages),
        ]),
        severity=Severity.hard,
    )

    ph = vi.photography
    add(
        "identidad_visual.fotografia", RuleType.photography, Modality.visual,
        "ESTILO FOTOGRÁFICO",
        "\n".join([
            f"Atmósfera: {ph.mood}",
            f"Sujetos: {ph.subject_guidelines}",
            f"Iluminación: {ph.lighting}",
            f"Color grading: {ph.color_grading}",
            f"Profundidad de campo: {ph.depth_of_field}",
            f"Representación de personas: {ph.people_representation}",
            f"Presencia del producto: {ph.product_presence}",
            f"Área mínima del producto en el encuadre: {ph.hero_product_min_area_pct}%",
            "",
            "IMÁGENES PROHIBIDAS:",
            *(f"- {f}" for f in ph.forbidden_imagery),
            "",
            f"Semilla de prompt para generación de imagen: {ph.prompt_seed}",
        ]),
        severity=Severity.hard,
    )

    co = vi.composition
    add(
        "identidad_visual.composicion", RuleType.composition, Modality.visual,
        "COMPOSICIÓN Y RETÍCULA",
        "\n".join([
            f"Retícula: {co.grid}",
            f"Área de seguridad: {co.safe_area_pct}% del borde",
            f"Jerarquía visual: {' → '.join(co.visual_hierarchy)}",
            f"Cobertura máxima de texto: {co.max_text_coverage_pct}%",
            f"Contraste mínimo texto/fondo: {co.min_text_contrast_ratio}:1",
            f"Espacio en blanco: {co.white_space_policy}",
            "",
            "LAYOUTS PROHIBIDOS:",
            *(f"- {l}" for l in co.forbidden_layouts),
        ]),
        severity=Severity.hard,
    )

    ic = vi.iconography
    add(
        "identidad_visual.iconografia", RuleType.iconography, Modality.visual,
        "ICONOGRAFÍA",
        "\n".join([
            f"Estilo: {ic.style}",
            f"Grosor de trazo: {ic.stroke_width}",
            f"Radio de esquina: {ic.corner_radius}",
            f"Uso: {ic.usage_notes}",
            "",
            "PROHIBIDO:",
            *(f"- {f}" for f in ic.forbidden),
        ]),
    )

    pk = vi.packaging
    add(
        "identidad_visual.packaging", RuleType.packaging, Modality.visual,
        "EMPAQUE",
        "\n".join([
            "Elementos obligatorios:",
            *(f"- {e}" for e in pk.mandatory_elements),
            "",
            f"Jerarquía del panel frontal: {' → '.join(pk.front_panel_hierarchy)}",
            f"Zona legal: {pk.legal_zone_notes}",
            f"Material y acabado: {pk.material_and_finish}",
        ]),
        severity=Severity.hard,
        channels=[Channel.packaging.value],
    )

    add_list(
        "identidad_visual.reglas", RuleType.composition, Modality.visual,
        "REGLAS VERIFICABLES DE IMAGEN",
        _render_rule_items(vi.visual_rules),
        severity=_dominant_severity(vi.visual_rules),
        rule_ids=[r.id for r in vi.visual_rules],
        channels=_channels_of(vi.visual_rules),
    )

    # ---------------------------------------------------------- Cumplimiento
    cp = manual.compliance
    add(
        "cumplimiento", RuleType.compliance, Modality.both,
        f"CUMPLIMIENTO NORMATIVO — {cp.market}",
        "\n".join([
            "Notas regulatorias:",
            *(f"- {n}" for n in cp.regulatory_notes),
            "",
            "Disclaimers obligatorios:",
            *(f"- {d}" for d in cp.required_disclaimers),
            "",
            "CLAIMS RESTRINGIDOS:",
            _render_rules(cp.restricted_claims),
        ]),
        severity=_dominant_severity(cp.restricted_claims),
        rule_ids=[r.id for r in cp.restricted_claims],
    )

    # Reindexar por si algún bloque se partió: `chunk_index` debe ser denso y
    # correlativo, porque es parte de la clave única (manual_id, chunk_index).
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    return chunks


def _dominant_severity_terms(terms: list) -> Severity:
    return Severity.hard if any(t.severity == Severity.hard for t in terms) else Severity.soft
