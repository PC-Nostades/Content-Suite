"""El validador determinista del Módulo II.

Estos tests son el contrato del guardrail: si el validador falla, el Creative
Engine deja pasar violaciones reales del manual. Corren sin red.
"""

import pytest

from app.modules.creative.validator import (
    blocking_violations,
    find_violations,
    format_feedback,
)

LEXICON = {
    "forbidden_terms": [
        {"term": "light", "match_mode": "exact", "severity": "hard",
         "replacement": "sin azúcar añadida", "reason": "Claim regulado."},
        {"term": "adelgaz", "match_mode": "stem", "severity": "hard",
         "replacement": "te acompaña", "reason": "Efecto de pérdida de peso."},
        {"term": r"\d+%\s*natural", "match_mode": "regex", "severity": "hard",
         "replacement": "de origen vegetal", "reason": "Requiere sustento."},
        {"term": "delicioso", "match_mode": "exact", "severity": "soft",
         "replacement": "crocante", "reason": "Adjetivo genérico."},
    ],
    "forbidden_claims": [
        {"term": "cura", "match_mode": "stem", "severity": "hard",
         "replacement": "aporta", "reason": "Propiedad curativa."},
    ],
}


# ------------------------------------------------------------ match_mode: exact


def test_exact_detecta_la_palabra_completa():
    v = find_violations("Es un snack light y rico", LEXICON)
    assert [x.term for x in v] == ["light"]


def test_exact_no_da_falso_positivo_como_subcadena():
    """Sin `\\b`, 'light' cazaría dentro de 'lighthouse' o 'delight'."""
    assert find_violations("Un delight de producto en el lighthouse", LEXICON) == []


def test_exact_es_insensible_a_mayusculas():
    assert len(find_violations("Producto LIGHT", LEXICON)) == 1


# ------------------------------------------------------------- match_mode: stem


@pytest.mark.parametrize(
    "texto", ["te adelgaza rapido", "producto adelgazante", "ayuda al adelgazamiento"]
)
def test_stem_detecta_los_derivados(texto):
    """Es la razón de ser de `stem`: con `exact` estas tres frases pasarían."""
    v = find_violations(texto, LEXICON)
    assert any(x.term == "adelgaz" for x in v), texto


def test_stem_respeta_el_limite_izquierdo_de_palabra():
    """`\\b` al inicio evita cazar dentro de otra palabra."""
    assert not any(x.term == "adelgaz" for x in find_violations("readelgazar", LEXICON))


# ------------------------------------------------------------ match_mode: regex


def test_regex_detecta_el_patron():
    v = find_violations("Es 100% natural y sano", LEXICON)
    assert any(x.term.startswith(r"\d") for x in v)


def test_regex_invalido_no_rompe_la_validacion():
    """Un patrón mal formado del LLM no debe tumbar la generación."""
    lexicon = {"forbidden_terms": [
        {"term": "[sin-cerrar", "match_mode": "regex", "severity": "hard",
         "replacement": "x", "reason": "y"}
    ]}
    assert find_violations("cualquier texto", lexicon) == []


# --------------------------------------------------------------------- Acentos


def test_detecta_ignorando_acentos():
    """'Adelgazá' debe caer igual que 'adelgaza': el modelo puede acentuar."""
    assert any(x.term == "adelgaz" for x in find_violations("Te adelgazá rápido", LEXICON))


# ------------------------------------------------------------------- Severidad


def test_solo_las_hard_bloquean():
    """Si todo bloqueara, el ciclo de reparación no convergería."""
    v = find_violations("Un snack delicioso", LEXICON)
    assert len(v) == 1 and v[0].severity == "soft"
    assert blocking_violations(v) == []


def test_las_hard_si_bloquean():
    v = find_violations("Un snack light", LEXICON)
    assert len(blocking_violations(v)) == 1


# ---------------------------------------------------------------- Claims aparte


def test_los_claims_se_marcan_con_su_propio_kind():
    v = find_violations("Este producto cura la anemia", LEXICON)
    assert any(x.kind == "forbidden_claim" for x in v)


# ------------------------------------------------------------------- Feedback


def test_el_feedback_dice_que_cambiar_y_por_que_termino():
    """Un feedback genérico no converge; hay que nombrar el reemplazo exacto."""
    v = blocking_violations(find_violations("Snack light que adelgaza", LEXICON))
    texto = format_feedback(v)
    assert "sin azúcar añadida" in texto
    assert "te acompaña" in texto
    assert "light" in texto


# ------------------------------------------------------------------ Casos borde


def test_texto_vacio_no_lanza():
    assert find_violations("", LEXICON) == []


def test_lexicon_vacio_no_lanza():
    assert find_violations("cualquier cosa", {}) == []


def test_texto_limpio_no_produce_violaciones():
    limpio = "Quinua de Puno, sin azúcar añadida, crocante y con energía que dura."
    assert find_violations(limpio, LEXICON) == []
