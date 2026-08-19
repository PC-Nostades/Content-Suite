"""Embeddings para el RAG, independientes del proveedor.

La asimetría documento/consulta se implementa con prefijos de instrucción y no
con un parámetro del proveedor. Es la forma que funciona con AMBOS: Gemini
`gemini-embedding-2` no soporta `task_type`, y OpenAI nunca lo tuvo. Que la
técnica sea la misma en los dos evita que cambiar de proveedor altere en silencio
la calidad de la recuperación.

Dimensión: 1536. Es la nativa de `text-embedding-3-small` y está por debajo del
límite de 2000 que pgvector puede indexar con el tipo `vector` — con las 3072
por defecto de Gemini el índice HNSW ni siquiera se crea.
"""

import asyncio
import logging

from app.ai.llm import embed_batch
from app.core.config import settings
from app.core.exceptions import LLMGenerationError

logger = logging.getLogger(__name__)

#: Los prefijos se aplican SOLO al texto que se embebe, nunca al `content` que se
#: persiste: si el prefijo se guardara, contaminaría el contexto que reciben los
#: LLM de los Módulos II y III.
DOC_PREFIX = "Regla del manual de marca:\n"
QUERY_PREFIX = "Consulta: encuentra las reglas del manual de marca relevantes para:\n"

BATCH_SIZE = 64
_semaphore = asyncio.Semaphore(3)


async def _embed_chunked(prepared: list[str]) -> list[list[float]]:
    async def _uno(lote: list[str]) -> list[list[float]]:
        async with _semaphore:
            vectores = await embed_batch(lote)

        if len(vectores) != len(lote):
            raise LLMGenerationError(
                f"Se pidieron {len(lote)} embeddings y llegaron {len(vectores)}."
            )
        for v in vectores:
            if len(v) != settings.EMBEDDING_DIM:
                raise LLMGenerationError(
                    f"Dimensión inesperada: se esperaban {settings.EMBEDDING_DIM} "
                    f"y llegaron {len(v)}. El índice HNSW rechazaría estos vectores."
                )
        return vectores

    lotes = [prepared[i : i + BATCH_SIZE] for i in range(0, len(prepared), BATCH_SIZE)]
    resultados = await asyncio.gather(*(_uno(lote) for lote in lotes))
    return [vector for lote in resultados for vector in lote]


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embebe chunks del manual para indexarlos."""
    if not texts:
        return []
    return await _embed_chunked([DOC_PREFIX + t for t in texts])


async def embed_query(text: str) -> list[float]:
    """Embebe una consulta de búsqueda."""
    vectores = await _embed_chunked([QUERY_PREFIX + text])
    return vectores[0]
