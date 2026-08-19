"""Chunking semántico: la garantía de la que depende el pre-filtrado del RAG.

Todos estos tests corren SIN red, contra el fixture escrito a mano. El free tier
de Gemini permite 20 peticiones al día por modelo: si el desarrollo del chunking
dependiera de generar manuales, sería inviable iterar.
"""

import json
from pathlib import Path

import pytest

from app.ai.chunking import MAX_CHUNK_CHARS, chunk_manual
from app.ai.schemas.brand_manual import BrandManual
from app.core.enums import TEXT_RULE_TYPES, VISUAL_RULE_TYPES, Modality, RuleType

FIXTURE = Path(__file__).parent / "fixtures" / "manual_quinua.json"


@pytest.fixture(scope="module")
def manual() -> BrandManual:
    return BrandManual.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def chunks(manual):
    return chunk_manual(manual)


def test_cantidad_de_chunks_en_el_rango_esperado(chunks):
    """Muy pocos = secciones fusionadas y metadata inútil.
    Demasiados = fragmentación que rompe unidades de significado."""
    assert 18 <= len(chunks) <= 32, f"se generaron {len(chunks)} chunks"


def test_indices_densos_y_correlativos(chunks):
    """`(manual_id, chunk_index)` es clave única en la BD: un hueco o un duplicado
    haría fallar el indexado transaccional."""
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_ninguna_seccion_supera_el_maximo(chunks):
    for c in chunks:
        assert len(c.content) <= MAX_CHUNK_CHARS + 400, f"{c.section} mide {len(c.content)}"


def test_todo_chunk_lleva_breadcrumb_embebido(chunks):
    """El breadcrumb va DENTRO del texto que se embebe (contextual retrieval):
    mejora el recall porque el vector sabe de qué sección viene."""
    for c in chunks:
        assert c.content.startswith("[MARCA:"), c.section
        assert "[MODALIDAD:" in c.content
        assert "[TIPO:" in c.content


# ---------------------------------------------------------------------------
# La garantía central: separación de dominios
# ---------------------------------------------------------------------------


def test_los_chunks_visuales_no_contienen_reglas_de_lexico(chunks):
    """Si esto se rompe, el Módulo III recuperaría términos prohibidos al
    auditar una imagen — el fallo exacto que el chunking semántico evita."""
    visuales = [c for c in chunks if c.modality == Modality.visual]
    assert visuales, "no se generó ningún chunk visual"
    for c in visuales:
        assert c.rule_type in VISUAL_RULE_TYPES, f"{c.section} → {c.rule_type}"


def test_los_chunks_de_texto_no_contienen_reglas_visuales(chunks):
    de_texto = [c for c in chunks if c.modality == Modality.text]
    assert de_texto
    for c in de_texto:
        assert c.rule_type in TEXT_RULE_TYPES, f"{c.section} → {c.rule_type}"


def test_el_filtro_del_modulo_iii_recupera_las_reglas_del_logo(chunks):
    """Simula el pre-filtro del Módulo III y comprueba que el tamaño mínimo del
    logo está dentro del subconjunto recuperable."""
    candidatos = [
        c for c in chunks
        if c.modality in (Modality.visual, Modality.both)
        and c.rule_type in VISUAL_RULE_TYPES
    ]
    texto = "\n".join(c.content for c in candidatos)
    assert "% del ancho de la pieza" in texto
    assert "zona de resguardo" in texto.lower()


def test_el_filtro_del_modulo_ii_recupera_el_lexico_prohibido(chunks):
    candidatos = [
        c for c in chunks
        if c.modality in (Modality.text, Modality.both)
        and c.rule_type in TEXT_RULE_TYPES
    ]
    texto = "\n".join(c.content for c in candidatos)
    assert "LÉXICO PROHIBIDO" in texto
    assert "light" in texto


def test_el_filtro_visual_excluye_el_lexico(chunks):
    """La comprobación inversa, y la más importante: una consulta visual NO debe
    poder alcanzar el chunk de léxico prohibido."""
    visuales = [
        c for c in chunks
        if c.modality in (Modality.visual, Modality.both)
        and c.rule_type in VISUAL_RULE_TYPES
    ]
    secciones = {c.section for c in visuales}
    assert "identidad_verbal.lexico_prohibido" not in secciones


