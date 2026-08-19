"""Orquestación del Módulo I: crear marca, generar manual, indexar y publicar."""

import logging
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.postprocess import count_rules
from app.ai.schemas.brand_manual import BrandManual
from app.core.enums import GenerationStage, ManualStatus
from app.core.exceptions import Conflict, NotFound
from app.db.models import Brand, BrandManual as BrandManualRow, User
from app.db.session import SessionLocal
from app.modules.brand_dna.agent import run_agent
from app.modules.brand_dna.indexer import index_manual

logger = logging.getLogger(__name__)

#: Un manual que lleva más de esto en `generating` se considera huérfano: su
#: BackgroundTask murió con el proceso (redeploy de Render, OOM, reinicio).
STALE_AFTER = timedelta(minutes=10)


def slugify(text: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    base = re.sub(r"[^a-zA-Z0-9]+", "-", sin_acentos).strip("-").lower()
    return base[:100] or "marca"


async def _slug_unico(db: AsyncSession, nombre: str) -> str:
    base = slugify(nombre)
    existentes = set(
        (await db.scalars(select(Brand.slug).where(Brand.slug.like(f"{base}%")))).all()
    )
    if base not in existentes:
        return base
    i = 2
    while f"{base}-{i}" in existentes:
        i += 1
    return f"{base}-{i}"


async def create_brand_and_queue(
    db: AsyncSession, *, brief: dict, user: User
) -> tuple[Brand, BrandManualRow]:
    """Crea la marca y la fila del manual en estado `generating`.

    Devuelve inmediatamente: la generación real corre en una BackgroundTask. Es lo
    que permite responder 202 y que el frontend haga polling — con `await` la
    petición duraría 60 s y no sobreviviría a un refresh del navegador.
    """
    brand = Brand(
        name=brief["brand_name"],
        slug=await _slug_unico(db, brief["brand_name"]),
        category=brief.get("product_category", ""),
        market=brief.get("market") or "PE",
        brief=brief,
        owner_id=user.id,
    )
    db.add(brand)
    await db.flush()

    manual = BrandManualRow(
        brand_id=brand.id,
        version=1,
        status=ManualStatus.generating,
        stage=GenerationStage.queued,
        input_params=brief,
        created_by=user.id,
    )
    db.add(manual)
    await db.commit()
    await db.refresh(brand)
    await db.refresh(manual)
    return brand, manual


async def queue_regeneration(
    db: AsyncSession, *, brand: Brand, user: User
) -> BrandManualRow:
    """Nueva versión del manual. 409 si ya hay una generándose."""
    en_curso = await db.scalar(
        select(func.count())
        .select_from(BrandManualRow)
        .where(
            BrandManualRow.brand_id == brand.id,
            BrandManualRow.status == ManualStatus.generating,
        )
    )
    if en_curso:
        raise Conflict("Ya hay una generación en curso para esta marca.")

    ultima = await db.scalar(
        select(func.max(BrandManualRow.version)).where(BrandManualRow.brand_id == brand.id)
    )
    manual = BrandManualRow(
        brand_id=brand.id,
        version=(ultima or 0) + 1,
        status=ManualStatus.generating,
        stage=GenerationStage.queued,
        input_params=brand.brief,
        created_by=user.id,
    )
    db.add(manual)
    await db.commit()
    await db.refresh(manual)
    return manual


async def generate_and_index(manual_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    """Tarea de fondo: genera el manual, lo indexa y lo publica.

    Abre su propia sesión: la del request ya se cerró al devolver el 202.
    """
    from app.ai.observability import traced

    try:
        with traced("brand_manual.generate", input={"manual_id": str(manual_id)}) as span:
            await _set_trace_id(manual_id, span.trace_id)
            await _run(manual_id, brand_id, span)
    except Exception as exc:  # noqa: BLE001
        await _mark_failed(manual_id, exc)


async def _set_trace_id(manual_id: uuid.UUID, trace_id: str | None) -> None:
    if not trace_id:
        return
    async with SessionLocal() as db:
        await db.execute(
            update(BrandManualRow)
            .where(BrandManualRow.id == manual_id)
            .values(langfuse_trace_id=trace_id)
        )
        await db.commit()


async def _run(manual_id: uuid.UUID, brand_id: uuid.UUID, span) -> None:
    async def on_stage(stage: GenerationStage) -> None:
        async with SessionLocal() as db:
            await db.execute(
                update(BrandManualRow).where(BrandManualRow.id == manual_id).values(stage=stage)
            )
            await db.commit()

    async with SessionLocal() as db:
        fila = await db.get(BrandManualRow, manual_id)
        if fila is None:
            raise NotFound("El manual desapareció antes de generarse.")
        brief = dict(fila.input_params or {})

    try:
        manual, _report, meta = await run_agent(brief, on_stage=on_stage)
    except Exception as exc:
        await _mark_failed(manual_id, exc)
        raise

    # Indexado + publicación en UNA transacción: si el indexado falla, el manual
    # no queda publicado con el índice vacío.
    await on_stage(GenerationStage.embedding)
    async with SessionLocal() as db:
        async with db.begin():
            stats = await index_manual(
                db, manual=manual, manual_id=manual_id, brand_id=brand_id
            )
            # Un solo manual publicado por marca (índice único parcial en la BD).
            await db.execute(
                update(BrandManualRow)
                .where(
                    BrandManualRow.brand_id == brand_id,
                    BrandManualRow.status == ManualStatus.published,
                )
                .values(status=ManualStatus.archived)
            )
            await db.execute(
                update(BrandManualRow)
                .where(BrandManualRow.id == manual_id)
                .values(
                    status=ManualStatus.published,
                    stage=GenerationStage.done,
                    content=manual.model_dump(mode="json"),
                    generation_ms=meta["generation_ms"],
                    prompt_version=meta["prompt_version"],
                    model=_modelo_actual(),
                    published_at=datetime.now(UTC),
                    error=None,
                )
            )

    if span is not None:
        span.update(output={"chunks": stats["chunks"], "rules": meta["rules"]})
    logger.info("Manual %s publicado (%s chunks)", manual_id, stats["chunks"])


def _modelo_actual() -> str:
    from app.core.config import settings

    return f"{settings.LLM_PROVIDER}:{settings.text_model}"


async def _mark_failed(manual_id: uuid.UUID, exc: Exception) -> None:
    mensaje = getattr(exc, "message", None) or f"{type(exc).__name__}: {exc}"
    logger.error("Generación del manual %s falló: %s", manual_id, mensaje)
    async with SessionLocal() as db:
        await db.execute(
            update(BrandManualRow)
            .where(BrandManualRow.id == manual_id)
            .values(status=ManualStatus.failed, error=mensaje[:1000])
        )
        await db.commit()


async def reconcile_stale_generations() -> int:
    """Marca como fallidos los manuales huérfanos. Se ejecuta al arrancar.

    `BackgroundTasks` vive en el proceso: un redeploy de Render mata las
    generaciones en curso y, sin esto, esas marcas quedarían «generando» para
    siempre y el frontend haría polling eternamente.
    """
    limite = datetime.now(UTC) - STALE_AFTER
    async with SessionLocal() as db:
        resultado = await db.execute(
            update(BrandManualRow)
            .where(
                BrandManualRow.status == ManualStatus.generating,
                BrandManualRow.updated_at < limite,
            )
            .values(
                status=ManualStatus.failed,
                error="Generación interrumpida (el servidor se reinició). Vuelve a intentarlo.",
            )
        )
        await db.commit()
    n = resultado.rowcount or 0
    if n:
        logger.warning("Reconciliadas %d generaciones huérfanas", n)
    return n


def manual_stats(content: dict | None, chunks: int = 0) -> dict:
    """Estadísticas para la UI, tolerantes a un manual aún sin generar."""
    if not content:
        return {"chunks": chunks}
    try:
        manual = BrandManual.model_validate(content)
    except Exception:  # noqa: BLE001 — un manual viejo con otro schema no debe romper la lista
        return {"chunks": chunks}
    r = count_rules(manual)
    return {
        "chunks": chunks,
        "verbal_rules": r["verbal"],
        "visual_rules": r["visual"],
        "compliance_rules": r["compliance"],
        "forbidden_terms": r["forbidden_terms"],
        "colors": r["colores"],
    }


def primary_color(content: dict | None) -> str | None:
    """Color primario para pintar el borde de la tarjeta en la grilla."""
    if not content:
        return None
    for c in (content.get("visual", {}) or {}).get("color_palette", []) or []:
        if c.get("role") == "primary":
            return c.get("hex")
    paleta = (content.get("visual", {}) or {}).get("color_palette", []) or []
    return paleta[0].get("hex") if paleta else None
