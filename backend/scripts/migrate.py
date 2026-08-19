"""Aplica las migraciones SQL de `backend/db/migrations/` en orden.

    python scripts/migrate.py            # aplica las pendientes
    python scripts/migrate.py --status   # solo muestra el estado

Las migraciones son idempotentes (`create ... if not exists`), pero se lleva
registro en `public.schema_migrations` para no reejecutarlas sin necesidad y para
que el estado sea visible.

Alternativa manual: pegar cada archivo en el SQL Editor de Supabase, en orden.
"""

import argparse
import asyncio
import hashlib
from pathlib import Path

import _bootstrap  # noqa: F401

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"

_REGISTRY_DDL = """
create table if not exists public.schema_migrations (
  filename    text primary key,
  checksum    text not null,
  applied_at  timestamptz not null default now()
);
"""


def _discover() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


async def _applied(conn) -> dict[str, str]:
    rows = (await conn.execute(text("select filename, checksum from public.schema_migrations"))).all()
    return {r.filename: r.checksum for r in rows}


async def run(status_only: bool = False) -> int:
    archivos = _discover()
    if not archivos:
        print(f"No hay migraciones en {MIGRATIONS_DIR}")
        return 1

    async with engine.begin() as conn:
        await conn.execute(text(_REGISTRY_DDL))
        aplicadas = await _applied(conn)

    print(f"Base de datos: {settings.DATABASE_URL.split('@')[-1]}")
    print(f"Migraciones encontradas: {len(archivos)}\n")

    pendientes: list[Path] = []
    for path in archivos:
        chk = _checksum(path)
        previo = aplicadas.get(path.name)
        if previo is None:
            print(f"  [ pendiente ] {path.name}")
            pendientes.append(path)
        elif previo != chk:
            # El archivo cambió después de aplicarse. Como el SQL es idempotente,
            # reaplicarlo es seguro y es lo que se quiere durante el desarrollo.
            print(f"  [ modificada] {path.name}  (se reaplica)")
            pendientes.append(path)
        else:
            print(f"  [  aplicada ] {path.name}")

    if status_only:
        return 0
    if not pendientes:
        print("\nNada que aplicar.")
        return 0

    print()
    for path in pendientes:
        sql = path.read_text(encoding="utf-8")
        print(f"→ Aplicando {path.name} ...", end=" ", flush=True)
        try:
            # Cada migración va en su propia transacción: si una falla, las
            # anteriores quedan aplicadas y el registro es consistente.
            async with engine.begin() as conn:
                await conn.exec_driver_sql(sql)
                await conn.execute(
                    text(
                        "insert into public.schema_migrations (filename, checksum) "
                        "values (:f, :c) "
                        "on conflict (filename) do update set checksum = excluded.checksum, "
                        "applied_at = now()"
                    ),
                    {"f": path.name, "c": _checksum(path)},
                )
            print("OK")
        except Exception as exc:  # noqa: BLE001
            print("FALLA")
            print(f"\n  {type(exc).__name__}: {exc}\n")
            return 1

    print("\nMigraciones aplicadas correctamente.")
    return 0


async def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica las migraciones SQL.")
    parser.add_argument("--status", action="store_true", help="Solo mostrar estado")
    args = parser.parse_args()
    try:
        return await run(status_only=args.status)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
