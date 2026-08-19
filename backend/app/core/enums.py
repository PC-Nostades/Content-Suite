"""Enums canónicos del dominio.

Viven aquí (y no dentro de los modelos ni de los schemas de IA) porque los comparten
tres capas: el schema del Manual de Marca, las tablas de Postgres y los filtros del
RAG. Una sola definición evita que se desincronicen — que es exactamente el bug que
haría que el Módulo III recuperase reglas de léxico al auditar una imagen.

Los valores string DEBEN coincidir con los de los tipos ENUM de Postgres
(ver `db/migrations/0001_extensions_and_enums.sql`).
"""

from enum import Enum


class UserRole(str, Enum):
    creator = "creator"
    approver_a = "approver_a"
    approver_b = "approver_b"
    admin = "admin"


class ManualStatus(str, Enum):
    generating = "generating"
    ready = "ready"
    failed = "failed"
    published = "published"
    archived = "archived"


class GenerationStage(str, Enum):
    """Etapas reales del agente multi-etapa. Alimentan el stepper del frontend:
    una barra que avanza por etapas nombradas se percibe como un sistema serio;
    un spinner durante 45 s se percibe como un cuelgue."""

    queued = "queued"
    drafting_strategy = "drafting_strategy"
    drafting_verbal = "drafting_verbal"
    drafting_visual = "drafting_visual"
    drafting_compliance = "drafting_compliance"
    postprocessing = "postprocessing"
    chunking = "chunking"
    embedding = "embedding"
    done = "done"


class Severity(str, Enum):
    hard = "hard"  # violarla invalida la pieza: el Mód. II bloquea, el Mód. III rechaza
    soft = "soft"  # recomendación: genera warning


class Modality(str, Enum):
    text = "text"
    visual = "visual"
    both = "both"


class RuleType(str, Enum):
    # Dominio textual — lo consulta el Módulo II
    strategy = "strategy"
    audience = "audience"
    tone = "tone"
    lexicon = "lexicon"
    grammar = "grammar"
    messaging = "messaging"
    channel = "channel"
    # Dominio visual — lo consulta el Módulo III
    color = "color"
    typography = "typography"
    logo = "logo"
    photography = "photography"
    composition = "composition"
    iconography = "iconography"
    packaging = "packaging"
    # Transversal
    compliance = "compliance"


class ContentType(str, Enum):
    product_description = "product_description"
    video_script = "video_script"
    image_prompt = "image_prompt"
    social_post = "social_post"


class ContentStatus(str, Enum):
    """Flujo de gobernanza del Módulo III.

    `pending_a` → revisión de texto (Aprobador A)
    `pending_b` → auditoría visual (Aprobador B)
    """

    draft = "draft"
    pending_a = "pending_a"
    pending_b = "pending_b"
    approved = "approved"
    rejected = "rejected"


class AuditVerdict(str, Enum):
    passed = "pass"
    warn = "warn"
    fail = "fail"


class Channel(str, Enum):
    packaging = "packaging"
    ecommerce_pdp = "ecommerce_pdp"
    instagram = "instagram"
    tiktok = "tiktok"
    facebook = "facebook"
    email = "email"
    ooh = "ooh"
    tv_radio = "tv_radio"
    web = "web"
    punto_de_venta = "punto_de_venta"


#: Conjuntos de pre-filtrado del RAG. Son la razón de ser del chunking semántico:
#: sin ellos, una consulta sobre el tamaño del logo puede devolver reglas de léxico.
TEXT_RULE_TYPES: frozenset[RuleType] = frozenset(
    {
        RuleType.strategy,
        RuleType.audience,
        RuleType.tone,
        RuleType.lexicon,
        RuleType.grammar,
        RuleType.messaging,
        RuleType.channel,
        RuleType.compliance,
    }
)

VISUAL_RULE_TYPES: frozenset[RuleType] = frozenset(
    {
        RuleType.color,
        RuleType.typography,
        RuleType.logo,
        RuleType.photography,
        RuleType.composition,
        RuleType.iconography,
        RuleType.packaging,
    }
)
