import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.enums import Modality, RuleType, Severity
from app.db.base import Base

chunk_modality_enum = PGEnum(
    Modality,
    name="chunk_modality",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)

chunk_rule_type_enum = PGEnum(
    RuleType,
    name="chunk_rule_type",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)

rule_severity_enum = PGEnum(
    Severity,
    name="rule_severity",
    create_type=False,
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class ManualChunk(Base):
    """Un fragmento semántico del manual, listo para RAG.

    La metadata (`modality`, `rule_type`, `severity`) NO es decorativa: es lo que
    permite el pre-filtrado SQL antes de la búsqueda vectorial. Sin ella, una
    consulta del Módulo III sobre el tamaño del logo puede devolver reglas de
    léxico. Ese pre-filtrado es la razón de ser del chunking semántico.
    """

    __tablename__ = "manual_chunks"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    manual_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brand_manuals.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[RuleType] = mapped_column(chunk_rule_type_enum, nullable=False)
    modality: Mapped[Modality] = mapped_column(chunk_modality_enum, nullable=False)
    severity: Mapped[Severity] = mapped_column(
        rule_severity_enum, nullable=False, default=Severity.soft
    )

    rule_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    channel_scope: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    heading: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: 1536 dims: por debajo del límite de 2000 que pgvector puede indexar con el
    #: tipo `vector`. Con las 3072 por defecto de Gemini el índice HNSW ni se crea.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.GEMINI_EMBEDDING_DIM), nullable=False
    )
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)

    extra_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    manual: Mapped["BrandManual"] = relationship(back_populates="chunks")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ManualChunk {self.section} [{self.modality.value}/{self.rule_type.value}]>"
