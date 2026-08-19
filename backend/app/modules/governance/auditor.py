"""Auditoría multimodal: contrasta una imagen contra las reglas visuales del manual.

El diseño se apoya entero en una decisión tomada en el Módulo I: cada regla del
manual lleva un **`check_hint` cuantitativo**. Sin eso, esto sería pedirle a un
modelo su opinión estética. Con eso, se le pide que **mida**:

    ❌ "¿el logo se ve bien?"
    ✅ "mide el ancho del logo / ancho de la pieza; la regla exige >= 0.08"

Y cada hallazgo **cita el `rule_id`** que evaluó. Una auditoría que no puede
señalar qué regla concreta se incumplió no es gobernanza, es una opinión.
"""

import logging
import time
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import generate_vision
from app.ai.retrieval import format_rules_for_prompt, retrieve_rules
from app.core.config import settings
from app.core.enums import Modality

logger = logging.getLogger(__name__)


class Finding(BaseModel):
    """Un hallazgo de la auditoría, anclado a una regla del manual."""

    rule_id: str = Field(
        description=(
            "El id EXACTO de la regla evaluada, copiado del manual. "
            "Si el hallazgo no corresponde a ninguna regla listada, usa 'general'."
        )
    )
    rule_statement: str = Field(description="La regla evaluada, en una frase.")
    verdict: Literal["pass", "warn", "fail"]
    evidence: str = Field(
        description=(
            "Qué observaste en la imagen y qué medida obtuviste. Sé concreto: "
            "«el logo ocupa aproximadamente el 4% del ancho», no «el logo es pequeño»."
        )
    )
    confidence: Literal["alta", "media", "baja"] = Field(
        description="Baja si la imagen no permite medir con fiabilidad."
    )


class AuditResult(BaseModel):
    verdict: Literal["pass", "warn", "fail"] = Field(
        description=(
            "'fail' si incumple alguna regla de severidad hard; 'warn' si solo "
            "incumple reglas soft o hay dudas; 'pass' si cumple todo lo evaluable."
        )
    )
    summary: str = Field(description="Dos frases: qué cumple y qué no.")
    findings: list[Finding] = Field(min_length=1)


AUDIT_SYSTEM = """\
Eres auditor de identidad visual de marca. Tu trabajo es contrastar una pieza
gráfica contra las reglas del manual de marca y emitir un dictamen verificable.

CÓMO TRABAJAS
1. Para CADA regla del manual que recibas, decide si la imagen la cumple.
2. Usa el campo «Verificación» de cada regla como tu método de medición. Si la
   regla dice «medir el ancho del logo / ancho de la pieza >= 0.08», estima esa
   proporción mirando la imagen y compárala con el umbral.
3. En `evidence` escribe la MEDIDA que obtuviste, no una impresión.
   ✅ "el logo ocupa aproximadamente el 4% del ancho; la regla exige 8%"
   ❌ "el logo se ve pequeño"
4. Copia el `rule_id` EXACTO tal como aparece entre corchetes en cada regla.
   Ese id es lo que permite rastrear el dictamen hasta el manual.
5. Si la imagen no permite verificar una regla con fiabilidad (resolución,
   recorte, ángulo), marca `confidence: baja` y `verdict: warn`. NO inventes una
   medición que no puedes hacer.

VEREDICTO GLOBAL
- `fail` si incumple al menos una regla marcada como `hard`.
- `warn` si solo incumple reglas `soft`, o si hay hallazgos de confianza baja.
- `pass` si cumple todo lo que se puede evaluar.

Sé exigente pero justo: el objetivo es proteger la marca, no rechazar por rechazar.
Responde en español.
"""


async def audit_image(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    image_bytes: bytes,
    mime_type: str,
    focus: str = "",
) -> tuple[AuditResult, list[str], int]:
    """Audita una imagen. Devuelve `(resultado, rule_ids_evaluadas, latencia_ms)`.

    El pre-filtrado `modality=visual` es lo que hace esto viable: sin él, el RAG
    devolvería reglas de léxico y el modelo de visión intentaría auditar palabras
    prohibidas mirando una foto.
    """
    inicio = time.monotonic()

    consulta = (
        focus
        or "reglas de logo, color, tipografía, composición y fotografía para auditar una pieza gráfica"
    )
    chunks, _ms = await retrieve_rules(
        db, brand_id=brand_id, query=consulta, modality=Modality.visual, top_k=8
    )

    rule_ids: list[str] = []
    for c in chunks:
        rule_ids.extend(c.rule_ids)
    rule_ids = sorted(set(rule_ids))

    contexto = format_rules_for_prompt(chunks)
    entrada = (
        f"REGLAS VISUALES DEL MANUAL DE MARCA\n{contexto}\n\n"
        f"Audita la imagen adjunta contra estas reglas. Emite un hallazgo por cada "
        f"regla verificable que encuentres, citando su rule_id exacto."
    )

    resultado = await generate_vision(
        system=AUDIT_SYSTEM,
        user_input=entrada,
        image_bytes=image_bytes,
        mime_type=mime_type,
        schema=AuditResult,
    )
    assert isinstance(resultado, AuditResult)

    latencia_ms = int((time.monotonic() - inicio) * 1000)
    logger.info(
        "visual_audit · %s · %d hallazgos · %d reglas evaluadas · %d ms",
        resultado.verdict, len(resultado.findings), len(rule_ids), latencia_ms,
    )
    return resultado, rule_ids, latencia_ms


def model_label() -> str:
    return f"{settings.LLM_PROVIDER}:{settings.vision_model}"
