"""Demostración del pre-filtrado por dominio del RAG.

    python scripts/demo_rag.py

Es la prueba visible del criterio «Arquitectura RAG» del reto: la MISMA consulta
devuelve conjuntos distintos según la modalidad, y una consulta visual nunca
alcanza las reglas de léxico. Guardar esta salida para la presentación.
"""

import asyncio

import _bootstrap  # noqa: F401

from sqlalchemy import select

from app.ai.observability import init_observability, shutdown_observability
from app.ai.retrieval import retrieve_rules
from app.core.enums import Modality
from app.db.models import Brand, BrandManual
from app.db.session import SessionLocal, engine

CONSULTAS = [
    ("¿qué tamaño mínimo debe tener el logo en la pieza?", Modality.visual),
    ("¿qué tamaño mínimo debe tener el logo en la pieza?", Modality.text),
    ("¿qué palabras están prohibidas en los textos?", Modality.text),
    ("¿qué palabras están prohibidas en los textos?", Modality.visual),
    ("¿cómo deben ser las fotografías de producto?", Modality.visual),
]


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
        print(f"Marca: {brand.name}\n")

        for consulta, modalidad in CONSULTAS:
            chunks, ms = await retrieve_rules(
                db, brand_id=brand.id, query=consulta, modality=modalidad, top_k=4
            )
            print("=" * 78)
            print(f"  «{consulta}»")
            print(f"  filtro modality={modalidad.value}  ·  {ms} ms  ·  {len(chunks)} resultados")
            print("-" * 78)
            for i, c in enumerate(chunks):
                print(f"   {i}. {c.similarity:.3f}  {c.section:<36} [{c.rule_type}/{c.modality}]")
            tipos = sorted({c.rule_type for c in chunks})
            print(f"   rule_types devueltos: {tipos}")
            if modalidad == Modality.visual and "lexicon" in tipos:
                print("   ⚠️  FALLO: una consulta visual devolvió reglas de léxico")
            print()

    shutdown_observability()
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
