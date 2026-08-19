"""Construye a mano un Manual de Marca completo y válido.

**Por qué existe:** desarrollar el chunking, el RAG y la UI contra un manual real
costaría una llamada al modelo por iteración, y el free tier de Gemini permite
**20 peticiones al día por modelo**. Con 4 llamadas por manual, eso son 5 manuales
diarios — insuficiente para iterar.

Este fixture desbloquea todo lo que va después del agente sin gastar una sola
llamada. Además sirve de contrato ejecutable: si alguien cambia el schema y rompe
la compatibilidad, este script deja de validar.

Se construye con los modelos Pydantic (no como JSON crudo) precisamente para que
sea imposible escribir un fixture inválido.

    python tests/fixtures/build_fixture.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.ai.postprocess import postprocess_manual  # noqa: E402
from app.ai.schemas.brand_manual import (  # noqa: E402
    Audience,
    BrandManual,
    BrandStrategy,
    ChannelGuideline,
    ColorSpec,
    Compliance,
    CompositionRules,
    ForbiddenTerm,
    GrammarStyle,
    IconographySpec,
    LogoSpec,
    MessagingPillar,
    PackagingSpec,
    PhotographyStyle,
    PreferredTerm,
    Rule,
    ToneAttribute,
    TypefaceSpec,
    VerbalIdentity,
    VisualIdentity,
    VoiceSpectrum,
)
from app.core.enums import Channel, Modality, Severity  # noqa: E402


def _rule(statement, rationale, severity, modality, good, bad, check, channels=()):
    return Rule(
        statement=statement,
        rationale=rationale,
        severity=severity,
        modality=modality,
        channel_scope=list(channels),
        good_example=good,
        bad_example=bad,
        check_hint=check,
    )


STRATEGY = BrandStrategy(
    brand_name="Kiwicha Pop",
    category="snack saludable de quinua inflada",
    mission="Hacer que el grano andino sea el snack diario de una generación que se mueve rápido.",
    positioning_statement=(
        "Para universitarios limeños de 18 a 26 que entrenan y comen fuera de casa, "
        "Kiwicha Pop es el snack andino inflado que da energía sostenida "
        "porque usa quinua de Puno sin azúcar añadida."
    ),
    value_proposition="Energía andina real, en un formato que cabe en el bolsillo del jean.",
    brand_archetype="bufon",
    personality_traits=["divertida", "auténtica", "enérgica", "orgullosamente andina"],
    differentiators=[
        "Quinua de Puno trazable por lote",
        "Sin azúcar añadida, endulzado solo con fruta",
        "Formato de 30 g pensado para mochila",
    ],
    competitor_contrast=[
        "No es una barra de cereal disfrazada de saludable",
        "No es un producto fitness que le habla a atletas de élite",
        "No es artesanía nostálgica: es andino contemporáneo",
    ],
)

AUDIENCES = [
    Audience(
        label="Gen Z urbana limeña",
        age_range="18-26",
        description=(
            "Universitarios y jóvenes profesionales de Lima que entrenan 3 veces por "
            "semana y comen al menos una vez al día fuera de casa."
        ),
        psychographics=[
            "Valora la autenticidad por encima de la perfección",
            "Desconfía del marketing que le habla como a un niño",
            "Le importa el origen de lo que consume, sin volverlo religión",
        ],
        jobs_to_be_done=[
            "Matar el hambre entre clases sin sentirse pesado",
            "Sentir que come bien sin hacer un esfuerzo consciente",
            "Mostrar buen gusto en lo que lleva en la mochila",
        ],
        pain_points=[
            "Los snacks saludables saben a cartón",
            "Los que saben bien tienen demasiada azúcar",
        ],
        cultural_codes=[
            "Jerga limeña cotidiana sin caer en la caricatura",
            "Orgullo por el ingrediente peruano, sin folclorismo",
            "Humor autoconsciente, del tipo que circula en TikTok",
        ],
        media_habits=[Channel.tiktok, Channel.instagram, Channel.packaging],
    )
]

VERBAL = VerbalIdentity(
    tone_attributes=[
        ToneAttribute(
            name="Cómplice",
            definition="Habla de igual a igual, como quien comparte un dato bueno.",
            intensity=4,
            sounds_like="Te va a durar hasta la última clase. En serio.",
            does_not_sound_like="Nuestro producto ha sido formulado para brindarle saciedad.",
        ),
        ToneAttribute(
            name="Directo",
            definition="Va al punto en la primera línea. Nada de rodeos.",
            intensity=5,
            sounds_like="Quinua de Puno. Sin azúcar añadida. Punto.",
            does_not_sound_like="En Kiwicha Pop creemos que la alimentación es un viaje...",
        ),
        ToneAttribute(
            name="Con humor",
            definition="Se ríe de sí misma antes que de nadie más.",
            intensity=3,
            sounds_like="Sí, es quinua. No, no sabe a castigo.",
            does_not_sound_like="Un snack serio para personas serias.",
        ),
    ],
    voice_spectrum=VoiceSpectrum(
        formal_vs_casual=85,
        serious_vs_playful=75,
        respectful_vs_irreverent=60,
        factual_vs_enthusiastic=55,
    ),
    preferred_terms=[
        PreferredTerm(use="energía que dura", instead_of=["energizante"], rationale="'Energizante' es claim regulado."),
        PreferredTerm(use="sin azúcar añadida", instead_of=["light", "dietético"], rationale="Es literal y verificable."),
        PreferredTerm(use="quinua de Puno", instead_of=["superalimento andino"], rationale="Específico, no grandilocuente."),
        PreferredTerm(use="te llena", instead_of=["produce saciedad"], rationale="Habla como el público."),
        PreferredTerm(use="crocante", instead_of=["textura crujiente óptima"], rationale="Una palabra basta."),
        PreferredTerm(use="para la mochila", instead_of=["formato portable"], rationale="Concreto y visual."),
        PreferredTerm(use="grano entero", instead_of=["integral"], rationale="Menos ambiguo en etiqueta."),
        PreferredTerm(use="hecho en Perú", instead_of=["producto nacional"], rationale="Directo y con orgullo."),
    ],
    forbidden_terms=[
        ForbiddenTerm(term="light", reason="Claim regulado que exige respaldo nutricional.", severity=Severity.hard, replacement="sin azúcar añadida", match_mode="exact"),
        ForbiddenTerm(term="milagroso", reason="Promesa imposible de sostener.", severity=Severity.hard, replacement="que funciona", match_mode="stem"),
        ForbiddenTerm(term="adelgaz", reason="Atribuye efecto de pérdida de peso; prohibido en alimentos.", severity=Severity.hard, replacement="te acompaña en tu rutina", match_mode="stem"),
        ForbiddenTerm(term="superalimento", reason="Término vacío y sobreexplotado por la categoría.", severity=Severity.soft, replacement="quinua de Puno", match_mode="exact"),
        ForbiddenTerm(term="biodisponibilidad", reason="Tecnicismo que rompe el tono cómplice.", severity=Severity.soft, replacement="tu cuerpo lo aprovecha", match_mode="exact"),
        ForbiddenTerm(term="delicioso", reason="Adjetivo genérico de la categoría; no dice nada.", severity=Severity.soft, replacement="crocante", match_mode="exact"),
        ForbiddenTerm(term="estimado cliente", reason="Trato distante que contradice el tono.", severity=Severity.hard, replacement="tú", match_mode="exact"),
        ForbiddenTerm(term="gratis", reason="Uso indebido en promociones con condiciones.", severity=Severity.soft, replacement="incluido", match_mode="exact"),
    ],
    forbidden_claims=[
        ForbiddenTerm(term="cura", reason="Atribuir propiedades curativas a un alimento es ilegal.", severity=Severity.hard, replacement="aporta", match_mode="stem"),
        ForbiddenTerm(term="100% natural", reason="Requiere sustento técnico verificable.", severity=Severity.hard, replacement="con ingredientes de origen vegetal", match_mode="exact"),
        ForbiddenTerm(term="el mejor del mercado", reason="Comparación no demostrable ante INDECOPI.", severity=Severity.hard, replacement="nuestro favorito", match_mode="exact"),
        ForbiddenTerm(term="previene", reason="Claim de salud no autorizado.", severity=Severity.hard, replacement="acompaña", match_mode="stem"),
    ],
    grammar_style=GrammarStyle(
        locale="es-PE",
        person="tu",
        max_sentence_words=18,
        max_paragraph_sentences=3,
        reading_level="basico",
        emoji_policy="limitado",
        allowed_emojis=["🔥", "💥", "🌾"],
        exclamation_policy="Máximo un signo de exclamación por pieza.",
        capitalization_rules=["Nunca escribir en MAYÚSCULAS sostenidas salvo el logotipo."],
        anglicism_policy="Evitar anglicismos salvo los ya integrados al habla limeña.",
        numbers_and_units="Usar cifras para gramos y porcentajes: 30 g, 12 %.",
    ),
    messaging_pillars=[
        MessagingPillar(
            name="Energía que dura",
            description="El grano andino libera energía de forma sostenida.",
            proof_points=["Quinua de grano entero", "Sin azúcar añadida"],
            sample_headlines=["Te dura hasta la última clase", "Energía que no se cae a media tarde"],
        ),
        MessagingPillar(
            name="Origen con nombre",
            description="Cada lote es trazable hasta su comunidad productora en Puno.",
            proof_points=["Trazabilidad por lote", "Compra directa a productores"],
            sample_headlines=["Sabemos de qué chacra salió", "Quinua con apellido"],
        ),
        MessagingPillar(
            name="Andino contemporáneo",
            description="Lo peruano no tiene que verse antiguo para ser auténtico.",
            proof_points=["Diseño gráfico contemporáneo", "Formato urbano de 30 g"],
            sample_headlines=["Andino, no arcaico", "De Puno a tu mochila"],
        ),
    ],
    taglines=["Energía andina, ritmo urbano", "De Puno a tu mochila", "Quinua con apellido"],
    boilerplate=(
        "Kiwicha Pop es un snack de quinua inflada hecho con grano entero de Puno, "
        "sin azúcar añadida, en formato de 30 g."
    ),
    channel_guidelines=[
        ChannelGuideline(channel=Channel.tiktok, max_chars=150, structure="hook (1 línea) → beneficio → CTA", cta_style="Invitación directa en segunda persona.", hashtag_policy="Máximo 3, siempre en minúsculas.", tone_adjustment="Sube el humor un punto."),
        ChannelGuideline(channel=Channel.instagram, max_chars=280, structure="gancho → contexto → CTA", cta_style="Pregunta abierta al final.", hashtag_policy="Máximo 5, agrupados al final.", tone_adjustment="Mantiene el tono base."),
        ChannelGuideline(channel=Channel.packaging, max_chars=90, structure="beneficio → origen → gramaje", cta_style="Sin CTA: el empaque informa.", hashtag_policy="Sin hashtags.", tone_adjustment="Baja el humor: prima la claridad legal."),
    ],
    verbal_rules=[
        _rule("Escribe siempre en segunda persona del singular (tú).", "El tono cómplice exige tratar de tú.", Severity.hard, Modality.text, "Te va a durar toda la mañana.", "Le durará toda la mañana.", "Buscar 'usted', 'le', 'su' como tratamiento formal."),
        _rule("Limita cada oración a 18 palabras.", "El público lee en móvil y en movimiento.", Severity.soft, Modality.text, "Quinua de Puno. Sin azúcar añadida.", "Un snack elaborado con quinua seleccionada de la región de Puno que ha sido cuidadosamente inflada.", "Contar palabras por oración; ninguna debe superar 18."),
        _rule("No uses tecnicismos nutricionales sin traducirlos.", "Rompen el tono y excluyen al lector.", Severity.hard, Modality.text, "Tu cuerpo lo aprovecha mejor.", "Alta biodisponibilidad proteica.", "Buscar términos técnicos sin una explicación coloquial adyacente."),
        _rule("Menciona el origen (Puno) al menos una vez por pieza larga.", "Es el diferenciador principal.", Severity.soft, Modality.text, "Quinua de Puno, inflada como cancha.", "Quinua de los Andes.", "Verificar presencia de 'Puno' en textos de más de 200 caracteres."),
        _rule("Nunca prometas resultados de salud o pérdida de peso.", "Riesgo regulatorio directo.", Severity.hard, Modality.both, "Energía para tu rutina.", "Te ayuda a bajar de peso.", "Buscar verbos de efecto fisiológico: adelgaza, cura, previene, quema."),
        _rule("Usa como máximo un signo de exclamación por pieza.", "Más de uno suena a publicidad gritada.", Severity.soft, Modality.text, "Te va a encantar. En serio.", "¡Increíble! ¡Delicioso! ¡Único!", "Contar caracteres '!' en la pieza; deben ser 0 o 1."),
        _rule("No escribas en mayúsculas sostenidas fuera del logotipo.", "Grita y perjudica la legibilidad.", Severity.hard, Modality.both, "Energía andina", "ENERGÍA ANDINA", "Detectar palabras de 4+ caracteres en mayúsculas fuera del logo."),
        _rule("Cierra los textos de redes con una invitación, no con una orden.", "El arquetipo bufón invita, no manda.", Severity.soft, Modality.text, "¿Lo pruebas?", "¡Compra ahora!", "Revisar la última oración: no debe ser imperativo de compra."),
    ],
)

VISUAL = VisualIdentity(
    color_palette=[
        ColorSpec(name="Naranja Cancha", hex="#E8552D", role="primary", usage_notes="Color de marca. Fondos plenos y titulares.", max_area_pct=45, pairs_well_with=["#1C1B19"], never_pair_with=["#C2185B"]),
        ColorSpec(name="Negro Chacra", hex="#1C1B19", role="neutral", usage_notes="Tipografía principal y fondos oscuros.", max_area_pct=60, pairs_well_with=["#F5EFE3", "#E8552D"], never_pair_with=[]),
        ColorSpec(name="Crema Grano", hex="#F5EFE3", role="background", usage_notes="Fondo por defecto de piezas informativas.", max_area_pct=100, pairs_well_with=["#1C1B19"], never_pair_with=[]),
        ColorSpec(name="Verde Puno", hex="#2E7D32", role="secondary", usage_notes="Solo para sellos de origen y trazabilidad.", max_area_pct=20, pairs_well_with=["#F5EFE3"], never_pair_with=["#E8552D"]),
        ColorSpec(name="Amarillo Sol", hex="#F2B705", role="accent", usage_notes="Destacados puntuales. Nunca como fondo completo.", max_area_pct=15, pairs_well_with=["#1C1B19"], never_pair_with=["#F5EFE3"]),
    ],
    forbidden_colors=[
        ColorSpec(name="Rosa Pastel", hex="#F8BBD0", role="accent", usage_notes="Contradice el carácter enérgico de la marca.", max_area_pct=0, pairs_well_with=[], never_pair_with=[]),
    ],
    typography=[
        TypefaceSpec(family="Archivo Black", fallback="system-ui, sans-serif", role="headline", weights=["900"], min_size_px_digital=28, min_size_pt_print=18, line_height="1.05", letter_spacing="-0.02em", case_rules="Título en mayúscula inicial. Nunca todo en mayúsculas."),
        TypefaceSpec(family="Inter", fallback="system-ui, sans-serif", role="body", weights=["400", "600"], min_size_px_digital=14, min_size_pt_print=9, line_height="1.5", letter_spacing="0", case_rules="Mayúscula inicial de oración."),
        TypefaceSpec(family="Inter", fallback="system-ui, sans-serif", role="legal", weights=["400"], min_size_px_digital=10, min_size_pt_print=6, line_height="1.3", letter_spacing="0.01em", case_rules="Mayúscula inicial de oración."),
    ],
    forbidden_fonts=["Comic Sans MS", "Papyrus", "Curlz MT"],
    logo=LogoSpec(
        approved_variants=["full-color sobre crema", "monocromo negro", "invertido blanco"],
        clear_space_multiplier=0.5,
        min_size_px_digital=48,
        min_size_mm_print=15,
        min_relative_width_pct=8.0,
        allowed_placements=["superior_izquierda", "inferior_derecha"],
        allowed_backgrounds=["Colores planos de la paleta", "Fotografía con área lisa y contraste >= 3:1"],
        forbidden_usages=[
            "Rotar el logo en cualquier ángulo",
            "Estirar o comprimir sin mantener proporción",
            "Aplicar sombras, degradados o contornos",
            "Colocarlo sobre fondos con ruido visual",
            "Recolorearlo fuera de las variantes aprobadas",
        ],
    ),
    photography=PhotographyStyle(
        mood="Cotidiano y luminoso, con energía de calle limeña.",
        subject_guidelines="Personas reales en contexto urbano, nunca posando de frente a cámara.",
        lighting="Luz natural lateral. Sin flash directo.",
        color_grading="Cálido, con negros abiertos. Sin filtros saturados.",
        depth_of_field="Media: el producto nítido, el fondo apenas desenfocado.",
        people_representation="Diversidad real de fenotipos peruanos, 18-30 años, expresión espontánea.",
        product_presence="El empaque siempre visible y legible, nunca como objeto secundario.",
        hero_product_min_area_pct=25,
        forbidden_imagery=[
            "Stock corporativo genérico de gente riendo con ensaladas",
            "Fondos blancos puros de estudio",
            "Sobre-retoque de piel",
            "Iconografía incaica literal o estereotipada",
        ],
        prompt_seed=(
            "fotografía cotidiana en calle limeña, luz natural lateral cálida, "
            "persona joven peruana en movimiento, empaque de snack visible y nítido "
            "ocupando al menos un cuarto del encuadre, fondo urbano apenas desenfocado, "
            "sin retoque de piel, grano fotográfico sutil"
        ),
    ),
    composition=CompositionRules(
        grid="Retícula de 12 columnas con canal de 16 px.",
        safe_area_pct=6,
        visual_hierarchy=["Producto", "Titular", "Beneficio", "Logo", "Legal"],
        max_text_coverage_pct=35,
        min_text_contrast_ratio=4.5,
        white_space_policy="Mínimo 20 % del área sin elementos.",
        forbidden_layouts=[
            "Texto centrado sobre fotografía con detalle",
            "Más de tres niveles tipográficos en una misma pieza",
        ],
    ),
    iconography=IconographySpec(
        style="line",
        stroke_width="2 px a 24 px de caja",
        corner_radius="2 px",
        usage_notes="Solo para atributos funcionales del producto.",
        forbidden=["Iconos rellenos", "Emojis como sustituto de iconos"],
    ),
    packaging=PackagingSpec(
        mandatory_elements=[
            "Octógonos de advertencia negros de la Ley 30021 en la cara frontal, cuando apliquen",
            "Gramaje visible en la esquina inferior derecha",
            "Sello de origen Puno",
        ],
        front_panel_hierarchy=["Logotipo", "Nombre de variedad", "Gramaje", "Octógonos"],
        legal_zone_notes="La zona legal inferior no puede ser invadida por elementos gráficos.",
        material_and_finish="Film mate con ventana transparente lateral.",
    ),
    visual_rules=[
        _rule("El logo debe ocupar al menos el 8 % del ancho de la pieza.", "Por debajo deja de ser reconocible en feed móvil.", Severity.hard, Modality.visual, "Logo de 96 px en pieza de 1080 px.", "Logo de 40 px en pieza de 1080 px.", "Medir ancho del bounding box del logo dividido por el ancho total; debe ser >= 0.08."),
        _rule("Ningún elemento puede invadir la zona de resguardo del logo.", "El logo pierde jerarquía si algo lo toca.", Severity.hard, Modality.visual, "Área perimetral vacía equivalente a media altura del logo.", "Un titular pegado al borde del logo.", "Inspeccionar el área perimetral del logo a 0.5x su altura; debe estar vacía."),
        _rule("El contraste entre texto y fondo debe ser al menos 4.5:1.", "Legibilidad WCAG AA.", Severity.hard, Modality.visual, "Texto #1C1B19 sobre #F5EFE3.", "Texto #F2B705 sobre #F5EFE3.", "Calcular el ratio de contraste WCAG entre texto y fondo; debe ser >= 4.5."),
        _rule("El producto debe ocupar al menos el 25 % del encuadre.", "Es el héroe de la pieza.", Severity.hard, Modality.visual, "Empaque ocupando un tercio del encuadre.", "Empaque diminuto al fondo de una escena.", "Estimar el área del empaque respecto al total; debe ser >= 0.25."),
        _rule("No usar más de tres niveles tipográficos por pieza.", "Más jerarquías rompen la lectura.", Severity.soft, Modality.visual, "Titular, bajada y legal.", "Cinco tamaños distintos en una misma pieza.", "Contar tamaños tipográficos distintos; deben ser <= 3."),
        _rule("El naranja primario no puede cubrir más del 45 % del área.", "Satura y pierde impacto.", Severity.soft, Modality.visual, "Franja naranja en un tercio de la pieza.", "Fondo naranja completo con texto encima.", "Estimar el porcentaje de área en #E8552D; debe ser <= 45."),
        _rule("No colocar el logo sobre fotografía con textura o ruido.", "Se vuelve ilegible.", Severity.hard, Modality.visual, "Logo sobre una franja de color plano.", "Logo sobre una foto de grano de quinua a detalle.", "Verificar que el área bajo el logo sea de color plano o contraste >= 3:1."),
        _rule("El margen de seguridad debe ser al menos el 6 % del borde.", "Evita cortes en impresión y recortes de feed.", Severity.hard, Modality.visual, "Elementos a 64 px del borde en pieza de 1080 px.", "Texto pegado al borde de la pieza.", "Medir la distancia del elemento más cercano al borde; debe ser >= 6 % del lado."),
        _rule("Los octógonos de advertencia no pueden taparse ni reducirse.", "Es obligación legal (Ley 30021).", Severity.hard, Modality.visual, "Octógonos completos y visibles en la cara frontal.", "Octógonos parcialmente cubiertos por un sello promocional.", "Verificar que los octógonos negros estén completos y sin superposiciones."),
        _rule("No usar iconografía incaica literal ni estereotipada.", "La marca es andina contemporánea, no folclórica.", Severity.soft, Modality.visual, "Patrón geométrico abstracto de dos colores.", "Chullo, flauta de pan o líneas de Nazca como decoración.", "Buscar en la imagen motivos folclóricos literales; no debe haber ninguno."),
        _rule("El texto no puede cubrir más del 35 % del área de la pieza.", "El aire es parte de la identidad.", Severity.soft, Modality.visual, "Bloque de texto en un tercio inferior.", "Pieza cubierta de texto de borde a borde.", "Estimar el área ocupada por texto; debe ser <= 35 %."),
    ],
)

COMPLIANCE = Compliance(
    market="Perú",
    regulatory_notes=[
        "Ley 30021 de Promoción de la Alimentación Saludable: exige octógonos de advertencia cuando se superan los límites de azúcar, sodio o grasas saturadas.",
        "Las comunicaciones dirigidas a menores tienen restricciones adicionales bajo el mismo marco.",
        "INDECOPI sanciona la publicidad engañosa y las comparaciones no sustentadas.",
    ],
    required_disclaimers=[
        "Este producto no reemplaza una alimentación variada y equilibrada.",
    ],
    restricted_claims=[
        _rule("No atribuir propiedades curativas, preventivas o terapéuticas.", "Prohibido para alimentos por la normativa sanitaria.", Severity.hard, Modality.both, "Aporta energía para tu día.", "Previene la anemia.", "Buscar los verbos cura, sana, previene, trata o combate aplicados a enfermedades."),
        _rule("No comparar el producto con competidores sin sustento verificable.", "INDECOPI exige respaldo para toda comparación.", Severity.hard, Modality.text, "Nuestra receta usa grano entero.", "Es el snack más nutritivo del mercado.", "Buscar superlativos comparativos: el mejor, el más, superior a."),
        _rule("Todo claim nutricional debe corresponder a la tabla nutricional declarada.", "Un claim sin respaldo en tabla es publicidad engañosa.", Severity.hard, Modality.both, "Sin azúcar añadida, según tabla nutricional.", "Bajo en calorías, sin dato que lo respalde.", "Contrastar cada claim nutricional contra la tabla nutricional del empaque."),
        _rule("Los octógonos deben aparecer en la cara frontal cuando correspondan.", "Obligación de etiquetado frontal.", Severity.hard, Modality.visual, "Octógonos en la esquina superior derecha del panel frontal.", "Octógonos relegados a la cara posterior.", "Verificar la presencia de octógonos negros en el panel frontal del empaque."),
    ],
)


def build() -> BrandManual:
    manual = BrandManual(
        executive_summary=(
            "Kiwicha Pop es un snack de quinua inflada de Puno, sin azúcar añadida, "
            "que le habla de tú a la Gen Z limeña con humor y sin tecnicismos."
        ),
        strategy=STRATEGY,
        audiences=AUDIENCES,
        verbal=VERBAL,
        visual=VISUAL,
        compliance=COMPLIANCE,
    )
    postprocess_manual(manual)  # asigna rule_ids estables y normaliza los hex
    return manual


if __name__ == "__main__":
    manual = build()
    destino = Path(__file__).parent / "manual_quinua.json"
    destino.write_text(
        json.dumps(manual.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Fixture escrito en {destino}")
    print(f"  reglas verbales   : {len(manual.verbal.verbal_rules)}")
    print(f"  reglas visuales   : {len(manual.visual.visual_rules)}")
    print(f"  reglas compliance : {len(manual.compliance.restricted_claims)}")
    print(f"  colores           : {len(manual.visual.color_palette)}")
    print(f"  ejemplo de rule_id: {manual.visual.visual_rules[0].id}")
