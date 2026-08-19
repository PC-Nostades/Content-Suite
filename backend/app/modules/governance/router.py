"""Endpoints del Módulo III — Gobernanza y auditoría multimodal.

Flujo de estados:  `pending_a` ──(Aprobador A)──► `pending_b` ──(Aprobador B)──► `approved`
                        └──────────────── rejected ◄────────────────┘

El RBAC lo aplica el backend: un Aprobador A que intente decidir en la etapa B
recibe 403 aunque el frontend le oculte el botón.
"""

import base64
import logging
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from app.core.deps import CurrentUser, DbSession, require_role
from app.core.enums import ContentStatus, UserRole
from app.core.exceptions import Conflict, Forbidden, NotFound
from app.db.models import Approval, Brand, ContentPiece, User, VisualAudit
from app.modules.governance.auditor import audit_image, model_label

logger = logging.getLogger(__name__)

router = APIRouter(tags=["governance"])

ApproverA = Annotated[User, Depends(require_role(UserRole.approver_a))]
ApproverB = Annotated[User, Depends(require_role(UserRole.approver_b))]

#: 8 MB. El free tier de Render tiene 512 MB de RAM y la imagen se carga entera
#: en memoria para enviarla al modelo.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIMES_PERMITIDOS = {"image/png", "image/jpeg", "image/webp"}


# ------------------------------------------------------------------ Schemas


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=1000)


class ApprovalOut(BaseModel):
    id: uuid.UUID
    stage: str
    decision: str
    comment: str
    approver_name: str
    created_at: datetime


class SubmissionOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    brand_name: str
    type: str
    channel: str
    status: str
    title: str
    body: str
    retrieved_rule_ids: list[str]
    fixed_violations: list[dict]
    remaining_violations: list[dict]
    created_by_name: str
    created_at: datetime
    approvals: list[ApprovalOut]


class FindingOut(BaseModel):
    rule_id: str
    rule_statement: str
    verdict: str
    evidence: str
    confidence: str


class AuditOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    content_piece_id: uuid.UUID | None
    verdict: str
    summary: str
    findings: list[FindingOut]
    checked_rule_ids: list[str]
    model: str
    latency_ms: int | None
    created_at: datetime


# --------------------------------------------------------- Bandeja y decisión


@router.get("/submissions", response_model=list[SubmissionOut], summary="Bandeja de aprobación")
async def list_submissions(
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
) -> list[SubmissionOut]:
    """Todos los roles ven la bandeja; lo que cambia es qué pueden hacer en ella."""
    stmt = select(ContentPiece).order_by(desc(ContentPiece.created_at)).limit(100)
    if status:
        stmt = stmt.where(ContentPiece.status == status)

    piezas = (await db.scalars(stmt)).all()
    if not piezas:
        return []

    ids = {p.id for p in piezas}
    marcas = {
        b.id: b.name
        for b in (await db.scalars(select(Brand).where(Brand.id.in_({p.brand_id for p in piezas})))).all()
    }
    decisiones = (
        await db.scalars(
            select(Approval).where(Approval.content_piece_id.in_(ids)).order_by(Approval.created_at)
        )
    ).all()
    usuarios = {
        u.id: u.full_name
        for u in (
            await db.scalars(
                select(User).where(
                    User.id.in_(
                        {p.created_by for p in piezas} | {d.approver_id for d in decisiones}
                    )
                )
            )
        ).all()
    }

    por_pieza: dict[uuid.UUID, list[ApprovalOut]] = {}
    for d in decisiones:
        por_pieza.setdefault(d.content_piece_id, []).append(
            ApprovalOut(
                id=d.id, stage=d.stage, decision=d.decision, comment=d.comment,
                approver_name=usuarios.get(d.approver_id, ""), created_at=d.created_at,  # type: ignore[arg-type]
            )
        )

    salida = []
    for p in piezas:
        out = p.output or {}
        salida.append(
            SubmissionOut(
                id=p.id,
                brand_id=p.brand_id,
                brand_name=marcas.get(p.brand_id, ""),
                type=p.type.value if hasattr(p.type, "value") else str(p.type),
                channel=p.channel,
                status=p.status.value if hasattr(p.status, "value") else str(p.status),
                title=out.get("title", ""),
                body=out.get("body", ""),
                retrieved_rule_ids=p.retrieved_rule_ids or [],
                fixed_violations=out.get("fixed_violations", []),
                remaining_violations=out.get("remaining_violations", []),
                created_by_name=usuarios.get(p.created_by, ""),
                created_at=p.created_at,
                approvals=por_pieza.get(p.id, []),
            )
        )
    return salida


