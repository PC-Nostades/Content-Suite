"""Genera un Manual de Marca desde la línea de comandos, sin tocar la BD.

    python scripts/generate_manual.py --preset quinua
    python scripts/generate_manual.py --preset quinua --out tests/fixtures/manual_quinua.json

Sirve para dos cosas: iterar los prompts sin levantar el stack completo, y
producir el fixture con el que se desarrollan el chunking y el RAG **sin gastar
llamadas al modelo**.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import _bootstrap  # noqa: F401

from app.ai.observability import init_observability, shutdown_observability
from app.core.enums import GenerationStage
from app.modules.brand_dna.agent import run_agent

PRESETS: dict[str, dict] = {
    "quinua": {
        "brand_name": "Kiwicha Pop",
        "product_category": "snack saludable de quinua inflada",
        "tone": "divertido pero profesional",
        "target_audience": "Gen Z urbana peruana, 18-26 años, Lima",
        "brand_values": ["autenticidad", "energía", "orgullo andino"],
        "key_differentiator": "grano de Puno, sin azúcar añadida",
        "price_positioning": "medio",
        "market": "Perú",
        "channels": ["instagram", "tiktok", "packaging"],
        "language": "es-PE",
        "constraints": (
            "No usar la palabra 'saludable' sin respaldo nutricional. "
            "Cumplir la Ley de Alimentación Saludable (octógonos)."
        ),
    },
    "aceite": {
        "brand_name": "Valle Dorado",
        "product_category": "aceite de oliva extra virgen premium",
        "tone": "cálido y confiable, con autoridad culinaria",
        "target_audience": "amas de casa y cocineros aficionados de 35-55 años, NSE B/C",
        "brand_values": ["tradición", "pureza", "familia"],
        "key_differentiator": "prensado en frío de olivares de Tacna",
        "price_positioning": "premium",
        "market": "Perú",
        "channels": ["packaging", "punto_de_venta", "facebook"],
        "language": "es-PE",
    },
    "bebida": {
        "brand_name": "Volt Andino",
        "product_category": "bebida deportiva isotónica natural",
        "tone": "enérgico y retador, sin agresividad",
        "target_audience": "millennials deportistas de 27-38 años en ciudades grandes",
        "brand_values": ["superación", "naturalidad", "constancia"],
        "key_differentiator": "electrolitos de sal rosada, sin colorantes artificiales",
        "price_positioning": "medio",
        "market": "Perú",
        "channels": ["instagram", "ecommerce_pdp", "punto_de_venta"],
        "language": "es-PE",
    },
}

_ETIQUETAS = {
    GenerationStage.drafting_strategy: "Definiendo estrategia y audiencias",
    GenerationStage.drafting_visual: "Generando identidad verbal, visual y cumplimiento",
    GenerationStage.postprocessing: "Post-proceso determinista",
}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Genera un Manual de Marca.")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="quinua")
    parser.add_argument("--out", type=Path, help="Ruta donde guardar el JSON resultante")
    parser.add_argument("--no-trace", action="store_true", help="No enviar trazas a Langfuse")
    args = parser.parse_args()

    if not args.no_trace:
        init_observability()

    brief = PRESETS[args.preset]
    print(f"Brief: {brief['brand_name']} — {brief['product_category']}\n")

    inicio = time.monotonic()

    async def on_stage(stage: GenerationStage) -> None:
        etiqueta = _ETIQUETAS.get(stage, stage.value)
        print(f"  [{time.monotonic() - inicio:5.1f}s] {etiqueta}...")

    try:
        manual, report, meta = await run_agent(brief, on_stage=on_stage)
    except Exception as exc:  # noqa: BLE001
        print(f"\nFALLÓ: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if not args.no_trace:
            shutdown_observability()

    print(f"\n{'=' * 66}")
    print(f"  Manual generado en {meta['generation_ms'] / 1000:.1f}s")
    print(f"{'=' * 66}")

    r = meta["rules"]
    print(f"  Reglas verbales     : {r['verbal']}")
    print(f"  Reglas visuales     : {r['visual']}  (con check_hint: {r['visual_con_check_hint']})")
    print(f"  Reglas compliance   : {r['compliance']}")
    print(f"  Severidad 'hard'    : {r['hard']}")
    print(f"  Términos prohibidos : {r['forbidden_terms']}")
    print(f"  Claims prohibidos   : {r['forbidden_claims']}")
    print(f"  Colores en paleta   : {r['colores']}")

    p = meta["postprocess"]
    print("\n  Post-proceso:")
    print(f"    ids asignados        : {p['rules_labeled']}")
    print(f"    hex normalizados     : {p['hex_normalized']}  (descartados: {p['hex_discarded']})")
    print(f"    duplicados quitados  : {p['duplicate_terms_removed']}")
    if p["low_contrast_pairs"]:
        print(f"    pares de bajo contraste: {', '.join(p['low_contrast_pairs'][:4])}")
    if p["inconsistent_headlines"]:
        print(f"    titulares incoherentes : {p['inconsistent_headlines'][0]}")

    print("\n  Muestra de reglas VISUALES (las que auditará el Módulo III):")
    for rule in manual.visual.visual_rules[:4]:
        print(f"    · [{rule.severity.value}] {rule.statement[:74]}")
        print(f"      check: {rule.check_hint[:74]}")

    print("\n  Muestra de términos PROHIBIDOS (los que filtrará el Módulo II):")
    for term in manual.verbal.forbidden_terms[:4]:
        print(f"    · «{term.term}» ({term.match_mode}) → «{term.replacement}»")

    print(f"\n  Paleta: {'  '.join(c.hex + ' ' + c.name for c in manual.visual.color_palette[:5])}")
    print(f"  Logo: mínimo {manual.visual.logo.min_relative_width_pct}% del ancho de la pieza")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(manual.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n  Guardado en {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
