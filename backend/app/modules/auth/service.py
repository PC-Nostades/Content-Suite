"""Lógica de autenticación."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCredentials
from app.core.security import create_access_token, verify_password
from app.db.models import User
from app.modules.auth.schemas import TokenResponse, UserOut


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Búsqueda case-insensitive: hay un índice único sobre `lower(email)`."""
    return await db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


async def authenticate(db: AsyncSession, email: str, password: str) -> TokenResponse:
    user = await get_user_by_email(db, email)

    # Mismo mensaje para "no existe" y "contraseña incorrecta": no filtramos qué
    # correos están registrados.
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise InvalidCredentials()

    token, expires_in = create_access_token(
        user_id=user.id, email=user.email, role=user.role.value
    )
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserOut.model_validate(user),
    )
