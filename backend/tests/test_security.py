"""Hashing de contraseñas y ciclo de vida del JWT."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_verifica_correcta_y_rechaza_incorrecta():
    hashed = hash_password("Alicorp2026!")
    assert hashed != "Alicorp2026!"
    assert verify_password("Alicorp2026!", hashed)
    assert not verify_password("otra", hashed)


def test_hashes_distintos_para_la_misma_contrasena():
    """bcrypt sala cada hash: dos hashes de la misma clave deben diferir."""
    assert hash_password("misma") != hash_password("misma")


def test_hash_malformado_no_lanza():
    """Un hash corrupto en la BD se trata como credencial inválida, no como 500."""
    assert not verify_password("cualquiera", "no-es-un-hash-bcrypt")


def test_bcrypt_trunca_en_72_bytes_de_forma_consistente():
    """bcrypt ignora lo que pase de 72 bytes. Lo importante es que el truncado
    sea el mismo al hashear y al verificar, o contraseñas largas fallarían."""
    larga = "a" * 100
    hashed = hash_password(larga)
    assert verify_password(larga, hashed)
    assert verify_password("a" * 72, hashed)


def test_token_lleva_rol_y_expiracion():
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(
        user_id=user_id, email="x@y.z", role="creator"
    )

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "creator"
    assert expires_in == settings.JWT_EXPIRE_MINUTES * 60


def test_firma_invalida_devuelve_none():
    token, _ = create_access_token(user_id=uuid.uuid4(), email="x@y.z", role="creator")
    assert decode_access_token(token + "manipulado") is None


def test_token_expirado_devuelve_none():
    vencido = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "x@y.z",
            "role": "creator",
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert decode_access_token(vencido) is None


def test_token_firmado_con_otro_secreto_devuelve_none():
    ajeno = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "atacante@mal.com",
            "role": "admin",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        "secreto-del-atacante",
        algorithm="HS256",
    )
    assert decode_access_token(ajeno) is None


@pytest.mark.parametrize("basura", ["", "abc", "a.b.c", "Bearer x"])
def test_tokens_basura_no_lanzan(basura):
    assert decode_access_token(basura) is None
