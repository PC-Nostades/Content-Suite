"""Engine y sesiones async contra Supabase (Session Pooler).

⚠️ Las tres trampas de este stack, documentadas aquí porque cada una cuesta horas:

1. **Session Pooler, no conexión directa.** La conexión directa de Supabase es
   IPv6-only y Render no tiene IPv6 saliente. El Session Pooler (puerto 5432) es
   IPv4 *y* soporta prepared statements, así que asyncpg trabaja en su modo óptimo.
   El Transaction Pooler (6543) también es IPv4 pero NO los soporta y obligaría a
   desactivar la caché de statements.

2. **`sslmode` no va en la query string.** Es sintaxis de libpq; asyncpg lanza
   `TypeError`. Va en `connect_args={"ssl": ...}`.

3. **`pool_pre_ping` no es opcional.** El pooler corta conexiones ociosas y el free
   tier de Render duerme el proceso: sin pre-ping, el primer request tras el
   despertar falla con una conexión muerta.
"""

import logging
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_connect_args() -> dict:
    # Supabase presenta un certificado válido; se verifica el cifrado pero no se
    # exige la cadena completa, que requeriría distribuir el CA de Supabase.
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return {
        "ssl": ssl_context,
        "server_settings": {"application_name": "content-suite-api"},
        "timeout": 15,
    }


engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_build_connect_args(),
    # Render free tier = 1 instancia, 0.1 CPU. Un pool pequeño evita agotar
    # las conexiones del pooler de Supabase.
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.SQL_ECHO,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia de FastAPI: una sesión por request, con rollback ante excepción."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> bool:
    """Ping barato para `/health/ready`. No lanza: devuelve False y loguea."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 — health check nunca debe tumbar el proceso
        logger.warning("Health check de BD falló: %s", exc)
        return False
