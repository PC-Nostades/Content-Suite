"""Proveedor OpenAI.

Se eligió sobre Gemini por una razón operativa concreta: el free tier de Gemini
limita a **20 peticiones al día por modelo**, y el agente consume 4 por manual.
Eso son 5 manuales diarios contando los del evaluador — la demo moriría con un
429. Con crédito de pago ese riesgo desaparece.

Dos ventajas técnicas que además simplifican el código:

- **Structured outputs estrictos.** `strict: true` garantiza adherencia al schema
  por construcción, así que el bucle de reparación pasa a ser una red de
  seguridad y no el camino habitual.
- **`text-embedding-3-small` es nativo de 1536 dimensiones**, exactamente lo que
  ya declara la columna `vector(1536)`. Sin truncado, sin renormalizar, sin
  migración de base de datos.
"""

import asyncio
import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import LLMGenerationError, RateLimited

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client = None

#: El free tier de OpenAI también tiene límites de concurrencia; el agente lanza
#: 3 etapas en paralelo y esto evita que los reintentos se acumulen encima.
_gen_semaphore = asyncio.Semaphore(4)


def get_client():
    """Cliente async singleton.

    Se importa desde `langfuse.openai` cuando hay trazado activo: ese módulo es un
    reemplazo directo del SDK que instrumenta cada llamada automáticamente
    (modelo, prompt, respuesta, tokens, latencia). Es el 70 % del Módulo IV gratis.
    """
    global _client
    if _client is None:
        if not settings.OPENAI_API_KEY:
            raise LLMGenerationError("Falta OPENAI_API_KEY: no se puede llamar al modelo.")

        if settings.langfuse_enabled:
            from langfuse.openai import AsyncOpenAI
        else:
            from openai import AsyncOpenAI

        _client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=float(settings.LLM_TIMEOUT_SECONDS),
            max_retries=4,  # reintentos de TRANSPORTE (429/5xx) que hace el SDK
        )
    return _client


def _es_rate_limit(exc: Exception) -> bool:
    nombre = type(exc).__name__
    return nombre == "RateLimitError" or "429" in str(exc)


async def generate_structured(
    *,
    schema: type[T],
    system: str,
    user_input: str,
    model: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int = 32_768,
    max_repair_attempts: int = 2,
    label: str = "generate",
) -> T:
    """Genera una respuesta que valida contra `schema`, o lanza `LLMGenerationError`.

    Con `responses.parse` el SDK devuelve el objeto Pydantic ya construido. El
    bucle de reparación queda como red de seguridad para el caso en que el modelo
    rechace la petición o devuelva una respuesta incompleta.
    """
    client = get_client()
    model_id = model or settings.OPENAI_TEXT_MODEL

    prompt = user_input
    ultimo_error: Exception | None = None

    for intento in range(max_repair_attempts + 1):
        try:
            async with _gen_semaphore:
                response = await client.responses.parse(
                    model=model_id,
                    instructions=system,
                    input=prompt,
                    text_format=schema,
                    max_output_tokens=max_output_tokens,
                    reasoning={"effort": settings.OPENAI_REASONING_EFFORT},
                )
        except Exception as exc:
            if _es_rate_limit(exc):
                raise RateLimited(
                    "Se alcanzó el límite de la API. Intenta de nuevo en unos segundos.",
                    retry_after_seconds=20,
                ) from exc
            # El texto crudo de la API va en `hint`: un error sin detalle obliga a
            # bisecar el schema contra la API, que es lento y caro.
            raise LLMGenerationError(
                f"Error al llamar al modelo en la etapa «{label}»: {type(exc).__name__}",
                hint=str(exc)[:400],
            ) from exc

        parsed = getattr(response, "output_parsed", None)
        if isinstance(parsed, schema):
            return parsed

        # El modelo se negó a responder o la salida quedó incompleta.
        rechazo = getattr(response, "refusal", None)
        crudo = (getattr(response, "output_text", "") or "").strip()

        if rechazo:
            raise LLMGenerationError(
                f"El modelo rechazó la petición en la etapa «{label}».", hint=str(rechazo)[:300]
            )

        try:
            return schema.model_validate_json(crudo)
        except (ValidationError, json.JSONDecodeError) as exc:
            ultimo_error = exc
            if intento == max_repair_attempts:
                break
            logger.warning(
                "Etapa «%s»: la respuesta no validó (intento %d/%d). Reparando.",
                label, intento + 1, max_repair_attempts,
            )
            prompt = (
                f"{user_input}\n\n"
                f"--- CORRECCIÓN REQUERIDA ---\n"
                f"Tu respuesta anterior no cumplió el schema. Errores:\n{str(exc)[:1500]}\n\n"
                f"Devuelve el JSON COMPLETO y corregido."
            )
            await asyncio.sleep(0.5 * (intento + 1))

    raise LLMGenerationError(
        f"La etapa «{label}» no produjo un JSON válido tras {max_repair_attempts + 1} intentos.",
        hint=str(ultimo_error)[:300] if ultimo_error else None,
    )


async def generate_vision(
    *,
    system: str,
    user_input: str,
    image_bytes: bytes,
    mime_type: str = "image/png",
    schema: type[T] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> T | str:
    """Análisis multimodal para el Módulo III.

    Temperatura baja a propósito: una auditoría debe ser reproducible, no creativa.
    """
    import base64

    client = get_client()
    model_id = model or settings.OPENAI_VISION_MODEL
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"

    contenido = [
        {"type": "input_text", "text": user_input},
        {"type": "input_image", "image_url": data_url},
    ]
    entrada = [{"role": "user", "content": contenido}]

    reasoning = {"effort": settings.OPENAI_REASONING_EFFORT}

    if schema is None:
        response = await client.responses.create(
            model=model_id, instructions=system, input=entrada, reasoning=reasoning
        )
        return (response.output_text or "").strip()

    response = await client.responses.parse(
        model=model_id,
        instructions=system,
        input=entrada,
        text_format=schema,
        reasoning=reasoning,
    )
    parsed = getattr(response, "output_parsed", None)
    if isinstance(parsed, schema):
        return parsed
    return schema.model_validate_json((response.output_text or "").strip())


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embeddings de un lote.

    `text-embedding-3-small` devuelve 1536 dimensiones de forma nativa y los
    vectores ya vienen normalizados a norma 1, así que la distancia coseno del
    índice HNSW funciona directamente.
    """
    client = get_client()
    response = await client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.EMBEDDING_DIM,
    )
    # La API no garantiza el orden de salida; se ordena por índice explícitamente.
    ordenados = sorted(response.data, key=lambda d: d.index)
    return [list(d.embedding) for d in ordenados]
