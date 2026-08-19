"""Modelos SQLAlchemy.

Se importan todos aquí para que las relaciones por string (`"BrandManual"`,
`"ManualChunk"`) se resuelvan sin importar en qué orden se cargue cada módulo.
"""

from app.db.models.brand import Brand
from app.db.models.brand_manual import BrandManual
from app.db.models.governance import Approval, ContentPiece, VisualAudit
from app.db.models.manual_chunk import ManualChunk
from app.db.models.user import User

__all__ = [
    "Approval",
    "Brand",
    "BrandManual",
    "ContentPiece",
    "ManualChunk",
    "User",
    "VisualAudit",
]
