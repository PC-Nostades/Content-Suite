"""Validación determinista del léxico prohibido.

**No usa LLM, y esa es la decisión importante.**

Un check de palabra prohibida necesita 100 % de recall. Ni la búsqueda semántica
ni un modelo lo garantizan: el RAG podría recuperar 8 de 15 términos, y un LLM
puede "olvidar" uno. Por eso el manual guarda cada término con su `match_mode`, y
aquí se ejecuta como código:

    exact  → \\bpalabra\\b     coincidencia exacta, respetando límites de palabra
    stem   → \\bpalabra\\w*    la raíz y sus derivados (adelgaz → adelgaza, adelgazante)
    regex  → el patrón tal cual

Elegir `exact` donde hacía falta `stem` deja pasar violaciones reales; por eso el
prompt de la Etapa B insiste en que el modelo elija bien el modo.

El RAG guía la generación; esto la verifica.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Violation:
    term: str
    matched: str
    replacement: str
    severity: str
    reason: str
    kind: str  # 'forbidden_term' | 'forbidden_claim'

    def as_dict(self) -> dict:
        return {
            "term": self.term,
            "matched": self.matched,
            "replacement": self.replacement,
            "severity": self.severity,
            "reason": self.reason,
            "kind": self.kind,
        }


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def _build_pattern(term: str, match_mode: str) -> re.Pattern | None:
    """Compila el patrón para un término. Devuelve `None` si es inválido.

    Se compara sin acentos y sin distinguir mayúsculas: 'Adelgazá' debe caer
    igual que 'adelgaza'.
    """
    limpio = _strip_accents(term.strip())
    if not limpio:
        return None

    try:
        if match_mode == "regex":
            return re.compile(limpio, re.IGNORECASE)
        if match_mode == "stem":
            # La raíz y cualquier sufijo: adelgaz → adelgaza, adelgazante, adelgazamiento
            return re.compile(rf"\b{re.escape(limpio)}\w*", re.IGNORECASE)
        # exact (por defecto): palabra completa, no subcadena.
        # Sin \b, "gratis" cazaría dentro de "gratisimo" y daría falsos positivos.
        return re.compile(rf"\b{re.escape(limpio)}\b", re.IGNORECASE)
    except re.error as exc:
        logger.warning("Patrón inválido para «%s» (%s): %s", term, match_mode, exc)
        return None


def find_violations(text: str, lexicon: dict) -> list[Violation]:
    """Busca términos y claims prohibidos en el texto.

    `lexicon` es lo que devuelve `get_hard_lexicon()`: la lista COMPLETA leída
    del JSONB, no una recuperación parcial por similitud.
    """
    if not text:
        return []

    normalizado = _strip_accents(text)
    violaciones: list[Violation] = []

    for clave, kind in (("forbidden_terms", "forbidden_term"), ("forbidden_claims", "forbidden_claim")):
        for entrada in lexicon.get(clave) or []:
            term = (entrada.get("term") or "").strip()
            if not term:
                continue
            patron = _build_pattern(term, entrada.get("match_mode") or "exact")
            if patron is None:
                continue
            encontrado = patron.search(normalizado)
            if encontrado:
                violaciones.append(
                    Violation(
                        term=term,
                        matched=encontrado.group(0),
                        replacement=entrada.get("replacement") or "",
                        severity=entrada.get("severity") or "soft",
                        reason=entrada.get("reason") or "",
                        kind=kind,
                    )
                )

    return violaciones


def blocking_violations(violations: list[Violation]) -> list[Violation]:
    """Solo las de severidad `hard`. Las `soft` se reportan pero no bloquean:
    si todo bloqueara, el ciclo de reparación no convergería nunca."""
    return [v for v in violations if v.severity == "hard"]


def format_feedback(violations: list[Violation]) -> str:
    """Instrucciones concretas para el nodo de reparación.

    Se le dice al modelo exactamente qué cambiar y por cuál término, no un
    genérico «revisa el léxico»: eso es lo que hace que la reparación converja
    en un intento.
    """
    lineas = ["Tu texto violó reglas del manual de marca. Corrígelas TODAS:"]
    for v in violations:
        lineas.append(
            f'- Encontrado «{v.matched}» (regla: «{v.term}»). '
            f'Reemplázalo por «{v.replacement}». Motivo: {v.reason}'
        )
    lineas.append("\nMantén el resto del texto y su intención. Devuelve el texto corregido completo.")
    return "\n".join(lineas)
