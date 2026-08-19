from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.modules.auth import service
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesión")
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Devuelve un JWT HS256 con `sub`, `email`, `role`, `iat` y `exp`.

    El frontend lee el `role` del payload para pintar el shell sin esperar red,
    pero el backend lo revalida contra la firma en cada request.
    """
    return await service.authenticate(db, payload.email, payload.password)


@router.get("/me", response_model=UserOut, summary="Usuario autenticado")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión")
async def logout(user: CurrentUser) -> None:
    """No-op del lado del servidor: el JWT es stateless y el cliente descarta el token.

    Existe por simetría con el frontend y como punto de enganche para auditoría.
    """
    return None
