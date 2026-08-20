"""El ciclo de reparación del grafo del Módulo II.

En la práctica el modelo casi nunca usa un término prohibido: el contexto del RAG
ya lo frena en generación (comprobado pidiéndole explícitamente que los usara —
se negó). Eso es lo deseable, pero deja el ciclo sin ejercitar.

Estos tests lo prueban de forma determinista, sustituyendo el nodo `generate`
por uno que sí viola las reglas. Verifican la arista condicional, el ciclo y su
convergencia, sin gastar una sola llamada al modelo.
"""

import uuid

import pytest

from app.modules.creative import graph as g

LEXICON = {
    "forbidden_terms": [
        {"term": "light", "match_mode": "exact", "severity": "hard",
         "replacement": "sin azúcar añadida", "reason": "Claim regulado."},
    ],
    "forbidden_claims": [],
}


@pytest.fixture
def sin_retrieval(monkeypatch):
    """Sustituye `retrieve` para no tocar la BD ni la API de embeddings."""

    async def fake_retrieve(state):
        return {
            "rules_context": "(reglas de prueba)",
            "retrieved_rule_ids": ["verbal.text.regla_de_prueba"],
            "lexicon": LEXICON,
            "attempts": 0,
            "fixed_violations": [],
        }

    monkeypatch.setattr(g, "node_retrieve", fake_retrieve)


def _estado_inicial():
    return {
        "brand_id": uuid.uuid4(),
        "content_type": "social_post",
        "channel": "instagram",
        "brief": "un post de prueba",
        "_db": None,
    }


async def test_sin_violaciones_el_grafo_termina_sin_reparar(monkeypatch, sin_retrieval):
    async def genera_limpio(state):
        return {"title": "Snack andino", "body": "Quinua de Puno, sin azúcar añadida.",
                "rationale": "ok"}

    monkeypatch.setattr(g, "node_generate", genera_limpio)

    resultado = await g.build_graph().ainvoke(_estado_inicial())

    assert resultado["attempts"] == 0
    assert resultado["fixed_violations"] == []
    assert resultado["violations"] == []


async def test_una_violacion_dispara_la_reparacion_y_converge(monkeypatch, sin_retrieval):
    """La arista condicional debe llevar a `repair`, y tras corregir, terminar."""
    llamadas = {"generate": 0, "repair": 0}

    async def genera_sucio(state):
        llamadas["generate"] += 1
        return {"title": "Snack light", "body": "Un producto light.", "rationale": "x"}

    async def repara(state):
        llamadas["repair"] += 1
        return {
            "title": "Snack sin azúcar añadida",
            "body": "Un producto sin azúcar añadida.",
            "rationale": "corregido",
            "attempts": state.get("attempts", 0) + 1,
            "fixed_violations": [*(state.get("fixed_violations") or []), *state["violations"]],
        }

    monkeypatch.setattr(g, "node_generate", genera_sucio)
    monkeypatch.setattr(g, "node_repair", repara)

    resultado = await g.build_graph().ainvoke(_estado_inicial())

    assert llamadas["generate"] == 1, "generate se ejecuta una sola vez"
    assert llamadas["repair"] == 1, "la violación debió disparar exactamente una reparación"
    assert resultado["attempts"] == 1
    assert resultado["violations"] == [], "tras reparar no deben quedar violaciones"
    assert [v["term"] for v in resultado["fixed_violations"]] == ["light"]
    assert "light" not in resultado["body"].lower()


async def test_el_ciclo_se_detiene_en_max_repairs(monkeypatch, sin_retrieval):
    """Si el modelo nunca corrige, el grafo NO puede quedarse en bucle infinito.

    Termina y reporta lo que no pudo arreglar: un guardrail que miente sobre su
    resultado es peor que no tenerlo.
    """
    reparaciones = {"n": 0}

    async def genera_sucio(state):
        return {"title": "Snack light", "body": "light light.", "rationale": "x"}

    async def repara_mal(state):
        reparaciones["n"] += 1
        return {
            "title": "Sigue light",
            "body": "Todavía light.",
            "rationale": "no corregido",
            "attempts": state.get("attempts", 0) + 1,
            "fixed_violations": state.get("fixed_violations") or [],
        }

    monkeypatch.setattr(g, "node_generate", genera_sucio)
    monkeypatch.setattr(g, "node_repair", repara_mal)

    resultado = await g.build_graph().ainvoke(_estado_inicial())

    assert reparaciones["n"] == g.MAX_REPAIRS, "debe agotar los reintentos y parar"
    assert resultado["attempts"] == g.MAX_REPAIRS
    # Y las violaciones se reportan, no se ocultan.
    assert [v["term"] for v in resultado["violations"]] == ["light"]


