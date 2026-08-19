"""Dependencias de FastAPI: sesión de BD, usuario actual y control de rol (RBAC).

El RBAC se aplica **en el servidor**, siempre. Ocultar un botón en el frontend es
UX, no seguridad: un aprobador que fuerce `POST /brands` con su token válido recibe
un 403 desde aquí. Hay un test que lo comprueba.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.exceptions import Forbidden, InvalidCredentials
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InvalidCredentials("Falta el token de autenticación.")
    return token


async def get_current_user(request: Request, db: DbSession) -> User:
    token = _extract_bearer_token(request)

    payload = decode_access_token(token)
    if payload is None:
        raise InvalidCredentials("Tu sesión expiró o el token no es válido.")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidCredentials("Token malformado.") from exc

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise InvalidCredentials("La cuenta no existe o está desactivada.")

    # El rol se relee de la BD, no del token: si a un usuario se le cambia el rol,
    # su token vigente no debe seguir concediéndole el permiso anterior.
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole):
    """Genera una dependencia que exige uno de los roles indicados.

    Uso:  `@router.post("/brands", dependencies=[Depends(require_role(UserRole.creator))])`
    o     `user: Annotated[User, Depends(require_role(UserRole.creator))]`
    """
    allowed_set = set(allowed) | {UserRole.admin}  # admin siempre pasa

    async def _dependency(user: CurrentUser) -> User:
        if user.role not in allowed_set:
            nombres = ", ".join(sorted(r.value for r in allowed))
            raise Forbidden(
                f"Esta acción requiere el rol: {nombres}. Tu rol actual es «{user.role.value}»."
            )
        return user

    return _dependency
