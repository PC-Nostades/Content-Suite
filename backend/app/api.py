"""Router raíz de la API v1.

Añadir un módulo nuevo (II o III) es una línea aquí y una carpeta en `app/modules/`.
Ese es todo el acoplamiento que existe entre módulos.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.modules.auth.router import router as auth_router

api_router = APIRouter(prefix=settings.API_V1_PREFIX)

api_router.include_router(auth_router)

# Módulo I — Brand DNA Architect
# from app.modules.brand_dna.router import router as brand_dna_router
# api_router.include_router(brand_dna_router)

# Módulo II — Creative Engine   (pendiente)
# Módulo III — Governance       (pendiente)
