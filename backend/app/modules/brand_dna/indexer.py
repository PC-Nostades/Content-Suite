"""Indexado del manual en pgvector: chunk → embed → persistir.

**Transaccional a propósito.** El indexado es "borra los chunks viejos, inserta
los nuevos y marca el manual como listo". Si eso fueran tres operaciones
independientes y fallara la segunda, quedaría un manual publicado con el índice
vacío — y el fallo solo se notaría cuando el Módulo II devolviera respuestas sin
contexto. Con una sola transacción, o queda todo o no queda nada.
"""

import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import chunk_manual
from app.ai.embeddings import embed_documents
from app.ai.schemas.brand_manual import BrandManual
from app.core.config import settings
from app.db.models import ManualChunk

logger = logging.getLogger(__name__)


async def index_manual(
    db: AsyncSession,
    *,
    manual: BrandManual,
    manual_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> dict:
    """Chunkea, embebe y persiste. Devuelve estadísticas para la traza.

    El caller es responsable del commit: así el indexado puede formar parte de la
    misma transacción que marca el manual como `ready`.
    """
    chunks = chunk_manual(manual)
    if not chunks:
        raise ValueError("El chunking no produjo ningún chunk.")

    vectores = await embed_documents([c.content for c in chunks])
    if len(vectores) != len(chunks):
        raise ValueError(
            f"Desajuste: {len(chunks)} chunks y {len(vectores)} embeddings."
        )

    # Reindexar es idempotente: se borran los chunks previos de este manual.
    await db.execute(delete(ManualChunk).where(ManualChunk.manual_id == manual_id))

    db.add_all(
        [
            ManualChunk(
                manual_id=manual_id,
                brand_id=brand_id,
                chunk_index=c.chunk_index,
                section=c.section,
                rule_type=c.rule_type,
                modality=c.modality,
                severity=c.severity,
                rule_ids=c.rule_ids,
                channel_scope=c.channel_scope,
                heading=c.heading,
                content=c.content,
                token_count=c.token_count,
                embedding=vector,
                embedding_model=settings.embedding_model,
                extra_metadata={},
            )
            for c, vector in zip(chunks, vectores, strict=True)
        ]
    )

    por_modalidad: dict[str, int] = {}
    for c in chunks:
        por_modalidad[c.modality.value] = por_modalidad.get(c.modality.value, 0) + 1

    stats = {
        "chunks": len(chunks),
        "avg_tokens": sum(c.token_count for c in chunks) // len(chunks),
        "by_modality": por_modalidad,
        "embedding_model": settings.embedding_model,
        "dims": settings.EMBEDDING_DIM,
    }
    logger.info("Manual %s indexado: %s", manual_id, stats)
    return stats
