"""⭐ EL CONTRATO CENTRAL DEL PROYECTO.

Todo lo demás se deriva de aquí: el chunking, los filtros del RAG, lo que el
Módulo II puede citar y lo que el Módulo III puede auditar.

Dos principios de diseño, y ambos importan:

1. **Cada regla hoja es un objeto `Rule`, no un string.** Un manual en prosa es
   legible para humanos e inútil para una máquina. Modelar `severity` y `modality`
   permite filtrar por dominio; modelar `id` permite que un hallazgo del Módulo III
   *cite* la regla que evaluó, en vez de opinar.

2. **`check_hint` obliga a que la regla sea verificable.** Es el campo que
   convierte el manual en algo auditable:

       ❌ "el logo debe verse bien"
       ✅ "el logo debe ocupar >= 8% del ancho de la pieza"
          check_hint: "medir ancho del bounding box del logo / ancho total >= 0.08"

Notas de compatibilidad con el structured output de Gemini (verificadas):
  - Soporta `type`, `properties`, `required`, `enum`, `items`, `minItems`/`maxItems`,
    `anyOf`, `$ref`, `description`.
  - **No soporta `pattern` de forma fiable** → los hex se validan en Pydantic
    DESPUÉS de recibir la respuesta (ver `validators.py`), no se delegan al modelo.
  - **Evitar `Optional` / `| None`**: se traducen a `anyOf[..., null]` y degradan
    la adherencia al schema. Se usan listas vacías o `"N/A"` como sentinela.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.enums import Channel, Modality, RuleType, Severity

# =============================================================================
# Unidad atómica
# =============================================================================


class Rule(BaseModel):
    """Una regla verificable del manual.

    `id` lo asigna el post-proceso determinista, no el LLM: los ids inventados por
    el modelo no son estables entre versiones, y el Módulo III necesita citarlos.
    """

    id: str = Field(
        default="",
        description=(
            "Dejar VACÍO. Lo asigna el sistema tras la generación "
            "(formato: seccion.tipo.slug)."
        ),
    )
    statement: str = Field(
        description="La regla en imperativo, autocontenida y verificable. Una sola idea."
    )
    rationale: str = Field(
        description="Por qué existe esta regla: qué la justifica en la marca, el público o la norma."
    )
    severity: Severity = Field(
        description=(
            "'hard' si violarla invalida la pieza (se bloquea o se rechaza). "
            "'soft' si es una recomendación que solo genera advertencia."
        )
    )
    modality: Modality = Field(
        description=(
            "'text' si se verifica leyendo un texto, 'visual' si se verifica mirando "
            "una imagen, 'both' si aplica a ambos."
        )
    )
    channel_scope: list[Channel] = Field(
        default_factory=list,
        description="Canales donde aplica. Lista vacía = aplica a todos los canales.",
    )
    good_example: str = Field(description="Un ejemplo concreto que CUMPLE la regla.")
    bad_example: str = Field(description="Un ejemplo concreto que la VIOLA.")
    check_hint: str = Field(
        description=(
            "Instrucción operativa para verificar la regla automáticamente. "
            "Si modality='visual', DEBE ser una medición observable en la imagen "
            "(ej.: 'ancho del logo / ancho de la pieza >= 0.08'). "
            "Si es de texto, describe el patrón concreto a buscar."
        )
    )


# =============================================================================
# 1 · Estrategia y audiencia  (Etapa A del agente)
# =============================================================================

BrandArchetype = Literal[
    "inocente", "explorador", "sabio", "heroe", "forajido", "mago",
    "hombre_comun", "amante", "bufon", "cuidador", "creador", "gobernante",
]


class BrandStrategy(BaseModel):
    brand_name: str
    category: str = Field(description="Categoría de producto en una frase corta.")
    mission: str
    positioning_statement: str = Field(
        description="Formato: 'Para <público>, <marca> es <categoría> que <beneficio> porque <razón>.'"
    )
    value_proposition: str
    brand_archetype: BrandArchetype
    personality_traits: list[str] = Field(
        min_length=2, max_length=4, description="2 a 4 adjetivos que definen la personalidad."
    )
    differentiators: list[str] = Field(
        min_length=2, max_length=3, description="Qué hace distinta a esta marca."
    )
    competitor_contrast: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Qué NO es esta marca, en contraste con lo genérico de la categoría.",
    )


class Audience(BaseModel):
    label: str = Field(description="Nombre corto del segmento. Ej: 'Gen Z urbana limeña'.")
    age_range: str
    description: str
    psychographics: list[str] = Field(min_length=2, max_length=3)
    jobs_to_be_done: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Qué 'contrata' esta persona al comprar el producto.",
    )
    pain_points: list[str] = Field(min_length=2, max_length=2)
    cultural_codes: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Referencias, jerga y códigos culturales locales que resuenan con este público.",
    )
    media_habits: list[Channel] = Field(min_length=1, max_length=2)


class StrategyStage(BaseModel):
    """Salida de la Etapa A. Es el fundamento que alimenta a las etapas B, C y D."""

    strategy: BrandStrategy
    audiences: list[Audience] = Field(min_length=1, max_length=1)


# =============================================================================
# 2 · Identidad verbal  (Etapa B) — COMBUSTIBLE DEL MÓDULO II
# =============================================================================


class ToneAttribute(BaseModel):
    name: str
    definition: str
    intensity: int = Field(ge=1, le=5, description="Qué tan marcado es este atributo, de 1 a 5.")
    sounds_like: str = Field(description="Ejemplo de frase que SÍ suena a la marca.")
    does_not_sound_like: str = Field(description="Ejemplo de frase que NO suena a la marca.")


class VoiceSpectrum(BaseModel):
    """Ejes de voz. 0 = extremo izquierdo del nombre, 100 = extremo derecho."""

    formal_vs_casual: int = Field(ge=0, le=100)
    serious_vs_playful: int = Field(ge=0, le=100)
    respectful_vs_irreverent: int = Field(ge=0, le=100)
    factual_vs_enthusiastic: int = Field(ge=0, le=100)


class PreferredTerm(BaseModel):
    use: str = Field(description="El término que SÍ se debe usar.")
    instead_of: list[str] = Field(
        min_length=1, max_length=2, description="Los términos que reemplaza."
    )
    rationale: str


class ForbiddenTerm(BaseModel):
    term: str = Field(description="El término prohibido.")
    reason: str
    severity: Severity
    replacement: str = Field(description="Con qué reemplazarlo. Nunca dejar vacío.")
    match_mode: Literal["exact", "stem", "regex"] = Field(
        description=(
            "Cómo detectarlo programáticamente: 'exact' palabra exacta, "
            "'stem' la raíz y sus derivados, 'regex' un patrón."
        )
    )


class GrammarStyle(BaseModel):
    locale: str = Field(description="Ej: es-PE")
    person: Literal["tu", "usted", "ustedes", "nosotros", "impersonal"]
    max_sentence_words: int = Field(ge=5, le=60)
    max_paragraph_sentences: int = Field(ge=1, le=10)
    reading_level: Literal["basico", "intermedio", "avanzado"]
    emoji_policy: Literal["prohibido", "limitado", "libre"]
    allowed_emojis: list[str] = Field(
        default_factory=list, description="Vacío si la política es 'prohibido'."
    )
    exclamation_policy: str
    capitalization_rules: list[str] = Field(min_length=1, max_length=2)
    anglicism_policy: str
    numbers_and_units: str


class MessagingPillar(BaseModel):
    name: str
    description: str
    proof_points: list[str] = Field(
        min_length=2, max_length=2, description="Hechos que sostienen el pilar."
    )
    sample_headlines: list[str] = Field(min_length=2, max_length=2)


class ChannelGuideline(BaseModel):
    channel: Channel
    max_chars: int = Field(ge=20)
    structure: str = Field(description="Ej: 'hook (1 línea) → beneficio → CTA'.")
    cta_style: str
    hashtag_policy: str
    tone_adjustment: str = Field(description="Cómo se ajusta el tono base en este canal.")


class VerbalIdentity(BaseModel):
    tone_attributes: list[ToneAttribute] = Field(min_length=2, max_length=3)
    voice_spectrum: VoiceSpectrum
    preferred_terms: list[PreferredTerm] = Field(min_length=2, max_length=8)
    forbidden_terms: list[ForbiddenTerm] = Field(
        min_length=2,
        max_length=8,
        description=(
            "Términos vetados por marca o por tono. El Módulo II ejecutará esta "
            "lista como un filtro determinista, no como una sugerencia."
        ),
    )
    forbidden_claims: list[ForbiddenTerm] = Field(
        min_length=2,
        max_length=4,
        description=(
            "Afirmaciones prohibidas por regulación o por falta de sustento: "
            "'cura', 'adelgaza', 'milagroso', '100% natural' sin respaldo, etc."
        ),
    )
    grammar_style: GrammarStyle
    messaging_pillars: list[MessagingPillar] = Field(min_length=2, max_length=3)
    taglines: list[str] = Field(min_length=2, max_length=3)
    boilerplate: str = Field(description="Párrafo estándar de cierre sobre la marca.")
    channel_guidelines: list[ChannelGuideline] = Field(min_length=2, max_length=3)
    verbal_rules: list[Rule] = Field(
        min_length=2,
        max_length=8,
        description="Do's y don'ts de texto, cada uno como una Rule verificable.",
    )


# =============================================================================
# 3 · Identidad visual  (Etapa C) — COMBUSTIBLE DEL MÓDULO III
# =============================================================================


class ColorSpec(BaseModel):
    name: str = Field(description="Nombre descriptivo. Ej: 'Verde Quinua'.")
    hex: str = Field(description="Color en formato #RRGGBB, con almohadilla y 6 dígitos.")
    role: Literal["primary", "secondary", "accent", "neutral", "background", "alert"]
    usage_notes: str
    max_area_pct: int = Field(
        ge=0, le=100, description="Porcentaje máximo del área de la pieza que puede cubrir."
    )
    pairs_well_with: list[str] = Field(default_factory=list, description="Hex que combinan bien.")
    never_pair_with: list[str] = Field(
        default_factory=list, description="Hex con los que NUNCA debe combinarse."
    )


class TypefaceSpec(BaseModel):
    family: str = Field(
        description="Familia tipográfica REAL y disponible (Google Fonts o estándar del sistema). Nunca inventar nombres."
    )
    fallback: str = Field(description="Ej: 'system-ui, sans-serif'.")
    role: Literal["headline", "subhead", "body", "accent", "legal"]
    weights: list[str] = Field(min_length=1, max_length=2, description="Ej: ['400', '700'].")
    min_size_px_digital: int = Field(ge=6)
    min_size_pt_print: int = Field(ge=4)
    line_height: str
    letter_spacing: str
    case_rules: str


class LogoSpec(BaseModel):
    approved_variants: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Ej: 'full-color', 'monocromo negro', 'invertido blanco'.",
    )
    clear_space_multiplier: float = Field(
        ge=0,
        description="Zona de resguardo como múltiplo de la altura del logo. Ej: 0.5",
    )
    min_size_px_digital: int = Field(ge=8)
    min_size_mm_print: int = Field(ge=1)
    min_relative_width_pct: float = Field(
        ge=0,
        le=100,
        description=(
            "⭐ Porcentaje MÍNIMO del ancho de la pieza que debe ocupar el logo. "
            "Es la regla que un modelo de visión puede medir directamente."
        ),
    )
    allowed_placements: list[
        Literal[
            "superior_izquierda", "superior_derecha", "inferior_izquierda",
            "inferior_derecha", "centro",
        ]
    ] = Field(min_length=1, max_length=2)
    allowed_backgrounds: list[str] = Field(min_length=1, max_length=2)
    forbidden_usages: list[str] = Field(
        min_length=2,
        max_length=5,
        description="Ej: no rotar, no estirar, no aplicar sombras, no sobre fondos con ruido, no recolorear.",
    )


class PhotographyStyle(BaseModel):
    mood: str
    subject_guidelines: str
    lighting: str
    color_grading: str
    depth_of_field: str
    people_representation: str = Field(description="Diversidad, edades, expresión, autenticidad.")
    product_presence: str
    hero_product_min_area_pct: int = Field(
        ge=0, le=100, description="Área mínima del encuadre que debe ocupar el producto."
    )
    forbidden_imagery: list[str] = Field(
        min_length=2,
        max_length=4,
        description="Ej: stock corporativo genérico, fondos blancos puros, sobre-retoque de piel.",
    )
    prompt_seed: str = Field(
        description=(
            "Semilla de prompt lista para un generador de imágenes, que resume este "
            "estilo fotográfico. La consumirá el Creative Engine (Módulo II)."
        )
    )


class CompositionRules(BaseModel):
    grid: str
    safe_area_pct: int = Field(ge=0, le=50, description="Margen mínimo libre, en % del borde.")
    visual_hierarchy: list[str] = Field(
        min_length=2, max_length=2, description="Orden de lectura esperado."
    )
    max_text_coverage_pct: int = Field(ge=0, le=100)
    min_text_contrast_ratio: float = Field(ge=1, description="Ratio WCAG. Ej: 4.5")
    white_space_policy: str
    forbidden_layouts: list[str] = Field(min_length=2, max_length=2)


class IconographySpec(BaseModel):
    style: Literal["line", "filled", "duotone", "hand_drawn"]
    stroke_width: str
    corner_radius: str
    usage_notes: str
    forbidden: list[str] = Field(min_length=2, max_length=2)


class PackagingSpec(BaseModel):
    mandatory_elements: list[str] = Field(
        min_length=2,
        max_length=2,
        description=(
            "Elementos obligatorios del empaque. En Perú (Ley 30021) incluye los "
            "octógonos de advertencia 'ALTO EN ...' en la cara frontal."
        ),
    )
    front_panel_hierarchy: list[str] = Field(min_length=2, max_length=3)
    legal_zone_notes: str
    material_and_finish: str


class VisualIdentity(BaseModel):
    color_palette: list[ColorSpec] = Field(min_length=2, max_length=4)
    forbidden_colors: list[ColorSpec] = Field(default_factory=list)
    typography: list[TypefaceSpec] = Field(min_length=2, max_length=2)
    forbidden_fonts: list[str] = Field(default_factory=list)
    logo: LogoSpec
    photography: PhotographyStyle
    composition: CompositionRules
    iconography: IconographySpec
    packaging: PackagingSpec
    visual_rules: list[Rule] = Field(
        min_length=2,
        max_length=10,
        description="Todas con modality='visual' y un check_hint CUANTITATIVO.",
    )


# =============================================================================
# 4 · Cumplimiento  (Etapa D)
# =============================================================================


class Compliance(BaseModel):
    market: str = Field(description="Mercado de aplicación. Ej: 'Perú'.")
    regulatory_notes: list[str] = Field(min_length=2, max_length=2)
    required_disclaimers: list[str] = Field(min_length=1, max_length=2)
    restricted_claims: list[Rule] = Field(min_length=2, max_length=3)


# =============================================================================
# Raíz
# =============================================================================


class BrandManual(BaseModel):
    """El Manual de Marca completo. Se ensambla a partir de las 4 etapas."""

    schema_version: Literal["1.0"] = "1.0"
    executive_summary: str = Field(default="", description="2-3 líneas que resumen la marca.")
    strategy: BrandStrategy
    audiences: list[Audience] = Field(min_length=1, max_length=1)
    verbal: VerbalIdentity
    visual: VisualIdentity
    compliance: Compliance

    @field_validator("visual")
    @classmethod
    def _reglas_visuales_no_pueden_ser_de_texto(cls, v: VisualIdentity) -> VisualIdentity:
        """Invariante del RAG: si una regla visual quedara marcada como 'text', el
        Módulo III jamás la recuperaría — su filtro es modality IN ('visual','both')."""
        malas = [r.statement[:60] for r in v.visual_rules if r.modality == Modality.text]
        if malas:
            raise ValueError(f"Reglas visuales marcadas como modality='text': {malas}")
        return v


#: Tipos que el agente genera por etapa. El multi-etapa existe porque pedir los
#: ~200 campos de una sola vez hace que el modelo trunque listas e ignore minItems.
STAGE_SCHEMAS: dict[str, type[BaseModel]] = {
    "strategy": StrategyStage,
    "verbal": VerbalIdentity,
    "visual": VisualIdentity,
    "compliance": Compliance,
}

__all__ = [
    "Audience",
    "BrandManual",
    "BrandStrategy",
    "ChannelGuideline",
    "ColorSpec",
    "Compliance",
    "CompositionRules",
    "ForbiddenTerm",
    "GrammarStyle",
    "IconographySpec",
    "LogoSpec",
    "MessagingPillar",
    "PackagingSpec",
    "PhotographyStyle",
    "PreferredTerm",
    "Rule",
    "RuleType",
    "STAGE_SCHEMAS",
    "StrategyStage",
    "ToneAttribute",
    "TypefaceSpec",
    "VerbalIdentity",
    "VisualIdentity",
    "VoiceSpectrum",
]
