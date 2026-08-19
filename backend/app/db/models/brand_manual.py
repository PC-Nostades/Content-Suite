import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import GenerationStage, ManualStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

manual_status_enum = PGEnum(
    ManualStatus,
    name="manual_status",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)

generation_stage_enum = PGEnum(
    GenerationStage,
    name="generation_stage",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class BrandManual(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Una versión del Manual de Marca.

    `content` es el `BrandManual` de Pydantic serializado a JSONB. Se guarda entero
    además de chunkeado porque las reglas DURAS (léxico prohibido, claims) se
    consultan por SQL directo, no por similitud vectorial: un check de palabra
    prohibida necesita 100% de recall y la búsqueda semántica no lo garantiza.
    """

    __tablename__ = "brand_manuals"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ManualStatus] = mapped_column(
        manual_status_enum, nullable=False, default=ManualStatus.generating
    )
    stage: Mapped[GenerationStage] = mapped_column(
        generation_stage_enum, nullable=False, default=GenerationStage.queued
    )

    content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")

    # Trazabilidad: qué modelo y qué versión de prompt produjeron esto, y el enlace
    # directo a la traza de Langfuse. Se devuelve por la API para poder saltar a ella.
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    generation_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    #: `timezone=True` es obligatorio: la columna real es `timestamptz` y sin esto
    #: SQLAlchemy la mapea a TIMESTAMP WITHOUT TIME ZONE, y asyncpg rechaza un
    #: datetime con tzinfo ("can't subtract offset-naive and offset-aware").
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    brand: Mapped["Brand"] = relationship(back_populates="manuals")  # noqa: F821
    chunks: Mapped[list["ManualChunk"]] = relationship(  # noqa: F821
        back_populates="manual", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BrandManual brand={self.brand_id} v{self.version} {self.status.value}>"
