"""Punto de entrada de la API de Content Suite."""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.db.session import check_db_health, engine

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("content_suite")

_STARTED_AT = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Arrancando Content Suite API v%s (%s)", settings.APP_VERSION, settings.APP_ENV)
    logger.info(
        "Modelos: texto=%s · visión=%s · embeddings=%s (%d dims)",
        settings.GEMINI_TEXT_MODEL,
        settings.GEMINI_VISION_MODEL,
        settings.GEMINI_EMBEDDING_MODEL,
        settings.GEMINI_EMBEDDING_DIM,
    )
    yield
    # Cerrar el pool explícitamente: Render duerme el proceso y las conexiones
    # colgadas contra el pooler de Supabase tardan en liberarse.
    await engine.dispose()
    logger.info("API detenida")


app = FastAPI(
    title="Content Suite API",
    description=(
        "Plataforma de consistencia de marca para lanzamientos masivos de producto.\n\n"
        "**Módulo I — Brand DNA Architect**: genera un Manual de Marca estructurado "
        "y lo indexa en pgvector para que los módulos siguientes lo consulten vía RAG."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# CORS — red de seguridad.
# En producción el SPA proxea /api/* desde su propio origen (rewrite de Render), así
# que no debería dispararse ni un preflight. Esto queda configurado para poder volver
# al esquema cross-origin cambiando solo VITE_API_BASE_URL, sin tocar código.
# `allow_credentials=False` es deliberado: usamos Bearer, no cookies → sin superficie CSRF.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Todos los errores de dominio salen con la misma forma `{"detail": {...}}`."""
    headers = {}
    if exc.retry_after_seconds is not None:
        headers["Retry-After"] = str(exc.retry_after_seconds)
    return JSONResponse(
        status_code=exc.status_code, content={"detail": exc.to_detail()}, headers=headers
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "validation_error",
                "message": "Los datos enviados no son válidos.",
                "hint": "Revisa los campos marcados.",
                "errors": [
                    {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
                    for e in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Red de seguridad: cualquier excepción no prevista sale con la MISMA forma
    que el resto de errores.

    Sin esto, un fallo de conexión a la BD devuelve `Internal Server Error` en
    texto plano y el cliente no puede parsearlo — rompiendo el único camino de
    manejo de errores que tiene el frontend. Además, un 500 sin cabeceras CORS se
    reporta en el navegador como «CORS error», que manda a depurar al sitio
    equivocado.
    """
    logger.exception("Error no manejado en %s %s", request.method, request.url.path)

    detalle = {
        "code": "internal_error",
        "message": "Ocurrió un error inesperado en el servidor.",
    }
    # En local se expone la causa: acelera el diagnóstico. En producción no,
    # para no filtrar detalles internos.
    if not settings.is_production:
        detalle["hint"] = f"{type(exc).__name__}: {exc}"

    return JSONResponse(status_code=500, content={"detail": detalle})


@app.get("/health", tags=["health"], summary="Liveness")
async def health() -> dict:
    """No toca la BD a propósito: es el blanco del keep-alive y debe responder rápido
    incluso mientras el servicio despierta."""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "uptime_s": round(time.monotonic() - _STARTED_AT, 1),
    }


@app.get("/health/ready", tags=["health"], summary="Readiness (incluye BD)")
async def health_ready() -> JSONResponse:
    db_ok = await check_db_health()
    body = {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "gemini": "configured" if settings.GEMINI_API_KEY else "missing_key",
        "langfuse": "configured" if settings.langfuse_enabled else "disabled",
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=body)


app.include_router(api_router)
