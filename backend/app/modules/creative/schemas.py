"""DTOs del Módulo II — Creative Engine."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["product_description", "video_script", "image_prompt", "social_post"]
ContentStatus = Literal["draft", "pending_a", "pending_b", "approved", "rejected"]


class ContentGenerateRequest(BaseModel):
    brand_id: uuid.UUID
    type: ContentType
    channel: str = Field(default="", max_length=40)
    brief: str = Field(min_length=5, max_length=600)


class ViolationOut(BaseModel):
    term: str
    matched: str
    replacement: str
    severity: str
    reason: str
    kind: str


class ContentOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    brand_name: str
    type: ContentType
    channel: str
    status: ContentStatus
    brief: str

    title: str
    body: str
    rationale: str

    #: ⭐ Trazabilidad del RAG: qué reglas concretas guiaron esta pieza.
    retrieved_rule_ids: list[str]
    #: Violaciones que el ciclo del grafo detectó y corrigió. Es la prueba
    #: visible de que el manual se respeta y no solo se consulta.
    fixed_violations: list[ViolationOut]
    #: Las que sobrevivieron a los reintentos. Se reportan con honestidad.
    remaining_violations: list[ViolationOut]
    repair_attempts: int

    langfuse_trace_id: str | None
    created_by_name: str
    created_at: datetime
