"""El RBAC se aplica en el SERVIDOR.

Ocultar un botón en el frontend es UX. Estos tests prueban que un aprobador con
un token perfectamente válido recibe 403 al intentar una acción de creador — que
es la afirmación que el reto evalúa bajo "Gobernanza de Datos".
"""

import pytest
from fastapi import APIRouter, Depends

from app.core.deps import require_role
from app.core.enums import UserRole
from app.main import app

# Ruta de prueba montada una sola vez, protegida igual que lo estará
# `POST /brands`: solo el creador puede llamarla.
_router = APIRouter(prefix="/__test", tags=["test"])


@_router.post("/solo-creador")
async def solo_creador(_=Depends(require_role(UserRole.creator))) -> dict:
    return {"ok": True}


app.include_router(_router)


@pytest.mark.parametrize(
    ("role", "esperado"),
    [
        (UserRole.creator, 200),
        (UserRole.admin, 200),  # admin siempre pasa
        (UserRole.approver_a, 403),
        (UserRole.approver_b, 403),
    ],
)
async def test_require_role_aplica_por_rol(client, as_role, role, esperado):
    as_role(role)
    response = await client.post("/__test/solo-creador")
    assert response.status_code == esperado, response.text


async def test_el_403_explica_el_motivo(client, as_role):
    """El mensaje de error debe ser accionable, no un 'Forbidden' pelado."""
    as_role(UserRole.approver_b)
    response = await client.post("/__test/solo-creador")

    detalle = response.json()["detail"]
    assert detalle["code"] == "forbidden"
    assert "creator" in detalle["message"]
    assert "approver_b" in detalle["message"]


async def test_sin_token_es_401_no_403(client):
    """Distinguir 'no autenticado' de 'sin permisos' importa: el frontend
    redirige al login en el primer caso y muestra /403 en el segundo."""
    response = await client.post("/__test/solo-creador")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"
