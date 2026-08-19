"""Adaptador único hacia Gemini.

**Todas** las llamadas al modelo pasan por aquí. Si la API del SDK cambia — y ya
cambió una vez, de `google-generativeai` a `google-genai` — se toca una función y
nada más. Los módulos II y III consumirán `generate_structured` y `generate_vision`
sin conocer al SDK.

Dos niveles de resiliencia, distintos y complementarios:

1. `HttpRetryOptions` (lo hace el SDK) → fallos de **transporte**: 429, 5xx,
   timeouts de red. Reintentar es correcto porque la petición nunca llegó a buen
   puerto.
2. **Bucle de reparación** (lo hacemos aquí) → el modelo respondió, pero con JSON
   que no valida contra el schema. Reintentar a ciegas no sirve: hay que
   devolverle los errores de validación para que corrija.

Confundir ambos es el error clásico: se reintenta 5 veces un JSON malformado y se
gastan 5 llamadas del cupo gratuito para obtener el mismo JSON malformado.
"""

import asyncio
import json
import logging
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import LLMGenerationError, RateLimited

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Cliente singleton. Se crea perezosamente para que importar este módulo no
    exija una API key (los tests de schema corren sin credenciales)."""
    global _client
    if _client is None:
        if not settings.GEMINI_API_KEY:
            raise LLMGenerationError("Falta GEMINI_API_KEY: no se puede llamar al modelo.")
        _client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.LLM_TIMEOUT_SECONDS * 1000,  # el SDK espera ms
                retry_options=types.HttpRetryOptions(
                    attempts=5,
                    initial_delay=1.0,
                    max_delay=30.0,
                    exp_base=2,
                    jitter=1,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
    return _client


def _es_rate_limit(exc: Exception) -> bool:
    texto = str(exc).lower()
    return "429" in texto or "resource_exhausted" in texto or "quota" in texto


#: Keywords de JSON Schema que la API rechaza o ignora en `response_schema`.
#: `default` provoca un 400 INVALID_ARGUMENT; `title` se acepta pero solo gasta
#: tokens del presupuesto de schema sin aportar nada al modelo.
_KEYWORDS_NO_SOPORTADAS = frozenset(
    {"default", "title", "exclusiveMinimum", "exclusiveMaximum", "pattern", "format"}
)


def sanitize_schema(node: object) -> object:
    """Poda recursivamente las keywords que la API no admite.

    Se sanea en vez de evitar los defaults en los modelos Pydantic porque los
    modelos también se usan para validar y persistir, donde `default` sí es útil
    (`Rule.id` se rellena en el post-proceso, no lo escribe el LLM).

    Mantenerlo como una lista explícita hace que el próximo caso de este tipo sea
    una línea, y no otra sesión de bisección contra la API.
    """
    if isinstance(node, dict):
        return {
            k: sanitize_schema(v)
            for k, v in node.items()
            if k not in _KEYWORDS_NO_SOPORTADAS
        }
    if isinstance(node, list):
        return [sanitize_schema(v) for v in node]
    return node


def to_gemini_schema(model: type[BaseModel]) -> dict:
    """JSON Schema de un modelo Pydantic, listo para `response_schema`."""
    return sanitize_schema(model.model_json_schema())  # type: ignore[return-value]


#: El free tier tiene un RPM bajo. El agente lanza 3 etapas en paralelo, lo cual
#: es seguro; este semáforo evita que reintentos y peticiones concurrentes de
#: varios usuarios se acumulen hasta provocar 429 en cascada.
_gen_semaphore = asyncio.Semaphore(3)


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

    El bucle de reparación reenvía los errores de validación de Pydantic junto con
    la respuesta anterior truncada. En la práctica el modelo corrige al primer
    intento; los dos reintentos son para el caso patológico.
    """
    client = get_client()
    model_id = model or settings.GEMINI_TEXT_MODEL
    gemini_schema = to_gemini_schema(schema)

    prompt = user_input
    ultimo_error: Exception | None = None
    crudo = ""

    for intento in range(max_repair_attempts + 1):
        try:
            async with _gen_semaphore:
                response = await client.aio.models.generate_content(
                    model=model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=temperature,
                        max_output_tokens=max_output_tokens,
                        response_mime_type="application/json",
                        response_schema=gemini_schema,
                    ),
                )
        except Exception as exc:
            # Aquí ya se agotaron los reintentos de transporte del SDK.
            if _es_rate_limit(exc):
                raise RateLimited(
                    "Se alcanzó el límite de la API de Gemini. Intenta de nuevo en unos segundos.",
                    retry_after_seconds=30,
                ) from exc
            # El mensaje crudo de la API se conserva en `hint`: un
            # "400 INVALID_ARGUMENT" sin detalle obliga a bisecar el schema a
            # mano contra la API, gastando cuota.
            raise LLMGenerationError(
                f"Error al llamar al modelo en la etapa «{label}»: {type(exc).__name__}",
                hint=str(exc)[:400],
            ) from exc

        # `response.parsed` ya viene tipado cuando el JSON valida contra el schema.
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed

        # Si no, se valida a mano para obtener los errores concretos que
        # alimentan el prompt de reparación.
        crudo = (response.text or "").strip()
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
                f"Tu respuesta anterior no cumplió el schema. Errores detectados:\n"
                f"{str(exc)[:1500]}\n\n"
                f"Fragmento de tu respuesta anterior:\n{crudo[:1500]}\n\n"
                f"Devuelve el JSON COMPLETO y corregido. Solo JSON, sin markdown."
            )
            await asyncio.sleep(0.5 * (intento + 1))

    raise LLMGenerationError(
        f"La etapa «{label}» no produjo un JSON válido tras "
        f"{max_repair_attempts + 1} intentos.",
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
    """Análisis multimodal. Lo consumirá el Módulo III para auditar imágenes.

    Se escribe aquí, en la capa compartida, porque el Módulo III no debe importar
    "hacia adentro" del Módulo I. Temperatura baja por defecto: una auditoría
    debe ser reproducible, no creativa.
    """
    client = get_client()
    model_id = model or settings.GEMINI_VISION_MODEL

    config_kwargs: dict = {
        "system_instruction": system,
        "temperature": temperature,
    }
    if schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = schema

    response = await client.aio.models.generate_content(
        model=model_id,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            user_input,
        ],
        config=types.GenerateContentConfig(**config_kwargs),
    )

    if schema is None:
        return (response.text or "").strip()

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, schema):
        return parsed
    return schema.model_validate_json((response.text or "").strip())


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embeddings con `gemini-embedding-2`.

    Auto-normaliza al truncar dimensiones (verificado: a 1536 dims devuelve norma
    L2 = 1.0000), así que no hace falta renormalizar. `gemini-embedding-001` sí lo
    exigía.
    """
    client = get_client()
    response = await client.aio.models.embed_content(
        model=settings.GEMINI_EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIM),
    )
    return [list(e.values or []) for e in (response.embeddings or [])]
