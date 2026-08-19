"""Modelos de los Módulos II y III.

Las tablas ya existían desde la migración `0004`: se crearon junto con las del
Módulo I para que añadir estos módulos no obligara a migrar datos existentes.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditVerdict, ContentStatus, ContentType
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _pg_enum(enum_cls, name: str):
    return PGEnum(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda e: [x.value for x in e],
    )


class ContentPiece(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Una pieza de contenido generada por el Módulo II."""

    __tablename__ = "content_pieces"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    manual_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brand_manuals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[ContentType] = mapped_column(_pg_enum(ContentType, "content_type"), nullable=False)
    channel: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    input_brief: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ContentStatus] = mapped_column(
        _pg_enum(ContentStatus, "content_status"), nullable=False, default=ContentStatus.draft
    )

    #: ⭐ Qué reglas del manual se recuperaron y aplicaron. Es lo que permite
    #: responder «¿por qué el texto dice esto?» con evidencia y no con una
    #: reconstrucción a posteriori.
    retrieved_rule_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )
    langfuse_trace_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class Approval(UUIDPrimaryKeyMixin, Base):
    """Una decisión de aprobación. Se guarda el historial completo, no solo el
    estado final: quién aprobó qué y cuándo es justamente lo que hace auditable
    un flujo de gobernanza."""

    __tablename__ = "approvals"

    content_piece_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_pieces.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(1), nullable=False)  # 'a' | 'b'
    approver_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # approved | rejected
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")

    from sqlalchemy import DateTime, func

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class VisualAudit(UUIDPrimaryKeyMixin, Base):
    """Resultado de una auditoría multimodal del Módulo III."""

    __tablename__ = "visual_audits"

    content_piece_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_pieces.id", ondelete="CASCADE"), nullable=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[AuditVerdict] = mapped_column(
        _pg_enum(AuditVerdict, "audit_verdict"), nullable=False
    )

    #: [{rule_id, verdict, evidence, confidence}] — cada hallazgo CITA la regla
    #: del manual que evaluó. Sin rule_id, la auditoría sería una opinión.
    findings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    checked_rule_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list
    )

    model: Mapped[str] = mapped_column(Text, nullable=False)
    langfuse_trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    from sqlalchemy import DateTime, func

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
