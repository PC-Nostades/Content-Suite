"""Recuperación RAG sobre el manual de marca.

Es el contrato que consumen los Módulos II y III, y está instrumentado con
Langfuse desde el principio: el enunciado del Módulo IV pide poder ver «qué
contexto se recuperó del RAG», y eso se satisface aquí, no en cada módulo.

La búsqueda es **híbrida estructurada**: el filtro SQL da precisión (nunca
recupera del dominio equivocado) y el vector da recall semántico dentro del
dominio correcto. Es lo que impide que una consulta sobre el tamaño del logo
devuelva reglas de léxico.
"""

import logging
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_query
from app.core.enums import TEXT_RULE_TYPES, VISUAL_RULE_TYPES, Modality, RuleType, Severity

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    id: uuid.UUID
    manual_id: uuid.UUID
    chunk_index: int
    section: str
    rule_type: str
    modality: str
    severity: str
    heading: str
    content: str
    rule_ids: list[str]
    similarity: float


#: Conjuntos de pre-filtrado por módulo. Se exponen como constantes para que el
#: Módulo II y el III no tengan que reconstruirlos (y desincronizarse).
TEXT_DOMAIN = sorted(rt.value for rt in TEXT_RULE_TYPES)
VISUAL_DOMAIN = sorted(rt.value for rt in VISUAL_RULE_TYPES)


def _modalities_for(modality: Modality | None) -> list[str] | None:
    """`visual` incluye `both`: una regla transversal aplica también a imágenes."""
    if modality is None:
        return None
    if modality == Modality.visual:
        return [Modality.visual.value, Modality.both.value]
    if modality == Modality.text:
        return [Modality.text.value, Modality.both.value]
    return [Modality.both.value]


async def retrieve_rules(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    query: str,
    modality: Modality | None = None,
    rule_types: list[RuleType] | None = None,
    severities: list[Severity] | None = None,
    top_k: int = 8,
    threshold: float = 0.10,
    manual_id: uuid.UUID | None = None,
) -> tuple[list[RetrievedChunk], int]:
    """Recupera reglas relevantes. Devuelve `(chunks, latencia_ms)`.

    Sin `manual_id` se consulta el manual **publicado** de la marca: la fuente de
    verdad vigente.
    """
    inicio = time.monotonic()

    modalities = _modalities_for(modality)
    tipos = [rt.value for rt in rule_types] if rule_types else None
    sevs = [s.value for s in severities] if severities else None

    embedding = await embed_query(query)

    # pgvector espera el literal '[1,2,3]'; asyncpg no sabe serializar una lista
    # de floats a `vector` por sí solo.
    vector_literal = "[" + ",".join(f"{v:.7f}" for v in embedding) + "]"

    sql = text(
        """
        select id, manual_id, chunk_index, section, rule_type::text, modality::text,
               severity::text, heading, content, rule_ids, similarity
        from public.match_manual_chunks(
            :brand_id,
            (:embedding)::vector,
            (:modalities)::public.chunk_modality[],
            (:rule_types)::public.chunk_rule_type[],
            (:severities)::public.rule_severity[],
            :threshold,
            :match_count,
            :manual_id
        )
        """
    )

    rows = (
        await db.execute(
            sql,
            {
                "brand_id": brand_id,
                "embedding": vector_literal,
                "modalities": modalities,
                "rule_types": tipos,
                "severities": sevs,
                "threshold": threshold,
                "match_count": top_k,
                "manual_id": manual_id,
            },
        )
    ).mappings().all()

    chunks = [RetrievedChunk(**dict(r)) for r in rows]
    latencia_ms = int((time.monotonic() - inicio) * 1000)

    _trace(query, modality, tipos, top_k, threshold, chunks, latencia_ms)
    return chunks, latencia_ms


def _trace(query, modality, tipos, top_k, threshold, chunks, latencia_ms) -> None:
    """Registra en Langfuse qué se pidió y qué se recuperó.

    Es el requisito literal del Módulo IV: «ver qué contexto se recuperó del RAG».
    Se hace aquí y no en los módulos que llaman, para que ninguno pueda olvidarlo.
    """
    logger.info(
        "rag.retrieve · %d chunks en %d ms · modality=%s · query=%.60s",
        len(chunks), latencia_ms, modality.value if modality else "todas", query,
    )
    from app.ai.observability import traced

    with traced("rag.retrieve", as_type="retriever") as span:
        span.update(
            input={
                "query": query,
                "filters": {
                    "modality": modality.value if modality else None,
                    "rule_types": tipos,
                    "top_k": top_k,
                    "threshold": threshold,
                },
            },
            output=[
                {
                    "rank": i,
                    "section": c.section,
                    "rule_type": c.rule_type,
                    "modality": c.modality,
                    "severity": c.severity,
                    "similarity": round(c.similarity, 4),
                    "rule_ids": c.rule_ids,
                    "preview": c.content[:200],
                }
                for i, c in enumerate(chunks)
            ],
            metadata={
                "retrieved": len(chunks),
                "latency_ms": latencia_ms,
                "score_range": (
                    [round(chunks[-1].similarity, 4), round(chunks[0].similarity, 4)]
                    if chunks else None
                ),
            },
        )


async def get_hard_lexicon(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Léxico prohibido COMPLETO, sin pasar por RAG.

    Un check de palabra prohibida necesita 100 % de recall, y la búsqueda
    semántica no lo garantiza: podría devolver 8 de 15 términos y el Módulo II
    dejaría pasar violaciones reales. Por eso las restricciones duras se leen del
    JSONB por SQL directo y el RAG queda para las reglas de *guía*.
    """
    row = await db.execute(
        text("select public.get_hard_lexicon(:brand_id) as lexicon"), {"brand_id": brand_id}
    )
    return row.scalar_one() or {}


async def get_channel_guideline(
    db: AsyncSession, brand_id: uuid.UUID, channel: str
) -> dict | None:
    """Guía del canal pedido, leída del JSONB por SQL directo.

    Mismo principio que `get_hard_lexicon`: **RAG para guía, SQL para lo que no
    puede fallar**. El chunk del canal existe y el vector suele recuperarlo, pero
    "suele" no basta para un límite de caracteres — si no se recupera, el sistema
    generaría 400 caracteres para un panel de empaque limitado a 90 y nadie se
    enteraría.
    """
    if not channel:
        return None

    row = await db.execute(
        text(
            """
            select g
            from public.brand_manuals m,
                 jsonb_array_elements(m.content -> 'verbal' -> 'channel_guidelines') g
            where m.brand_id = :brand_id
              and m.status = 'published'
              and g ->> 'channel' = :channel
            limit 1
            """
        ),
        {"brand_id": brand_id, "channel": channel},
    )
    return row.scalar_one_or_none()


def format_rules_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Serializa los chunks recuperados como contexto para el LLM."""
    if not chunks:
        return "(no se recuperaron reglas del manual)"
    partes = []
    for c in chunks:
        partes.append(f"### {c.heading} [{c.section} · {c.severity}]\n{c.content}")
    return "\n\n".join(partes)
