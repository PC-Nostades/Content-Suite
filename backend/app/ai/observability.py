"""Integración con Langfuse (Módulo IV), instrumentada desde el día 1.

Dos capas complementarias:

1. **Instrumentación automática** — `GoogleGenAIInstrumentor` convierte CADA llamada
   a `google-genai` (generación y embeddings) en un span con modelo, prompt,
   respuesta, tokens y latencia. Es el 70 % del Módulo IV con dos líneas.

2. **Árbol manual** — los `@observe` de `agent.py`, `chunking.py` y `retrieval.py`
   dan la estructura: qué contexto se recuperó del RAG, qué prompt se envió y
   cuánto tardó cada etapa. Que es literalmente lo que pide el enunciado.

⚠️ El SDK lee la configuración de variables de entorno del proceso, pero
pydantic-settings carga el `.env` SIN exportarlas a `os.environ`. Por eso aquí se
pasan explícitamente al constructor: si no, el cliente arranca deshabilitado y las
trazas se pierden en silencio — sin error, solo sin datos.
"""

import logging
from contextlib import contextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)

_initialized = False


def init_observability() -> None:
    """Inicializa Langfuse y la instrumentación de Gemini. Idempotente.

    Nunca lanza: si la observabilidad falla, la aplicación debe seguir funcionando.
    Perder trazas es un problema; caerse por no poder trazar, uno peor.
    """
    global _initialized
    if _initialized:
        return

    if not settings.langfuse_enabled:
        logger.info("Langfuse sin configurar: la app corre sin trazas.")
        _initialized = True
        return

    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            base_url=settings.LANGFUSE_BASE_URL,
            environment=settings.LANGFUSE_TRACING_ENVIRONMENT,
            release=settings.APP_VERSION,
        )

        if client.auth_check():
            logger.info("Langfuse conectado (%s)", settings.LANGFUSE_BASE_URL)
        else:
            logger.warning("Langfuse: auth_check() falló. Se continúa sin trazas.")

        # Instrumentación del proveedor activo, DESPUÉS de crear el cliente para
        # que los spans automáticos se adjunten al tracer provider correcto.
        if settings.LLM_PROVIDER == "openai":
            # `langfuse.openai` es un reemplazo directo del SDK: el propio
            # `openai_provider.get_client()` lo importa de ahí cuando hay trazado,
            # así que cada llamada genera su span sin código adicional.
            logger.info("Instrumentación de OpenAI activada (langfuse.openai)")
        else:
            try:
                from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

                GoogleGenAIInstrumentor().instrument()
                logger.info("Instrumentación de google-genai activada")
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo instrumentar google-genai: %s", exc)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse no pudo inicializarse (%s). Se continúa sin trazas.", exc)

    _initialized = True


@contextmanager
def traced(name: str, *, as_type: str = "span", **kwargs):
    """Abre un span de Langfuse, o un no-op si la observabilidad no está activa.

    Centraliza la llamada al SDK a propósito. La API de Langfuse ya cambió una vez
    bajo nuestros pies (`start_as_current_span` → `start_as_current_observation`) y
    estaba invocada desde cuatro sitios: con este envoltorio, el próximo cambio se
    arregla en una línea.

    Cede un objeto con `.update(...)` y una propiedad `.trace_id`, así el código
    que llama no necesita comprobar si hay trazado activo.
    """
    if not settings.langfuse_enabled:
        yield _NoopSpan()
        return

    try:
        from langfuse import get_client

        client = get_client()
        with client.start_as_current_observation(name=name, as_type=as_type, **kwargs) as span:
            yield _SpanHandle(span, client.get_current_trace_id())
    except Exception as exc:  # noqa: BLE001 — nunca romper por no poder trazar
        logger.debug("No se pudo abrir el span «%s»: %s", name, exc)
        yield _NoopSpan()


class _SpanHandle:
    def __init__(self, span, trace_id: str | None) -> None:
        self._span = span
        self.trace_id = trace_id

    def update(self, **kwargs) -> None:
        try:
            self._span.update(**kwargs)
        except Exception as exc:  # noqa: BLE001
            logger.debug("No se pudo actualizar el span: %s", exc)


class _NoopSpan:
    trace_id: str | None = None

    def update(self, **kwargs) -> None:  # noqa: D102
        return None


def shutdown_observability() -> None:
    """Flush obligatorio al apagar.

    Render duerme el proceso tras 15 min de inactividad; sin este flush, las
    trazas que estén en el buffer se pierden — justo las de la última interacción,
    que suele ser la que interesa auditar.
    """
    if not settings.langfuse_enabled:
        return
    try:
        from langfuse import get_client

        get_client().shutdown()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error al hacer flush de Langfuse: %s", exc)
