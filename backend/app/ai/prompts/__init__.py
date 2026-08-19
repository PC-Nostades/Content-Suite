"""Prompts de sistema del agente Brand DNA Architect.

Se versionan con `PROMPT_VERSION` y ese valor se persiste en `brand_manuals.prompt_version`:
sin eso, al comparar dos manuales generados con semanas de diferencia no se sabría
si la diferencia viene del modelo, del brief o de un cambio de prompt.

Todos siguen la misma plantilla:
    rol experto → tarea → REGLA INNEGOCIABLE → reglas de contenido → formato
"""

from app.ai.prompts.compliance import COMPLIANCE_SYSTEM
from app.ai.prompts.strategy import STRATEGY_SYSTEM
from app.ai.prompts.verbal import VERBAL_SYSTEM
from app.ai.prompts.visual import VISUAL_SYSTEM

PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPTS: dict[str, str] = {
    "strategy": STRATEGY_SYSTEM,
    "verbal": VERBAL_SYSTEM,
    "visual": VISUAL_SYSTEM,
    "compliance": COMPLIANCE_SYSTEM,
}

__all__ = [
    "COMPLIANCE_SYSTEM",
    "PROMPT_VERSION",
    "STRATEGY_SYSTEM",
    "SYSTEM_PROMPTS",
    "VERBAL_SYSTEM",
    "VISUAL_SYSTEM",
]
