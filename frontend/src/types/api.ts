/**
 * Espejo de los schemas Pydantic del backend.
 *
 * No hay generación automática a propósito: sin workspaces npm, un único archivo
 * espejo es más simple que montar un pipeline de OpenAPI → TS para un módulo.
 * Si el contrato crece, el paso natural es `openapi-typescript` contra /openapi.json.
 */

/* ─────────────────────────── Comunes ─────────────────────────── */

export type Role = 'creator' | 'approver_a' | 'approver_b' | 'admin'

export type ManualStatus = 'generating' | 'ready' | 'failed' | 'published' | 'archived'

/** Etapas reales del agente multi-etapa: alimentan el stepper de progreso. */
export type GenerationStage =
  | 'queued'
  | 'drafting_strategy'
  | 'drafting_verbal'
  | 'drafting_visual'
  | 'drafting_compliance'
  | 'postprocessing'
  | 'chunking'
  | 'embedding'
  | 'done'

export type Severity = 'hard' | 'soft'
export type Modality = 'text' | 'visual' | 'both'

export type ApiErrorCode =
  | 'invalid_credentials'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'validation_error'
  | 'rate_limited'
  | 'generation_failed'
  | 'internal_error'

export interface ApiErrorDetail {
  code: ApiErrorCode
  /** En español y apto para mostrar al usuario tal cual. */
  message: string
  hint?: string
  retry_after_seconds?: number
  errors?: Array<{ field: string; message: string }>
}

/* ──────────────────────────── Auth ──────────────────────────── */

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  /** Segundos hasta la expiración. */
  expires_in: number
  /** Viene con el token para ahorrar un round-trip a /auth/me tras el login. */
  user: User
}

/** Payload del JWT, leído en el cliente SIN verificar firma — solo para pintar
 *  el shell sin esperar red. La autoridad es siempre el backend. */
export interface JwtPayload {
  sub: string
  email: string
  role: Role
  iat: number
  exp: number
}
