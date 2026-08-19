import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.deps import get_current_user
from app.core.enums import UserRole
from app.db.models import User
from app.main import app


def make_user(role: UserRole, email: str | None = None) -> User:
    """Usuario en memoria, sin tocar la BD.

    Los tests de RBAC no necesitan Postgres: lo que se valida es la dependencia
    `require_role`, no la persistencia. Mantenerlos sin red los hace rápidos y
    ejecutables en CI sin credenciales.
    """
    user = User(
        id=uuid.uuid4(),
        email=email or f"{role.value}@test.local",
        password_hash="x",
        full_name=f"Test {role.value}",
        role=role,
        is_active=True,
    )
    return user


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def as_role():
    """Sustituye `get_current_user` por un usuario del rol pedido.

    Devuelve una función; el override se limpia al terminar cada test.
    """
    def _apply(role: UserRole) -> User:
        user = make_user(role)
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    yield _apply
    app.dependency_overrides.pop(get_current_user, None)
