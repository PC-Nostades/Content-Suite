"""Router raíz de la API v1.

Añadir un módulo nuevo (II o III) es una línea aquí y una carpeta en `app/modules/`.
Ese es todo el acoplamiento que existe entre módulos.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.modules.auth.router import router as auth_router
from app.modules.brand_dna.router import router as brand_dna_router
from app.modules.creative.router import router as creative_router
from app.modules.governance.router import router as governance_router

api_router = APIRouter(prefix=settings.API_V1_PREFIX)

api_router.include_router(auth_router)

# Módulo I — Brand DNA Architect
api_router.include_router(brand_dna_router)

# Módulo II — Creative Engine
api_router.include_router(creative_router)

# Módulo III — Governance & Multimodal Audit
api_router.include_router(governance_router)

