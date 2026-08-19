"""Siembra marcas de demo a partir de manuales ya generados.

    python scripts/seed_demo.py

**Por qué existe:** la demo del visor no debe depender de una llamada en vivo al
LLM. Si el evaluador abre la app y lo primero que ve es un spinner de 80 segundos
—o peor, un error de rate limit— la impresión ya está hecha. Con marcas sembradas
hay contenido real desde el primer segundo, y el botón «generar» queda como
demostración opcional.

Solo consume API para los embeddings (1 petición por marca), no para generar.
Es idempotente: reejecutarlo reemplaza la marca y reindexa.
"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from sqlalchemy import delete, func, select

from app.ai.observability import init_observability, shutdown_observability
from app.ai.schemas.brand_manual import BrandManual
from app.core.config import settings
from app.core.enums import GenerationStage, ManualStatus, UserRole
from app.db.models import Brand, BrandManual as BrandManualRow, User
from app.db.session import SessionLocal, engine
from app.modules.brand_dna.indexer import index_manual
from app.modules.brand_dna.service import slugify

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

#: (archivo, brief). El brief se conserva para que la UI muestre de qué semilla
#: salió el manual y para poder regenerarlo desde la app.
SEEDS: list[tuple[str, dict]] = [
    (
        "manual_generado.json",
        {
            "brand_name": "Kiwicha Pop",
            "product_category": "snack saludable de quinua inflada",
            "tone": "divertido pero profesional",
            "target_audience": "Gen Z urbana peruana, 18-26 años",
            "brand_values": ["autenticidad", "energía", "orgullo andino"],
            "key_differentiator": "grano de Puno, sin azúcar añadida",
            "price_positioning": "medio",
            "market": "Perú",
            "channels": ["tiktok", "instagram", "packaging"],
            "language": "es-PE",
            "constraints": "Cumplir la Ley 30021 de Alimentación Saludable (octógonos).",
        },
    ),
    (
        "manual_quinua.json",
        {
            "brand_name": "Kiwicha Pop Clásico",
            "product_category": "snack de quinua inflada (manual de referencia)",
            "tone": "divertido pero profesional",
            "target_audience": "Gen Z urbana limeña, 18-26 años",
            "brand_values": ["autenticidad", "energía"],
            "market": "Perú",
            "channels": ["tiktok", "instagram", "packaging"],
            "language": "es-PE",
        },
    ),
]


async def sembrar_marca(db, *, creator: User, archivo: str, brief: dict) -> bool:
    ruta = FIXTURES / archivo
    if not ruta.exists():
        print(f"  OMITIDA  {archivo} (no existe)")
        return False

    manual = BrandManual.model_validate(json.loads(ruta.read_text(encoding="utf-8")))
    nombre = brief["brand_name"]
    slug = slugify(nombre)

    # Idempotente: se borra la marca previa con el mismo slug (cascade limpia
    # manuales y chunks).
    previa = await db.scalar(select(Brand).where(Brand.slug == slug))
    if previa is not None:
        await db.execute(delete(Brand).where(Brand.id == previa.id))
        await db.flush()

    brand = Brand(
        name=nombre,
        slug=slug,
        category=brief["product_category"],
        market=brief.get("market", "PE"),
        brief=brief,
        owner_id=creator.id,
    )
    db.add(brand)
    await db.flush()

    fila = BrandManualRow(
        brand_id=brand.id,
        version=1,
        status=ManualStatus.published,
        stage=GenerationStage.done,
        content=manual.model_dump(mode="json"),
        input_params=brief,
        model=f"{settings.LLM_PROVIDER}:{settings.text_model}",
        prompt_version="1.0.0",
        generation_ms=0,
        created_by=creator.id,
        published_at=datetime.now(UTC),
    )
    db.add(fila)
    await db.flush()

    stats = await index_manual(db, manual=manual, manual_id=fila.id, brand_id=brand.id)
    print(
        f"  OK       {nombre:<24} {stats['chunks']} chunks "
        f"({stats['by_modality']}) · {stats['avg_tokens']} tok/chunk"
    )
    return True


async def main() -> int:
    init_observability()
    print("Sembrando marcas de demostración...\n")

    sembradas = 0
    async with SessionLocal() as db:
        # La transacción se abre al principio: cualquier SELECT previo la iniciaría
        # implícitamente y `db.begin()` fallaría con "transaction already begun".
        async with db.begin():
            creator = await db.scalar(
                select(User).where(User.role == UserRole.creator).order_by(User.created_at)
            )
            if creator is None:
                print("No hay usuario 'creator'. Ejecuta antes: python scripts/seed_users.py")
                return 1

            for archivo, brief in SEEDS:
                if await sembrar_marca(db, creator=creator, archivo=archivo, brief=brief):
                    sembradas += 1

    async with SessionLocal() as db:
        from app.db.models import ManualChunk

        total_marcas = await db.scalar(select(func.count()).select_from(Brand))
        total_chunks = await db.scalar(select(func.count()).select_from(ManualChunk))

    print(f"\n  {sembradas} marcas sembradas.")
    print(f"  Total en la BD: {total_marcas} marcas · {total_chunks} chunks indexados.")

    shutdown_observability()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
