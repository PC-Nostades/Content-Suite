"""Módulo II — Creative Engine, orquestado con LangGraph.

```
    retrieve ──► generate ──► validate ──┬─ sin violaciones ─► END
       ▲                                 │
       └────────── repair ◄──────────────┘  violaciones y intentos < 2
```

**Por qué LangGraph aquí y no en el Módulo I.** El agente del Módulo I es un
fan-out sin ciclos ni decisiones: `asyncio.gather` lo expresa mejor y envolverlo
en un grafo sería ceremonia. Este flujo, en cambio, tiene una **arista
condicional** y un **ciclo**: el resultado de `validate` decide si se termina o
se vuelve atrás. Eso es un grafo de verdad, y el estado explícito hace trivial
trazar por qué una pieza acabó como acabó.

Los nodos son funciones async que llaman a `app/ai/llm.py`. No entra
`langchain-openai`: la abstracción de proveedor se mantiene intacta y cambiar de
modelo sigue siendo una variable de entorno.
"""

import logging
import uuid
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import generate_structured
from app.ai.retrieval import format_rules_for_prompt, get_hard_lexicon, retrieve_rules
from app.core.enums import Modality
from app.modules.creative.validator import (
    Violation,
    blocking_violations,
    find_violations,
    format_feedback,
)

logger = logging.getLogger(__name__)

MAX_REPAIRS = 2

ContentType = Literal["product_description", "video_script", "image_prompt", "social_post"]

TIPO_INSTRUCCIONES: dict[str, str] = {
    "product_description": (
        "Escribe una DESCRIPCIÓN DE PRODUCTO para ecommerce: un titular corto y "
        "2-3 párrafos breves que cubran beneficio, diferenciador y cierre."
    ),
    "video_script": (
        "Escribe un GUION DE VIDEO corto (15-30 s) con marcas de tiempo, indicando "
        "qué se ve y qué se dice o se sobreimprime en cada bloque."
    ),
    "image_prompt": (
        "Escribe un PROMPT DE IMAGEN en español para un generador de imágenes: una "
        "instrucción densa que fije encuadre, luz, color y presencia de producto, "
        "coherente con el estilo fotográfico del manual."
    ),
    "social_post": (
        "Escribe un POST PARA REDES: gancho en la primera línea, cuerpo breve y "
        "cierre con invitación. Respeta el límite de caracteres del canal."
    ),
}


class GeneratedContent(BaseModel):
    """Salida estructurada del nodo `generate`."""

    title: str = Field(description="Titular o nombre corto de la pieza.")
    body: str = Field(description="El texto completo de la pieza.")
    rationale: str = Field(
        description="En una frase: qué reglas del manual guiaron las decisiones tomadas."
    )


# --------------------------------------------------------------------- Estado


class CreativeState(TypedDict, total=False):
    # Entrada
    brand_id: uuid.UUID
    content_type: str
    channel: str
    brief: str

    # Contexto recuperado
    rules_context: str
    retrieved_rule_ids: list[str]
    lexicon: dict

    # Generación
    title: str
    body: str
    rationale: str

    # Ciclo de validación
    violations: list[dict]
    fixed_violations: list[dict]
    attempts: int

    # Dependencia inyectada (no serializable: el grafo no se persiste)
    _db: Annotated[Any, lambda a, b: b]


# ---------------------------------------------------------------------- Nodos


async def node_retrieve(state: CreativeState) -> dict:
    """Recupera reglas de TEXTO y el léxico duro completo.

    Dos fuentes distintas a propósito: el RAG trae reglas de *guía* (tono,
    estructura, canal) y el léxico duro viene por SQL directo, porque necesita
    recall del 100 %.
    """
    db: AsyncSession = state["_db"]
    consulta = (
        f"{TIPO_INSTRUCCIONES.get(state['content_type'], '')} "
        f"Canal: {state.get('channel') or 'general'}. {state['brief']}"
    )

    chunks, _ms = await retrieve_rules(
        db,
        brand_id=state["brand_id"],
        query=consulta,
        modality=Modality.text,
        top_k=8,
    )
    lexicon = await get_hard_lexicon(db, state["brand_id"])

    rule_ids: list[str] = []
    for c in chunks:
        rule_ids.extend(c.rule_ids)

    logger.info(
        "creative.retrieve · %d chunks · %d términos prohibidos",
        len(chunks), len(lexicon.get("forbidden_terms") or []),
    )
    return {
        "rules_context": format_rules_for_prompt(chunks),
        "retrieved_rule_ids": sorted(set(rule_ids)),
        "lexicon": lexicon,
        "attempts": 0,
        "fixed_violations": [],
    }


SYSTEM_GENERATE = """\
Eres redactor publicitario senior para marcas de consumo masivo en Perú.

Escribes SIEMPRE respetando el manual de marca que recibes. El manual no es una
sugerencia: es la fuente de verdad. Si una regla dice que un término está
prohibido, no lo uses ni en una variante.

REGLAS DE TRABAJO
1. Ajusta el tono al espectro de voz y a los atributos declarados.
2. Usa los términos preferidos del manual y evita los prohibidos.
3. Respeta el límite de caracteres del canal indicado.
4. No inventes atributos del producto que no estén en el brief o el manual.
5. No hagas promesas de salud, resultados ni comparaciones con competidores.

En `rationale`, indica en UNA frase qué reglas concretas guiaron tus decisiones.
Responde en español (variante peruana neutra).
"""


