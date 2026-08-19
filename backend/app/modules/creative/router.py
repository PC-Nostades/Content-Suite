"""Endpoints del Módulo II — Creative Engine."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, DbSession, require_role
from app.core.enums import ManualStatus, UserRole
from app.core.exceptions import Conflict, NotFound
from app.db.models import Brand, ContentPiece, User
from app.modules.creative.graph import run_creative
from app.modules.creative.schemas import ContentGenerateRequest, ContentOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["creative"])

CreatorOnly = Annotated[User, Depends(require_role(UserRole.creator))]


def _to_out(pieza: ContentPiece, brand_name: str, autor: str) -> ContentOut:
    salida = pieza.output or {}
    return ContentOut(
        id=pieza.id,
        brand_id=pieza.brand_id,
        brand_name=brand_name,
        type=pieza.type.value if hasattr(pieza.type, "value") else pieza.type,
        channel=pieza.channel,
        status=pieza.status.value if hasattr(pieza.status, "value") else pieza.status,
        brief=(pieza.input_brief or {}).get("brief", ""),
        title=salida.get("title", ""),
        body=salida.get("body", ""),
        rationale=salida.get("rationale", ""),
        retrieved_rule_ids=pieza.retrieved_rule_ids or [],
        fixed_violations=salida.get("fixed_violations", []),
        remaining_violations=salida.get("remaining_violations", []),
        repair_attempts=salida.get("repair_attempts", 0),
        langfuse_trace_id=pieza.langfuse_trace_id,
        created_by_name=autor,
        created_at=pieza.created_at,
    )


@router.post("", response_model=ContentOut, summary="Generar contenido guiado por el manual")
async def generate_content(
    payload: ContentGenerateRequest, db: DbSession, user: CreatorOnly
) -> ContentOut:
    """Ejecuta el grafo `retrieve → generate → validate → (repair)`.

    A diferencia del Módulo I no se usa 202 + polling: la generación de una pieza
    tarda ~10-20 s, dentro de lo que un usuario espera con un botón en estado de
    carga. Reservar el patrón asíncrono para lo que de verdad tarda un minuto
    mantiene la UI simple donde puede serlo.
    """
    brand = await db.scalar(
        select(Brand).where(Brand.id == payload.brand_id).options(selectinload(Brand.manuals))
    )
    if brand is None:
        raise NotFound("La marca no existe.")

    publicado = next(
        (m for m in brand.manuals if m.status == ManualStatus.published), None
    )
    if publicado is None:
        raise Conflict(
            "Esta marca aún no tiene un manual publicado. "
            "El Creative Engine necesita el manual como fuente de verdad."
        )

    trace_id = None
    try:
        from langfuse import get_client

        lf = get_client()
        with lf.start_as_current_span(name="creative.generate") as span:
            trace_id = lf.get_current_trace_id()
            span.update(input={"type": payload.type, "brief": payload.brief})
            resultado = await run_creative(
                db,
                brand_id=payload.brand_id,
                content_type=payload.type,
                channel=payload.channel,
                brief=payload.brief,
            )
            span.update(
                output={
                    "rules_used": len(resultado["retrieved_rule_ids"]),
                    "violations_fixed": len(resultado["fixed_violations"]),
                    "repair_attempts": resultado["repair_attempts"],
                }
            )
    except ImportError:
        resultado = await run_creative(
            db,
            brand_id=payload.brand_id,
            content_type=payload.type,
            channel=payload.channel,
            brief=payload.brief,
        )

    pieza = ContentPiece(
        brand_id=brand.id,
        manual_id=publicado.id,
        type=payload.type,
        channel=payload.channel,
        input_brief={"brief": payload.brief},
        output={
            "title": resultado["title"],
            "body": resultado["body"],
            "rationale": resultado["rationale"],
            "fixed_violations": resultado["fixed_violations"],
            "remaining_violations": resultado["remaining_violations"],
            "repair_attempts": resultado["repair_attempts"],
        },
        # Nace pendiente del Aprobador A: el flujo de gobernanza empieza aquí.
        status="pending_a",
        retrieved_rule_ids=resultado["retrieved_rule_ids"],
        langfuse_trace_id=trace_id,
        created_by=user.id,
    )
    db.add(pieza)
    await db.commit()
    await db.refresh(pieza)

    return _to_out(pieza, brand.name, user.full_name)


@router.get("", response_model=list[ContentOut], summary="Listar contenido generado")
async def list_content(
    db: DbSession,
    user: CurrentUser,
    brand_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ContentOut]:
    stmt = (
        select(ContentPiece).order_by(desc(ContentPiece.created_at)).limit(limit)
    )
    if brand_id:
        stmt = stmt.where(ContentPiece.brand_id == brand_id)

    piezas = (await db.scalars(stmt)).all()
    if not piezas:
        return []

    marcas = {
        b.id: b.name
        for b in (
            await db.scalars(select(Brand).where(Brand.id.in_({p.brand_id for p in piezas})))
        ).all()
    }
    autores = {
        u.id: u.full_name
        for u in (
            await db.scalars(select(User).where(User.id.in_({p.created_by for p in piezas})))
        ).all()
    }
    return [
        _to_out(p, marcas.get(p.brand_id, ""), autores.get(p.created_by, "")) for p in piezas
    ]