# ---------------------------------------------------------------------------
# Integridad de las listas y de las reglas
# ---------------------------------------------------------------------------


def test_el_lexico_prohibido_llega_completo(manual, chunks):
    """Un check de palabra prohibida necesita 100 % de recall: si el chunking
    parte la lista, el Módulo II dejaría pasar violaciones reales."""
    lexico = [c for c in chunks if c.section == "identidad_verbal.lexico_prohibido"]
    texto = "\n".join(c.content for c in lexico)
    for termino in manual.verbal.forbidden_terms:
        assert termino.term in texto, f"se perdió el término prohibido «{termino.term}»"


def test_cada_termino_prohibido_conserva_su_reemplazo_y_match_mode(chunks):
    """Recuperar 'no digas light' sin el reemplazo ni el modo de coincidencia
    deja al Módulo II sin poder actuar."""
    lexico = "\n".join(
        c.content for c in chunks if c.section == "identidad_verbal.lexico_prohibido"
    )
    assert "match=" in lexico
    assert "→ usar" in lexico


def test_las_reglas_conservan_su_check_hint(chunks):
    """Sin `check_hint` en el texto recuperado, el modelo de visión sabe qué
    exige la regla pero no cómo comprobarla."""
    reglas = [c for c in chunks if c.section == "identidad_visual.reglas"]
    assert reglas
    texto = "\n".join(c.content for c in reglas)
    assert texto.count("Verificación:") >= 10


def test_los_chunks_de_reglas_exponen_sus_rule_ids(manual, chunks):
    """El Módulo III cita `rule_id` en cada hallazgo: sin esta trazabilidad la
    auditoría sería una opinión."""
    reglas_visuales = next(c for c in chunks if c.section == "identidad_visual.reglas")
    assert len(reglas_visuales.rule_ids) == len(manual.visual.visual_rules)
    assert all(rid for rid in reglas_visuales.rule_ids)


def test_la_paleta_conserva_hex_y_su_restriccion_juntos(chunks):
    """Un corte que separase el hex de su restricción de uso haría que el
    Módulo III auditase con información incompleta."""
    paleta = next(c for c in chunks if c.section == "identidad_visual.paleta")
    assert "#E8552D" in paleta.content
    assert "NUNCA combinar con" in paleta.content
    assert "Área máxima" in paleta.content


def test_las_secciones_esperadas_estan_todas(chunks):
    secciones = {c.section for c in chunks}
    esperadas = {
        "estrategia.posicionamiento",
        "estrategia.personalidad",
        "identidad_verbal.tono",
        "identidad_verbal.espectro_voz",
        "identidad_verbal.lexico_preferido",
        "identidad_verbal.lexico_prohibido",
        "identidad_verbal.claims_prohibidos",
        "identidad_verbal.gramatica_estilo",
        "identidad_verbal.pilares",
        "identidad_verbal.reglas",
        "identidad_visual.paleta",
        "identidad_visual.tipografia",
        "identidad_visual.logo",
        "identidad_visual.fotografia",
        "identidad_visual.composicion",
        "identidad_visual.iconografia",
        "identidad_visual.packaging",
        "identidad_visual.reglas",
        "cumplimiento",
    }
    faltantes = esperadas - secciones
    assert not faltantes, f"secciones ausentes: {faltantes}"


def test_las_guias_de_canal_generan_un_chunk_por_canal(manual, chunks):
    canales = [c for c in chunks if c.section.startswith("identidad_verbal.canal.")]
    assert len(canales) == len(manual.verbal.channel_guidelines)
    for c in canales:
        assert c.rule_type == RuleType.channel
        assert c.channel_scope, "el chunk de canal debe declarar su channel_scope"


def test_las_listas_largas_se_parten_por_items_completos():
    """Un término prohibido cortado a la mitad es peor que no tenerlo."""
    from app.ai.chunking import _split_items

    items = [f"- término_{i} con una descripción razonablemente larga" for i in range(200)]
    bloques = _split_items(items, "CABECERA\n\n", 1000)

    assert len(bloques) > 1, "la lista debería haberse partido"
    for bloque in bloques:
        assert bloque.startswith("CABECERA"), "cada bloque repite el encabezado"
    # Ningún ítem puede aparecer partido: todos deben estar íntegros en algún bloque.
    unido = "\n".join(bloques)
    for item in items:
        assert item in unido