async def test_exceder_el_limite_del_canal_dispara_la_reparacion(monkeypatch):
    """El límite de caracteres del canal se aplica igual que el léxico.

    En la práctica el modelo ya no se pasa (la guía va explícita en el prompt y
    generó 76 de 90 caracteres a la primera), pero la aplicación tiene que
    funcionar igualmente: prevenir no es lo mismo que garantizar.
    """

    async def fake_retrieve(state):
        return {
            "rules_context": "(reglas)",
            "retrieved_rule_ids": [],
            "lexicon": {"forbidden_terms": [], "forbidden_claims": []},
            "channel_guideline": {"channel": "packaging", "max_chars": 90},
            "attempts": 0,
            "fixed_violations": [],
        }

    async def genera_largo(state):
        return {"title": "Titular", "body": "x" * 200, "rationale": "x"}

    async def repara_corto(state):
        return {
            "title": "Titular",
            "body": "Quinua de Puno, sin azúcar añadida. 30 g.",
            "rationale": "recortado",
            "attempts": state.get("attempts", 0) + 1,
            "fixed_violations": [*(state.get("fixed_violations") or []), *state["violations"]],
        }

    monkeypatch.setattr(g, "node_retrieve", fake_retrieve)
    monkeypatch.setattr(g, "node_generate", genera_largo)
    monkeypatch.setattr(g, "node_repair", repara_corto)

    resultado = await g.build_graph().ainvoke(_estado_inicial())

    assert resultado["attempts"] == 1, "el exceso de longitud debió disparar la reparación"
    assert resultado["violations"] == [], "tras recortar no debe quedar violación"
    assert [v["kind"] for v in resultado["fixed_violations"]] == ["channel_limit"]
    assert len(f"{resultado['title']}\n{resultado['body']}".strip()) <= 90


async def test_sin_guia_de_canal_no_se_impone_ningun_limite(monkeypatch):
    """Si el manual no declara ese canal, no se inventa un límite."""

    async def fake_retrieve(state):
        return {
            "rules_context": "(reglas)",
            "retrieved_rule_ids": [],
            "lexicon": {},
            "channel_guideline": {},
            "attempts": 0,
            "fixed_violations": [],
        }

    async def genera_largo(state):
        return {"title": "T", "body": "x" * 3000, "rationale": "x"}

    monkeypatch.setattr(g, "node_retrieve", fake_retrieve)
    monkeypatch.setattr(g, "node_generate", genera_largo)

    resultado = await g.build_graph().ainvoke(_estado_inicial())
    assert resultado["attempts"] == 0
    assert resultado["violations"] == []


async def test_una_violacion_soft_no_dispara_reparacion(monkeypatch):
    """Si las `soft` bloquearan, el ciclo no convergería en textos normales."""

    async def fake_retrieve(state):
        return {
            "rules_context": "(reglas)",
            "retrieved_rule_ids": [],
            "lexicon": {"forbidden_terms": [
                {"term": "delicioso", "match_mode": "exact", "severity": "soft",
                 "replacement": "crocante", "reason": "genérico"}
            ]},
            "attempts": 0,
            "fixed_violations": [],
        }

    async def genera(state):
        return {"title": "Snack delicioso", "body": "Muy delicioso.", "rationale": "x"}

    monkeypatch.setattr(g, "node_retrieve", fake_retrieve)
    monkeypatch.setattr(g, "node_generate", genera)

    resultado = await g.build_graph().ainvoke(_estado_inicial())

    assert resultado["attempts"] == 0, "una soft no debe disparar el ciclo"
    # Pero sí se reporta, para que el usuario la vea.
    assert [v["term"] for v in resultado["violations"]] == ["delicioso"]
