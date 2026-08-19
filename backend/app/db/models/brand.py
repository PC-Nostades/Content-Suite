import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Brand(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Una marca. `brief` guarda los parámetros cortos que escribió el usuario.

    Se conserva el brief crudo (y no solo el manual generado) porque es la entrada
    del agente: permite regenerar una versión nueva y, sobre todo, mostrar en la UI
    de qué semilla salió cada manual.
    """

    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    market: Mapped[str] = mapped_column(String(80), nullable=False, default="PE")
    brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    manuals: Mapped[list["BrandManual"]] = relationship(  # noqa: F821
        back_populates="brand",
        cascade="all, delete-orphan",
        order_by="desc(BrandManual.version)",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Brand {self.slug}>"
