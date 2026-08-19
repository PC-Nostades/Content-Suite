"""Endpoints del Módulo I — Brand DNA Architect."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload

from app.ai.retrieval import get_hard_lexicon, retrieve_rules
from app.core.deps import CurrentUser, DbSession, require_role
from app.core.enums import ManualStatus, Modality, RuleType, Severity, UserRole
from app.core.exceptions import Forbidden, NotFound
from app.db.models import Brand, BrandManual, ManualChunk, User
from app.modules.brand_dna import service
from app.modules.brand_dna.schemas import (
    BrandCreate,
    BrandDetail,
    BrandListItem,
    BrandStatus,
    ChunkOut,
    HardRulesResponse,
    RagResult,
    RagSearchRequest,
    RagSearchResponse,
)

router = APIRouter(tags=["brand-dna"])

CreatorOnly = Annotated[User, Depends(require_role(UserRole.creator))]


async def _get_brand(db, brand_id: uuid.UUID) -> Brand:
    brand = await db.scalar(
        select(Brand).where(Brand.id == brand_id).options(selectinload(Brand.manuals))
    )
    if brand is None:
        raise NotFound("La marca no existe.")
    return brand


def _latest(brand: Brand) -> BrandManual | None:
    """El manual publicado si existe; si no, el de versión más alta."""
    if not brand.manuals:
        return None
    publicado = next((m for m in brand.manuals if m.status == ManualStatus.published), None)
    return publicado or max(brand.manuals, key=lambda m: m.version)


# ============================================================== Marcas


@router.post(
    "/brands",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BrandStatus,
    summary="Crear marca y generar su manual",
)
async def create_brand(
    payload: BrandCreate,
    db: DbSession,
    user: CreatorOnly,
    background: BackgroundTasks,
) -> BrandStatus:
    """Devuelve **202** de inmediato y genera en segundo plano.

    La generación tarda ~60 s. Con `await` la petición no sobreviviría a un
    refresh del navegador y el peor caso sería *cold start + generación* en un
    solo request HTTP. El frontend hace polling a `/brands/{id}/status`.
    """
    brief = payload.brief.model_dump(mode="json")
    brand, manual = await service.create_brand_and_queue(db, brief=brief, user=user)

    background.add_task(service.generate_and_index, manual.id, brand.id)

    return BrandStatus(
        id=brand.id,
        manual_status=manual.status,
        generation_stage=manual.stage,
        manual_id=manual.id,
        error_message=None,
        elapsed_ms=0,
    )


@router.get("/brands", response_model=list[BrandListItem], summary="Listar marcas")
async def list_brands(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BrandListItem]:
    """Todos los roles ven todas las marcas.

    Los aprobadores necesitan leer el manual para poder juzgar: en el Módulo III,
    el Aprobador A evalúa si un texto respeta el léxico y el B si una imagen
    respeta la paleta. La restricción va sobre las mutaciones, no sobre la lectura.
    """
    stmt = (
        select(Brand)
        .options(selectinload(Brand.manuals))
        .order_by(desc(Brand.created_at))
        .limit(limit)
    )
    if q:
        stmt = stmt.where(Brand.name.ilike(f"%{q}%"))

    brands = (await db.scalars(stmt)).all()
    owners = {
        u.id: u.full_name
        for u in (
            await db.scalars(select(User).where(User.id.in_([b.owner_id for b in brands])))
        ).all()
    } if brands else {}

    salida = []
    for b in brands:
        m = _latest(b)
        salida.append(
            BrandListItem(
                id=b.id,
                brand_name=b.name,
                product_category=b.category,
                market=b.market,
                manual_status=m.status if m else None,
                generation_stage=m.stage if m else None,
                manual_id=m.id if m else None,
                primary_color_hex=service.primary_color(m.content if m else None),
                created_by_name=owners.get(b.owner_id, ""),
                created_at=b.created_at,
            )
        )
    return salida


@router.get("/brands/{brand_id}", response_model=BrandDetail, summary="Detalle de marca")
async def get_brand(brand_id: uuid.UUID, db: DbSession, user: CurrentUser) -> BrandDetail:
    brand = await _get_brand(db, brand_id)
    m = _latest(brand)
    owner = await db.get(User, brand.owner_id)

    n_chunks = 0
    if m is not None:
        n_chunks = (
            await db.scalar(
                select(func.count()).select_from(ManualChunk).where(ManualChunk.manual_id == m.id)
            )
        ) or 0

    return BrandDetail(
        id=brand.id,
        brief=brand.brief,
        manual_status=m.status if m else None,
        generation_stage=m.stage if m else None,
        manual_id=m.id if m else None,
        error_message=m.error if m else None,
        version=m.version if m else None,
        model=m.model if m else None,
        generation_ms=m.generation_ms if m else None,
        langfuse_trace_id=m.langfuse_trace_id if m else None,
        created_by_name=owner.full_name if owner else "",
        created_at=brand.created_at,
        # Solo se envía el manual cuando está listo: mientras genera, la UI
        # muestra el stepper de progreso, no un objeto a medias.
        manual=m.content if (m and m.status in (ManualStatus.published, ManualStatus.ready)) else None,
        stats=service.manual_stats(m.content if m else None, n_chunks),  # type: ignore[arg-type]
    )


@router.get(
    "/brands/{brand_id}/status",
    response_model=BrandStatus,
    summary="Estado de generación (polling)",
)
async def get_brand_status(
    brand_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> BrandStatus:
    """Payload mínimo, pensado para pedirse cada 2,5 s sin coste apreciable."""
    brand = await _get_brand(db, brand_id)
    m = _latest(brand)
    if m is None:
        raise NotFound("La marca no tiene ningún manual.")

    from datetime import UTC, datetime

    elapsed = int((datetime.now(UTC) - m.created_at).total_seconds() * 1000)
    return BrandStatus(
        id=brand.id,
        manual_status=m.status,
        generation_stage=m.stage,
        manual_id=m.id,
        error_message=m.error,
        elapsed_ms=elapsed,
    )


@router.post(
    "/brands/{brand_id}/regenerate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=BrandStatus,
    summary="Regenerar el manual (nueva versión)",
)
async def regenerate(
    brand_id: uuid.UUID, db: DbSession, user: CreatorOnly, background: BackgroundTasks
) -> BrandStatus:
    brand = await _get_brand(db, brand_id)
    if brand.owner_id != user.id and user.role != UserRole.admin:
        raise Forbidden("Solo el propietario de la marca puede regenerar su manual.")

    manual = await service.queue_regeneration(db, brand=brand, user=user)
    background.add_task(service.generate_and_index, manual.id, brand.id)

    return BrandStatus(
        id=brand.id,
        manual_status=manual.status,
        generation_stage=manual.stage,
        manual_id=manual.id,
        error_message=None,
        elapsed_ms=0,
    )


# ============================================================== Chunks / RAG


@router.get(
    "/manuals/{manual_id}/chunks",
    response_model=list[ChunkOut],
    summary="Chunks indexados de un manual",
)
async def list_chunks(
    manual_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    modality: Modality | None = None,
    rule_type: RuleType | None = None,
) -> list[ChunkOut]:
    """Hace visible el chunking semántico y su metadata. Nunca expone el embedding."""
    stmt = (
        select(ManualChunk)
        .where(ManualChunk.manual_id == manual_id)
        .order_by(ManualChunk.chunk_index)
    )
    if modality:
        stmt = stmt.where(ManualChunk.modality == modality)
    if rule_type:
        stmt = stmt.where(ManualChunk.rule_type == rule_type)
    return [ChunkOut.model_validate(c) for c in (await db.scalars(stmt)).all()]


@router.post(
    "/rag/search", response_model=RagSearchResponse, summary="Búsqueda híbrida en el manual"
)
async def rag_search(
    payload: RagSearchRequest, db: DbSession, user: CurrentUser
) -> RagSearchResponse:
    """⭐ El contrato que consumen los Módulos II y III.

    El filtro SQL por `modality`/`rule_type` da precisión y el vector da recall
    dentro del dominio correcto. Con `modality=visual` esta llamada **nunca**
    devuelve reglas de léxico, que es la garantía que hace posible una auditoría
    de imagen fiable.
    """
    chunks, latencia = await retrieve_rules(
        db,
        brand_id=payload.brand_id,
        query=payload.query,
        modality=payload.modality,
        rule_types=payload.rule_types or None,
        severities=payload.severities or None,
        top_k=payload.top_k,
        threshold=payload.threshold,
    )
    return RagSearchResponse(
        results=[
            RagResult(
                chunk_id=c.id,
                section=c.section,
                rule_type=c.rule_type,
                modality=c.modality,
                severity=c.severity,
                heading=c.heading,
                content=c.content,
                rule_ids=c.rule_ids,
                similarity=round(c.similarity, 4),
            )
            for c in chunks
        ],
        latency_ms=latencia,
        applied_filters={
            "modality": payload.modality.value if payload.modality else None,
            "rule_types": [rt.value for rt in payload.rule_types] or None,
            "severities": [s.value for s in payload.severities] or None,
            "top_k": payload.top_k,
            "threshold": payload.threshold,
        },
    )


@router.get(
    "/brands/{brand_id}/hard-rules",
    response_model=HardRulesResponse,
    summary="Léxico prohibido completo (sin RAG)",
)
async def hard_rules(
    brand_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> HardRulesResponse:
    """Las restricciones duras se leen por SQL, no por similitud vectorial.

    Un check de palabra prohibida necesita 100 % de recall: la búsqueda semántica
    podría devolver 8 de 15 términos y el Módulo II dejaría pasar violaciones.
    """
    lexicon = await get_hard_lexicon(db, brand_id)
    return HardRulesResponse(
        forbidden_terms=lexicon.get("forbidden_terms") or [],
        forbidden_claims=lexicon.get("forbidden_claims") or [],
        preferred_terms=lexicon.get("preferred_terms") or [],
    )
