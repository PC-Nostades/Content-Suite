"""DTOs del Módulo I. Espejados en `frontend/src/types/api.ts`."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Channel, GenerationStage, ManualStatus, Modality, RuleType, Severity

PricePositioning = Literal["economico", "medio", "premium"]


class BrandBrief(BaseModel):
    """Los «parámetros cortos» que escribe el usuario. Solo 4 son obligatorios:
    pedir más campos obligatorios hunde la tasa de finalización del formulario."""

    brand_name: str = Field(min_length=2, max_length=60)
    product_category: str = Field(min_length=3, max_length=120)
    tone: str = Field(min_length=3, max_length=120)
    target_audience: str = Field(min_length=3, max_length=160)

    brand_values: list[str] = Field(default_factory=list, max_length=6)
    key_differentiator: str = Field(default="", max_length=240)
    price_positioning: PricePositioning | None = None
    market: str = Field(default="Perú", max_length=80)
    competitors: list[str] = Field(default_factory=list, max_length=5)
    channels: list[Channel] = Field(default_factory=list)
    language: str = Field(default="es-PE", max_length=20)
    constraints: str = Field(default="", max_length=500)


class BrandCreate(BaseModel):
    brief: BrandBrief


class BrandListItem(BaseModel):
    """Payload liviano para la grilla: no incluye el manual completo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand_name: str
    product_category: str
    market: str
    manual_status: ManualStatus | None
    generation_stage: GenerationStage | None
    manual_id: uuid.UUID | None
    primary_color_hex: str | None
    created_by_name: str
    created_at: datetime


class BrandStatus(BaseModel):
    """Respuesta mínima para el polling: se pide cada 2,5 s mientras genera."""

    id: uuid.UUID
    manual_status: ManualStatus | None
    generation_stage: GenerationStage | None
    manual_id: uuid.UUID | None
    error_message: str | None
    elapsed_ms: int | None


class ManualStats(BaseModel):
    chunks: int = 0
    verbal_rules: int = 0
    visual_rules: int = 0
    compliance_rules: int = 0
    forbidden_terms: int = 0
    colors: int = 0


class BrandDetail(BaseModel):
    id: uuid.UUID
    brief: dict
    manual_status: ManualStatus | None
    generation_stage: GenerationStage | None
    manual_id: uuid.UUID | None
    error_message: str | None
    version: int | None
    model: str | None
    generation_ms: int | None
    langfuse_trace_id: str | None
    created_by_name: str
    created_at: datetime
    #: `null` mientras `manual_status != 'ready'`.
    manual: dict | None
    stats: ManualStats


class ChunkOut(BaseModel):
    """Vitrina de que el chunking funciona. Nunca expone el embedding."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_index: int
    section: str
    rule_type: RuleType
    modality: Modality
    severity: Severity
    heading: str
    content: str
    rule_ids: list[str]
    token_count: int


# --------------------------------------------------------------------- RAG


class RagSearchRequest(BaseModel):
    brand_id: uuid.UUID
    query: str = Field(min_length=2, max_length=500)
    modality: Modality | None = None
    rule_types: list[RuleType] = Field(default_factory=list)
    severities: list[Severity] = Field(default_factory=list)
    top_k: int = Field(default=8, ge=1, le=30)
    threshold: float = Field(default=0.10, ge=0.0, le=1.0)


class RagResult(BaseModel):
    chunk_id: uuid.UUID
    section: str
    rule_type: str
    modality: str
    severity: str
    heading: str
    content: str
    rule_ids: list[str]
    similarity: float


class RagSearchResponse(BaseModel):
    results: list[RagResult]
    latency_ms: int
    #: Filtros efectivamente aplicados: hace visible el pre-filtrado por dominio,
    #: que es la parte no obvia (y evaluable) de la arquitectura RAG.
    applied_filters: dict


class HardRulesResponse(BaseModel):
    forbidden_terms: list[dict]
    forbidden_claims: list[dict]
    preferred_terms: list[dict]
