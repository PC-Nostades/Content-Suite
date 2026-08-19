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

        # Instrumenta google-genai DESPUÉS de crear el cliente, para que los spans
        # automáticos se adjunten al tracer provider correcto.
        try:
            from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

            GoogleGenAIInstrumentor().instrument()
            logger.info("Instrumentación de google-genai activada")
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo instrumentar google-genai: %s", exc)

    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse no pudo inicializarse (%s). Se continúa sin trazas.", exc)

    _initialized = True


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