@router.post(
    "/submissions/{piece_id}/decision",
    response_model=SubmissionOut,
    summary="Aprobar o rechazar (Aprobador A — texto)",
)
async def decide(
    piece_id: uuid.UUID, payload: DecisionRequest, db: DbSession, user: ApproverA
) -> SubmissionOut:
    """El Aprobador A revisa el TEXTO. Si aprueba, pasa a auditoría visual.

    El estado se valida en el servidor: no se puede aprobar dos veces ni saltarse
    la etapa A. El frontend oculta el botón, pero eso es UX, no control.
    """
    pieza = await db.get(ContentPiece, piece_id)
    if pieza is None:
        raise NotFound("La pieza de contenido no existe.")
    if pieza.status != ContentStatus.pending_a:
        raise Conflict(
            f"Esta pieza está en estado «{pieza.status.value}» y no admite revisión de texto."
        )

    db.add(
        Approval(
            content_piece_id=pieza.id,
            stage="a",
            approver_id=user.id,
            decision=payload.decision,
            comment=payload.comment,
        )
    )
    pieza.status = (
        ContentStatus.pending_b if payload.decision == "approved" else ContentStatus.rejected
    )
    await db.commit()

    resultados = await list_submissions(db, user)  # type: ignore[arg-type]
    encontrada = next((s for s in resultados if s.id == piece_id), None)
    if encontrada is None:
        raise NotFound("La pieza desapareció tras la decisión.")
    return encontrada


@router.post(
    "/submissions/{piece_id}/visual-decision",
    response_model=SubmissionOut,
    summary="Aprobar o rechazar (Aprobador B — visual)",
)
async def decide_visual(
    piece_id: uuid.UUID, payload: DecisionRequest, db: DbSession, user: ApproverB
) -> SubmissionOut:
    pieza = await db.get(ContentPiece, piece_id)
    if pieza is None:
        raise NotFound("La pieza de contenido no existe.")
    if pieza.status != ContentStatus.pending_b:
        raise Conflict(
            f"Esta pieza está en «{pieza.status.value}»: aún no pasó la revisión de texto."
        )

    db.add(
        Approval(
            content_piece_id=pieza.id,
            stage="b",
            approver_id=user.id,
            decision=payload.decision,
            comment=payload.comment,
        )
    )
    pieza.status = (
        ContentStatus.approved if payload.decision == "approved" else ContentStatus.rejected
    )
    await db.commit()

    resultados = await list_submissions(db, user)  # type: ignore[arg-type]
    encontrada = next((s for s in resultados if s.id == piece_id), None)
    if encontrada is None:
        raise NotFound("La pieza desapareció tras la decisión.")
    return encontrada


# ------------------------------------------------------- Auditoría multimodal