async def node_generate(state: CreativeState) -> dict:
    instruccion = TIPO_INSTRUCCIONES.get(state["content_type"], "")
    entrada = (
        f"MANUAL DE MARCA (reglas recuperadas)\n{state['rules_context']}\n\n"
        f"TAREA\n{instruccion}\n"
        f"Canal: {state.get('channel') or 'general'}\n"
        f"Brief: {state['brief']}"
    )

    salida = await generate_structured(
        schema=GeneratedContent,
        system=SYSTEM_GENERATE,
        user_input=entrada,
        temperature=0.8,
        max_output_tokens=4096,
        label="creative.generate",
    )
    return {"title": salida.title, "body": salida.body, "rationale": salida.rationale}


def node_validate(state: CreativeState) -> dict:
    """Nodo determinista: aplica el léxico como código, no como criterio."""
    texto = f"{state.get('title', '')}\n{state.get('body', '')}"
    violaciones: list[Violation] = find_violations(texto, state.get("lexicon") or {})
    bloqueantes = blocking_violations(violaciones)

    logger.info(
        "creative.validate · %d violaciones (%d bloqueantes) en el intento %d",
        len(violaciones), len(bloqueantes), state.get("attempts", 0),
    )
    return {"violations": [v.as_dict() for v in violaciones]}


async def node_repair(state: CreativeState) -> dict:
    """Regenera indicando exactamente qué corregir."""
    violaciones = [Violation(**v) for v in state.get("violations") or []]
    bloqueantes = blocking_violations(violaciones)

    entrada = (
        f"MANUAL DE MARCA (reglas recuperadas)\n{state['rules_context']}\n\n"
        f"TEXTO A CORREGIR\nTitular: {state.get('title', '')}\n{state.get('body', '')}\n\n"
        f"{format_feedback(bloqueantes)}"
    )

    salida = await generate_structured(
        schema=GeneratedContent,
        system=SYSTEM_GENERATE,
        user_input=entrada,
        temperature=0.5,  # más baja: aquí se corrige, no se explora
        max_output_tokens=4096,
        label="creative.repair",
    )

    # Se acumulan las violaciones corregidas: es la evidencia visible de que el
    # RAG y el filtro determinista funcionaron, y se muestra en la UI.
    ya_corregidas = list(state.get("fixed_violations") or [])
    ya_corregidas.extend(v.as_dict() for v in bloqueantes)

    return {
        "title": salida.title,
        "body": salida.body,
        "rationale": salida.rationale,
        "attempts": state.get("attempts", 0) + 1,
        "fixed_violations": ya_corregidas,
    }


def route_after_validate(state: CreativeState) -> Literal["repair", "__end__"]:
    """La arista condicional: aquí es donde el grafo gana sobre asyncio."""
    violaciones = [Violation(**v) for v in state.get("violations") or []]
    if blocking_violations(violaciones) and state.get("attempts", 0) < MAX_REPAIRS:
        return "repair"
    return "__end__"


# ---------------------------------------------------------------------- Grafo


def build_graph():
    grafo = StateGraph(CreativeState)
    grafo.add_node("retrieve", node_retrieve)
    grafo.add_node("generate", node_generate)
    grafo.add_node("validate", node_validate)
    grafo.add_node("repair", node_repair)

    grafo.set_entry_point("retrieve")
    grafo.add_edge("retrieve", "generate")
    grafo.add_edge("generate", "validate")
    grafo.add_conditional_edges(
        "validate", route_after_validate, {"repair": "repair", "__end__": END}
    )
    # El ciclo: tras reparar se vuelve a validar. Si sigue violando y quedan
    # intentos, repara otra vez; si no, termina reportando lo que no pudo arreglar.
    grafo.add_edge("repair", "validate")

    return grafo.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run_creative(
    db: AsyncSession,
    *,
    brand_id: uuid.UUID,
    content_type: str,
    channel: str,
    brief: str,
) -> dict:
    """Ejecuta el grafo y devuelve el resultado con su trazabilidad."""
    estado_final = await get_graph().ainvoke(
        {
            "brand_id": brand_id,
            "content_type": content_type,
            "channel": channel,
            "brief": brief,
            "_db": db,
        }
    )

    pendientes = [
        v for v in (estado_final.get("violations") or []) if v.get("severity") == "hard"
    ]
    return {
        "title": estado_final.get("title", ""),
        "body": estado_final.get("body", ""),
        "rationale": estado_final.get("rationale", ""),
        "retrieved_rule_ids": estado_final.get("retrieved_rule_ids", []),
        # Violaciones que el ciclo detectó y corrigió: la prueba visible de que
        # el manual se respeta, no solo se consulta.
        "fixed_violations": estado_final.get("fixed_violations", []),
        # Las que sobrevivieron a los reintentos. Se reportan con honestidad en
        # vez de esconderlas: un guardrail que miente es peor que no tenerlo.
        "remaining_violations": pendientes,
        "repair_attempts": estado_final.get("attempts", 0),
    }
