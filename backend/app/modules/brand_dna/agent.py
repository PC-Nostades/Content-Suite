"""El agente Brand DNA Architect.

Genera en cuatro etapas, no en una sola llamada:

    brief ──► A: estrategia + audiencias        (~8 s, fundamento)
                 │
                 └─(A como contexto)──┬─ B: identidad verbal      ┐
                                      ├─ C: identidad visual      ├─ en paralelo
                                      └─ D: cumplimiento          ┘
                                              │
                              ensamblar → validar → post-proceso

Por qué multi-etapa y no una llamada única:

1. El schema completo son ~22 KB de JSON Schema. A esa escala el modelo trunca
   listas e ignora `minItems`, y la calidad se degrada hacia el final del
   documento — justo donde vive la identidad visual, que es lo que el Módulo III
   necesita preciso.
2. Cada schema de etapa es 2-7× menor, y la adherencia sube en consecuencia.
3. **Un fallo de validación cuesta una etapa, no 45 segundos de trabajo.**
4. B, C y D son independientes entre sí: corren concurrentes.
5. Las etapas dan progreso REAL al frontend. Una barra que avanza por nombres
   durante 45 s se percibe como un sistema serio; un spinner, como un cuelgue.
"""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

from app.ai.llm import generate_structured
from app.ai.postprocess import PostProcessReport, count_rules, postprocess_manual
from app.ai.prompts import (
    COMPLIANCE_SYSTEM,
    PROMPT_VERSION,
    STRATEGY_SYSTEM,
    VERBAL_SYSTEM,
    VISUAL_SYSTEM,
)
from app.ai.schemas.brand_manual import (
    BrandManual,
    Compliance,
    StrategyStage,
    VerbalIdentity,
    VisualIdentity,
)
from app.core.enums import GenerationStage
from app.core.exceptions import LLMGenerationError

logger = logging.getLogger(__name__)

#: Callback opcional para reportar avance. Lo usa el servicio para persistir
#: `brand_manuals.stage` y que el frontend lo muestre en el stepper.
StageCallback = Callable[[GenerationStage], Awaitable[None]]


def build_brief_text(brief: dict) -> str:
    """Convierte el brief del usuario en el prompt de entrada de la Etapa A.

    Se omiten los campos vacíos a propósito: un "Competidores: (no especificado)"
    invita al modelo a inventarlos.
    """
    etiquetas = {
        "brand_name": "Nombre de la marca",
        "product_category": "Categoría de producto",
        "tone": "Tono deseado",
        "target_audience": "Público objetivo",
        "brand_values": "Valores de marca",
        "key_differentiator": "Diferenciador clave",
        "price_positioning": "Posicionamiento de precio",
        "market": "Mercado",
        "competitors": "Competidores",
        "channels": "Canales prioritarios",
        "language": "Idioma / variante",
        "constraints": "Restricciones",
    }

    lineas = []
    for clave, etiqueta in etiquetas.items():
        valor = brief.get(clave)
        if valor in (None, "", [], {}):
            continue
        if isinstance(valor, list):
            valor = ", ".join(str(v) for v in valor)
        lineas.append(f"{etiqueta}: {valor}")

    return "BRIEF DE MARCA\n" + "\n".join(lineas)


def _contexto_de_estrategia(stage_a: StrategyStage) -> str:
    """Contexto compacto que reciben las etapas B, C y D.

    Se les pasa un resumen y no el JSON completo de la Etapa A: lo que necesitan
    es la dirección estratégica, y meterles 3 KB de JSON gasta contexto y los
    distrae con campos irrelevantes para su tarea.
    """
    s = stage_a.strategy
    audiencias = "\n".join(
        f"  - {a.label} ({a.age_range}): {a.description}\n"
        f"    Códigos culturales: {', '.join(a.cultural_codes)}"
        for a in stage_a.audiences
    )
    return (
        f"ESTRATEGIA DE MARCA YA DEFINIDA (respétala; no la contradigas)\n"
        f"Marca: {s.brand_name}\n"
        f"Categoría: {s.category}\n"
        f"Arquetipo: {s.brand_archetype}\n"
        f"Personalidad: {', '.join(s.personality_traits)}\n"
        f"Posicionamiento: {s.positioning_statement}\n"
        f"Propuesta de valor: {s.value_proposition}\n"
        f"Diferenciadores: {'; '.join(s.differentiators)}\n"
        f"Lo que NO es: {'; '.join(s.competitor_contrast)}\n"
        f"\nAUDIENCIAS\n{audiencias}\n"
    )


