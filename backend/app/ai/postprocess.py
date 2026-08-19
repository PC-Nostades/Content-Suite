"""Post-proceso determinista del manual generado.

Nada de esto se le delega al LLM, y cada punto tiene una razón concreta:

- **Los `rule_id` los asigna el sistema.** Un id inventado por el modelo no es
  estable entre versiones, y el Módulo III necesita citar reglas de forma que
  sigan significando lo mismo cuando el manual se regenere.
- **Los hex se normalizan aquí.** El structured output de Gemini no soporta
  `pattern` de forma fiable, así que el formato se arregla después, no se pide.
- **El contraste se calcula, no se pregunta.** Un modelo puede afirmar que dos
  colores combinan bien; la aritmética WCAG dice si es cierto.

Devuelve un informe de lo que tocó, que se registra en Langfuse y sirve para
detectar degradación del prompt sin leer manuales enteros.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.ai.color import contrast_ratio, normalize_hex
from app.ai.schemas.brand_manual import BrandManual, ColorSpec, Rule
from app.core.enums import Modality, Severity

logger = logging.getLogger(__name__)

#: Por debajo de esto, un par de colores declarado como "combina bien" no es
#: legible para texto normal (WCAG AA).
MIN_CONTRAST_AA = 4.5


@dataclass
class PostProcessReport:
    rules_labeled: int = 0
    hex_normalized: int = 0
    hex_discarded: int = 0
    duplicate_terms_removed: int = 0
    low_contrast_pairs: list[str] = field(default_factory=list)
    inconsistent_headlines: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "rules_labeled": self.rules_labeled,
            "hex_normalized": self.hex_normalized,
            "hex_discarded": self.hex_discarded,
            "duplicate_terms_removed": self.duplicate_terms_removed,
            "low_contrast_pairs": self.low_contrast_pairs,
            "inconsistent_headlines": self.inconsistent_headlines,
        }


def slugify(text: str, max_length: int = 28) -> str:
    """Slug ASCII estable a partir de una frase en español."""
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    limpio = re.sub(r"[^a-zA-Z0-9]+", "_", sin_acentos).strip("_").lower()
    return limpio[:max_length].rstrip("_") or "regla"


def _assign_rule_ids(rules: list[Rule], domain: str, report: PostProcessReport) -> None:
    """Asigna ids `dominio.tipo.slug`, garantizando unicidad dentro del manual."""
    vistos: dict[str, int] = {}
    for rule in rules:
        base = f"{domain}.{rule.modality.value}.{slugify(rule.statement)}"
        if base in vistos:
            vistos[base] += 1
            rule.id = f"{base}_{vistos[base]}"
        else:
            vistos[base] = 0
            rule.id = base
        report.rules_labeled += 1


def _normalize_color(color: ColorSpec, report: PostProcessReport) -> bool:
    """Normaliza el hex in-place. Devuelve False si era irrecuperable."""
    normalizado = normalize_hex(color.hex)
    if normalizado is None:
        report.hex_discarded += 1
        logger.warning("Color descartado por hex inválido: %r (%s)", color.hex, color.name)
        return False
    if normalizado != color.hex:
        report.hex_normalized += 1
    color.hex = normalizado

    for campo in ("pairs_well_with", "never_pair_with"):
        originales = getattr(color, campo)
        validos = []
        for h in originales:
            n = normalize_hex(h)
            if n is None:
                report.hex_discarded += 1
            else:
                if n != h:
                    report.hex_normalized += 1
                validos.append(n)
        setattr(color, campo, validos)
    return True


def _dedupe_forbidden_terms(manual: BrandManual, report: PostProcessReport) -> None:
    """Deduplica por término en minúsculas, conservando la severidad más alta.

    Un término duplicado con severidades distintas es peor que un duplicado: el
    filtro del Módulo II aplicaría la que encuentre primero, de forma no determinista.
    """
    for atributo in ("forbidden_terms", "forbidden_claims"):
        originales = getattr(manual.verbal, atributo)
        por_termino: dict[str, object] = {}
        for term in originales:
            clave = term.term.strip().lower()
            existente = por_termino.get(clave)
            if existente is None:
                por_termino[clave] = term
            else:
                report.duplicate_terms_removed += 1
                if term.severity == Severity.hard:
                    por_termino[clave] = term
        setattr(manual.verbal, atributo, list(por_termino.values()))


def _check_declared_contrast(manual: BrandManual, report: PostProcessReport) -> None:
    """Verifica los pares que el modelo declaró como compatibles.

    Si un par no llega a AA, se anota. No se elimina: puede ser un par válido para
    bloques de color, solo no para texto encima. La decisión informada es mejor
    que el borrado silencioso.
    """
    for color in manual.visual.color_palette:
        for pareja in color.pairs_well_with:
            ratio = contrast_ratio(color.hex, pareja)
            if ratio is not None and ratio < MIN_CONTRAST_AA:
                report.low_contrast_pairs.append(f"{color.hex}/{pareja} ({ratio:.2f}:1)")


def _check_headline_coherence(manual: BrandManual, report: PostProcessReport) -> None:
    """¿El propio manual se contradice?

    Si un titular de ejemplo usa una palabra que el mismo manual prohíbe, el
    manual es incoherente — y ese es justo el fallo que el Módulo II heredaría.
    """
    prohibidos = {t.term.strip().lower() for t in manual.verbal.forbidden_terms if t.term.strip()}
    if not prohibidos:
        return

    for pilar in manual.verbal.messaging_pillars:
        for titular in pilar.sample_headlines:
            minuscula = titular.lower()
            for termino in prohibidos:
                if re.search(rf"\b{re.escape(termino)}\b", minuscula):
                    report.inconsistent_headlines.append(f"«{titular}» contiene «{termino}»")
                    break


def postprocess_manual(manual: BrandManual) -> PostProcessReport:
    """Aplica todo el post-proceso in-place y devuelve el informe."""
    report = PostProcessReport()

    # 1 · Ids estables por dominio
    _assign_rule_ids(manual.verbal.verbal_rules, "verbal", report)
    _assign_rule_ids(manual.visual.visual_rules, "visual", report)
    _assign_rule_ids(manual.compliance.restricted_claims, "compliance", report)

    # 2 · Normalización de color (descarta los irrecuperables)
    manual.visual.color_palette = [
        c for c in manual.visual.color_palette if _normalize_color(c, report)
    ]
    manual.visual.forbidden_colors = [
        c for c in manual.visual.forbidden_colors if _normalize_color(c, report)
    ]

    # 3 · Léxico sin duplicados
    _dedupe_forbidden_terms(manual, report)

    # 4 · Verificaciones que el modelo no puede hacer por sí mismo
    _check_declared_contrast(manual, report)
    _check_headline_coherence(manual, report)

    # 5 · Última red: ninguna regla visual puede quedar como 'text', o el
    #     Módulo III nunca la recuperaría (su filtro es modality IN ('visual','both')).
    for rule in manual.visual.visual_rules:
        if rule.modality == Modality.text:
            rule.modality = Modality.visual

    return report


def count_rules(manual: BrandManual) -> dict[str, int]:
    """Conteo para métricas y para las trazas de Langfuse."""
    visual = manual.visual.visual_rules
    return {
        "verbal": len(manual.verbal.verbal_rules),
        "visual": len(visual),
        "compliance": len(manual.compliance.restricted_claims),
        "visual_con_check_hint": sum(1 for r in visual if r.check_hint.strip()),
        "hard": sum(
            1
            for r in [*manual.verbal.verbal_rules, *visual, *manual.compliance.restricted_claims]
            if r.severity == Severity.hard
        ),
        "forbidden_terms": len(manual.verbal.forbidden_terms),
        "forbidden_claims": len(manual.verbal.forbidden_claims),
        "colores": len(manual.visual.color_palette),
    }
