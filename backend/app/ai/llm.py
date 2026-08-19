"""Interfaz única hacia el LLM, independiente del proveedor.

Todo el resto de la aplicación importa de aquí. Cambiar de proveedor es cambiar
`LLM_PROVIDER` en el entorno: ni el agente, ni el indexer, ni los módulos II y III
saben qué hay detrás.

Esto no es abstracción especulativa — se pagó sola en este proyecto. Empezamos
con Gemini y hubo que migrar a OpenAI a mitad de camino porque el free tier de
Gemini limita a 20 peticiones al día por modelo, insuficiente para un flujo
agéntico de 4 llamadas por manual. Con esta capa, la migración tocó un archivo.

Ambos proveedores exponen la misma firma:
    generate_structured(schema=..., system=..., user_input=..., ...) -> BaseModel
    generate_vision(system=..., user_input=..., image_bytes=..., ...) -> BaseModel | str
    embed_batch(texts) -> list[list[float]]
"""

from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover
    pass

T = TypeVar("T", bound=BaseModel)


def _provider():
    """Importa el módulo del proveedor activo.

    La importación es perezosa para no exigir ambos SDKs instalados a la vez ni
    una API key al importar (los tests de schema corren sin credenciales).
    """
    if settings.LLM_PROVIDER == "openai":
        from app.ai.providers import openai_provider

        return openai_provider

    from app.ai.providers import gemini_provider

    return gemini_provider


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
    return await _provider().generate_structured(
        schema=schema,
        system=system,
        user_input=user_input,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        max_repair_attempts=max_repair_attempts,
        label=label,
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
    return await _provider().generate_vision(
        system=system,
        user_input=user_input,
        image_bytes=image_bytes,
        mime_type=mime_type,
        schema=schema,
        model=model,
        temperature=temperature,
    )


async def embed_batch(texts: list[str]) -> list[list[float]]:
    return await _provider().embed_batch(texts)