@router.post("/audit/image", response_model=AuditOut, summary="Auditar imagen contra el manual")
async def audit(
    db: DbSession,
    user: ApproverB,
    brand_id: Annotated[uuid.UUID, Form()],
    file: Annotated[UploadFile, File()],
    content_piece_id: Annotated[uuid.UUID | None, Form()] = None,
    focus: Annotated[str, Form()] = "",
) -> AuditOut:
    """⭐ El corazón del Módulo III.

    Recupera SOLO reglas visuales (pre-filtrado `modality=visual`), se las pasa al
    modelo de visión junto con la imagen, y devuelve hallazgos que **citan el
    `rule_id`** del manual. Esa cita es lo que separa una auditoría de una opinión.
    """
    if file.content_type not in MIMES_PERMITIDOS:
        raise Conflict(
            f"Formato no soportado ({file.content_type}). Usa PNG, JPEG o WebP."
        )

    contenido = await file.read()
    if len(contenido) > MAX_IMAGE_BYTES:
        raise Conflict(
            f"La imagen pesa {len(contenido) // 1024} KB; el máximo es "
            f"{MAX_IMAGE_BYTES // 1024} KB."
        )
    if not contenido:
        raise Conflict("El archivo está vacío.")

    brand = await db.get(Brand, brand_id)
    if brand is None:
        raise NotFound("La marca no existe.")

    trace_id = None
    try:
        from langfuse import get_client

        lf = get_client()
        with lf.start_as_current_span(name="visual_audit") as span:
            trace_id = lf.get_current_trace_id()
            resultado, rule_ids, latencia = await audit_image(
                db, brand_id=brand_id, image_bytes=contenido,
                mime_type=file.content_type or "image/png", focus=focus,
            )
            span.update(
                output={
                    "verdict": resultado.verdict,
                    "findings": len(resultado.findings),
                    "rules_checked": len(rule_ids),
                },
                metadata={"latency_ms": latencia},
            )
    except ImportError:
        resultado, rule_ids, latencia = await audit_image(
            db, brand_id=brand_id, image_bytes=contenido,
            mime_type=file.content_type or "image/png", focus=focus,
        )

    # La imagen se guarda embebida como data URI. En producción iría a Supabase
    # Storage; para la evaluación evita depender de un bucket más.
    data_uri = f"data:{file.content_type};base64,{base64.b64encode(contenido).decode()}"

    auditoria = VisualAudit(
        content_piece_id=content_piece_id,
        brand_id=brand_id,
        image_url=data_uri,
        verdict=resultado.verdict,
        findings=[f.model_dump() for f in resultado.findings],
        checked_rule_ids=rule_ids,
        model=model_label(),
        langfuse_trace_id=trace_id,
        latency_ms=latencia,
        created_by=user.id,
    )
    db.add(auditoria)
    await db.commit()
    await db.refresh(auditoria)

    return AuditOut(
        id=auditoria.id,
        brand_id=brand_id,
        content_piece_id=content_piece_id,
        verdict=resultado.verdict,
        summary=resultado.summary,
        findings=[FindingOut(**f.model_dump()) for f in resultado.findings],
        checked_rule_ids=rule_ids,
        model=auditoria.model,
        latency_ms=latencia,
        created_at=auditoria.created_at,  # type: ignore[arg-type]
    )


@router.get("/audits", response_model=list[AuditOut], summary="Auditorías realizadas")
async def list_audits(
    db: DbSession, user: CurrentUser, brand_id: uuid.UUID | None = None
) -> list[AuditOut]:
    stmt = select(VisualAudit).order_by(desc(VisualAudit.created_at)).limit(50)
    if brand_id:
        stmt = stmt.where(VisualAudit.brand_id == brand_id)

    return [
        AuditOut(
            id=a.id,
            brand_id=a.brand_id,
            content_piece_id=a.content_piece_id,
            verdict=a.verdict.value if hasattr(a.verdict, "value") else str(a.verdict),
            summary="",
            findings=[FindingOut(**f) for f in (a.findings or [])],
            checked_rule_ids=a.checked_rule_ids or [],
            model=a.model,
            latency_ms=a.latency_ms,
            created_at=a.created_at,  # type: ignore[arg-type]
        )
        for a in (await db.scalars(stmt)).all()
    ]
