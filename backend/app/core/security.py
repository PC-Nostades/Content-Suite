"""Hashing de contraseñas y emisión/validación de JWT.

Decisiones (ver README, sección de decisiones de diseño):
  - **PyJWT**, no `python-jose`: este último está abandonado y arrastra
    CVE-2024-33663 (crítica) sin parche. FastAPI ya migró a PyJWT.
  - **bcrypt directo**, no `passlib`: passlib está sin mantenimiento y se rompe
    con `bcrypt>=4.1` (busca un atributo `__about__` que ya no existe).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.core.config import settings

# bcrypt trunca silenciosamente en 72 bytes; cortamos explícitamente para que
# el comportamiento sea el mismo al hashear y al verificar.
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Hash malformado en la BD: se trata como credencial inválida, no como 500.
        return False


def create_access_token(*, user_id: UUID | str, email: str, role: str) -> tuple[str, int]:
    """Devuelve `(token, expires_in_segundos)`.

    El `role` viaja en el token para que el frontend pinte el shell sin esperar a
    `/auth/me`, pero el backend **siempre** lo revalida contra la firma en cada
    request. El frontend nunca es la fuente de autoridad del RBAC.
    """
    expires_delta = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    now = datetime.now(UTC)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Devuelve el payload si el token es válido y no expiró; `None` en caso contrario."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
