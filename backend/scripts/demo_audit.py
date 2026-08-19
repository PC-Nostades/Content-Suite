"""Demostración de la auditoría multimodal (Módulo III).

    python scripts/demo_audit.py

Audita dos piezas idénticas salvo por el tamaño del logo. Si el sistema funciona,
la que tiene el logo al 4 % debe incumplir la regla del 8 % y **citar su rule_id**.
Guardar esta salida para la presentación.
"""

import asyncio
from pathlib import Path

import _bootstrap  # noqa: F401

from sqlalchemy import select

from app.ai.observability import init_observability, shutdown_observability
from app.db.models import Brand, BrandManual
from app.db.session import SessionLocal, engine
from app.modules.governance.auditor import audit_image

IMAGENES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "images"

ICONO = {"pass": "[ OK ]", "warn": "[WARN]", "fail": "[FAIL]"}


async def main() -> int:
    init_observability()

    async with SessionLocal() as db:
        fila = await db.scalar(
            select(BrandManual).where(BrandManual.status == "published").limit(1)
        )
        if fila is None:
            print("No hay manuales publicados. Ejecuta: python scripts/seed_demo.py")
            return 1
        brand = await db.get(Brand, fila.brand_id)

        regla_logo = next(
            (
                r
                for r in fila.content["visual"]["visual_rules"]
                if "logo" in r["statement"].lower() and "%" in r["statement"]
            ),
            None,
        )
        print(f"Marca: {brand.name}")
        print(f"Regla del manual bajo prueba:")
        if regla_logo:
            print(f"  id    : {regla_logo['id']}")
            print(f"  regla : {regla_logo['statement']}")
            print(f"  check : {regla_logo['check_hint']}")
        print()

        for nombre, esperado in (("pieza_ok.png", "pass"), ("pieza_mala.png", "fail")):
            ruta = IMAGENES / nombre
            if not ruta.exists():
                print(f"Falta {ruta}. Ejecuta: python scripts/make_test_images.py")
                return 1

            resultado, rule_ids, ms = await audit_image(
                db,
                brand_id=brand.id,
                image_bytes=ruta.read_bytes(),
                mime_type="image/png",
                focus="tamaño del logo, zona de resguardo, paleta y contraste",
            )

            print("=" * 78)
            acierto = "✓" if resultado.verdict == esperado else "✗ (esperado: " + esperado + ")"
            print(f"  {nombre}  →  {ICONO[resultado.verdict]}  {acierto}   ({ms} ms)")
            print(f"  {resultado.summary}")
            print(f"  reglas evaluadas: {len(rule_ids)}")
            print("-" * 78)
            for f in resultado.findings:
                print(f"   {ICONO[f.verdict]} [{f.rule_id}]  conf={f.confidence}")
                print(f"        {f.rule_statement[:70]}")
                print(f"        evidencia: {f.evidence[:150]}")
            print()

    shutdown_observability()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
