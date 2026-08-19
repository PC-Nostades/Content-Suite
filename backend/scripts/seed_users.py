"""Crea los 3 usuarios de demo (uno por rol). Idempotente.

    python scripts/seed_users.py

Las credenciales resultantes son las que se entregan al evaluador. La contraseña
sale de DEMO_PASSWORD en el `.env`.
"""

import asyncio

import _bootstrap  # noqa: F401

from sqlalchemy import func, select

from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.db.models import User
from app.db.session import SessionLocal, engine

DEMO_USERS = [
    ("creator@alicorp.demo", "Ana Creadora", UserRole.creator),
    ("approver.a@alicorp.demo", "Bruno Aprobador A", UserRole.approver_a),
    ("approver.b@alicorp.demo", "Carla Aprobadora B", UserRole.approver_b),
]


async def main() -> int:
    password = settings.DEMO_PASSWORD
    # Un solo hash para los tres: bcrypt cuesta ~250 ms por hash y aquí no aporta
    # nada tener sales distintas — son cuentas de demo con la misma contraseña.
    hashed = hash_password(password)

    async with SessionLocal() as db:
        for email, full_name, role in DEMO_USERS:
            existente = await db.scalar(
                select(User).where(func.lower(User.email) == email.lower())
            )
            if existente:
                existente.full_name = full_name
                existente.role = role
                existente.password_hash = hashed
                existente.is_active = True
                accion = "actualizado"
            else:
                db.add(
                    User(
                        email=email,
                        full_name=full_name,
                        role=role,
                        password_hash=hashed,
                        is_active=True,
                    )
                )
                accion = "creado"
            print(f"  {role.value:<12} {email:<28} {accion}")
        await db.commit()

    print(f"\nContraseña para los tres: {password}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