async def _noop_callback(_: GenerationStage) -> None:
    return None


async def run_agent(
    brief: dict,
    *,
    on_stage: StageCallback | None = None,
) -> tuple[BrandManual, PostProcessReport, dict]:
    """Genera un Manual de Marca completo.

    Devuelve `(manual, informe_de_postproceso, metadatos)`.
    Lanza `LLMGenerationError` si alguna etapa no logra producir JSON válido.
    """
    notify = on_stage or _noop_callback
    inicio = time.monotonic()

    # ---------------------------------------------------------------- Etapa A
    await notify(GenerationStage.drafting_strategy)
    brief_text = build_brief_text(brief)

    stage_a = await generate_structured(
        schema=StrategyStage,
        system=STRATEGY_SYSTEM,
        user_input=brief_text,
        temperature=0.8,  # la estrategia se beneficia de algo de divergencia
        label="strategy",
    )
    logger.info("Etapa A lista: %s (%s)", stage_a.strategy.brand_name, stage_a.strategy.brand_archetype)

    contexto = _contexto_de_estrategia(stage_a)
    restricciones = brief.get("constraints") or ""
    sufijo = f"\n\nRESTRICCIONES ADICIONALES DEL CLIENTE\n{restricciones}" if restricciones else ""

    # ------------------------------------------------- Etapas B, C y D en paralelo
    # Se notifica 'drafting_visual' porque es la etapa más lenta y la que más
    # importa: el stepper debe reflejar dónde está realmente el tiempo.
    await notify(GenerationStage.drafting_visual)

    tarea_verbal = generate_structured(
        schema=VerbalIdentity,
        system=VERBAL_SYSTEM,
        user_input=contexto + sufijo,
        temperature=0.7,
        label="verbal",
    )
    tarea_visual = generate_structured(
        schema=VisualIdentity,
        system=VISUAL_SYSTEM,
        user_input=contexto + sufijo,
        temperature=0.6,  # más baja: las reglas visuales deben ser precisas, no creativas
        label="visual",
    )
    tarea_compliance = generate_structured(
        schema=Compliance,
        system=COMPLIANCE_SYSTEM,
        user_input=contexto + f"\n\nMercado objetivo: {brief.get('market') or 'Perú'}" + sufijo,
        temperature=0.3,  # la más baja: aquí inventar es un riesgo real
        label="compliance",
    )

    # `return_exceptions=True` para poder decir QUÉ etapa falló, en vez de
    # propagar la primera excepción y perder el contexto de las otras dos.
    resultados = await asyncio.gather(
        tarea_verbal, tarea_visual, tarea_compliance, return_exceptions=True
    )
    verbal, visual, compliance = resultados

    fallos = [
        (nombre, r)
        for nombre, r in zip(("verbal", "visual", "compliance"), resultados, strict=True)
        if isinstance(r, BaseException)
    ]
    if fallos:
        detalle = "; ".join(f"{n}: {type(e).__name__}" for n, e in fallos)
        primera = fallos[0][1]
        if isinstance(primera, LLMGenerationError):
            raise primera
        raise LLMGenerationError(f"Fallaron etapas del agente ({detalle}).") from primera

    assert isinstance(verbal, VerbalIdentity)
    assert isinstance(visual, VisualIdentity)
    assert isinstance(compliance, Compliance)

    # -------------------------------------------------------------- Ensamblado
    await notify(GenerationStage.postprocessing)

    manual = BrandManual(
        executive_summary=stage_a.strategy.value_proposition,
        strategy=stage_a.strategy,
        audiences=stage_a.audiences,
        verbal=verbal,
        visual=visual,
        compliance=compliance,
    )

    report = postprocess_manual(manual)

    duracion_ms = int((time.monotonic() - inicio) * 1000)
    metadatos = {
        "generation_ms": duracion_ms,
        "prompt_version": PROMPT_VERSION,
        "rules": count_rules(manual),
        "postprocess": report.as_dict(),
    }
    logger.info(
        "Manual generado en %.1f s · %s",
        duracion_ms / 1000,
        json.dumps(metadatos["rules"], ensure_ascii=False),
    )

    return manual, report, metadatos
