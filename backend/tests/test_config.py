"""Invariantes de configuración que, de romperse, fallan tarde y en silencio."""

from app.core.config import settings
from app.core.enums import TEXT_RULE_TYPES, VISUAL_RULE_TYPES, Modality, RuleType


def test_dimension_de_embedding_es_indexable_por_pgvector():
    """pgvector no puede construir un índice HNSW sobre el tipo `vector` con más
    de 2000 dimensiones. Con las 3072 por defecto de Gemini el índice NO se crea
    y el fallo aparecería recién al usar el RAG, no al insertar."""
    assert settings.EMBEDDING_DIM <= 2000


def test_los_model_ids_de_gemini_no_llevan_el_prefijo_models():
    """El SDK google-genai espera 'gemini-3.5-flash', no 'models/gemini-3.5-flash'."""
    for model_id in (
        settings.GEMINI_TEXT_MODEL,
        settings.GEMINI_VISION_MODEL,
        settings.GEMINI_EMBEDDING_MODEL,
    ):
        assert not model_id.startswith("models/"), model_id


def test_el_proveedor_activo_resuelve_sus_tres_modelos():
    """Las propiedades de despacho deben devolver un id no vacío para el
    proveedor configurado; si no, el agente fallaría en tiempo de ejecución."""
    assert settings.text_model
    assert settings.vision_model
    assert settings.embedding_model
    assert settings.LLM_PROVIDER in ("openai", "gemini")


def test_cors_origins_se_parsea_y_no_deja_barra_final():
    """Un '/' sobrante rompe el match de origen en el middleware de CORS."""
    origenes = settings.cors_origins
    assert isinstance(origenes, list)
    assert all(not o.endswith("/") for o in origenes)


def test_los_dominios_de_filtrado_rag_son_disjuntos():
    """El pre-filtrado por dominio es lo que impide que una consulta visual
    devuelva reglas de léxico. Si los conjuntos se solaparan, esa garantía
    desaparecería."""
    solape = TEXT_RULE_TYPES & VISUAL_RULE_TYPES
    assert solape == set(), f"rule_types en ambos dominios: {solape}"


def test_todo_rule_type_pertenece_a_algun_dominio():
    """Un rule_type huérfano nunca sería recuperado por ningún módulo."""
    cubiertos = TEXT_RULE_TYPES | VISUAL_RULE_TYPES
    faltantes = set(RuleType) - cubiertos
    assert faltantes == set(), f"rule_types sin dominio: {faltantes}"


def test_modality_tiene_los_tres_valores_esperados():
    assert {m.value for m in Modality} == {"text", "visual", "both"}
