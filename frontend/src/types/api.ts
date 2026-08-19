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

/* ─────────────────────── Módulo I — Brand DNA ─────────────────────── */

export type Channel =
  | 'packaging' | 'ecommerce_pdp' | 'instagram' | 'tiktok' | 'facebook'
  | 'email' | 'ooh' | 'tv_radio' | 'web' | 'punto_de_venta'

export type RuleType =
  | 'strategy' | 'audience' | 'tone' | 'lexicon' | 'grammar' | 'messaging' | 'channel'
  | 'color' | 'typography' | 'logo' | 'photography' | 'composition' | 'iconography'
  | 'packaging' | 'compliance'

export interface BrandBrief {
  brand_name: string
  product_category: string
  tone: string
  target_audience: string
  brand_values?: string[]
  key_differentiator?: string
  price_positioning?: 'economico' | 'medio' | 'premium' | null
  market?: string
  competitors?: string[]
  channels?: Channel[]
  language?: string
  constraints?: string
}

export interface BrandListItem {
  id: string
  brand_name: string
  product_category: string
  market: string
  manual_status: ManualStatus | null
  generation_stage: GenerationStage | null
  manual_id: string | null
  primary_color_hex: string | null
  created_by_name: string
  created_at: string
}

export interface BrandStatusResponse {
  id: string
  manual_status: ManualStatus | null
  generation_stage: GenerationStage | null
  manual_id: string | null
  error_message: string | null
  elapsed_ms: number | null
}

export interface ManualStats {
  chunks: number
  verbal_rules?: number
  visual_rules?: number
  compliance_rules?: number
  forbidden_terms?: number
  colors?: number
}

export interface BrandDetail {
  id: string
  brief: BrandBrief
  manual_status: ManualStatus | null
  generation_stage: GenerationStage | null
  manual_id: string | null
  error_message: string | null
  version: number | null
  model: string | null
  generation_ms: number | null
  langfuse_trace_id: string | null
  created_by_name: string
  created_at: string
  manual: BrandManual | null
  stats: ManualStats
}

/* ── El Manual de Marca (espejo de app/ai/schemas/brand_manual.py) ── */

export interface Rule {
  id: string
  statement: string
  rationale: string
  severity: Severity
  modality: Modality
  channel_scope: Channel[]
  good_example: string
  bad_example: string
  /** Instrucción operativa de verificación. Es lo que hace auditable la regla. */
  check_hint: string
}

export interface ColorSpec {
  name: string
  hex: string
  role: string
  usage_notes: string
  max_area_pct: number
  pairs_well_with: string[]
  never_pair_with: string[]
}

export interface BrandManual {
  schema_version: string
  executive_summary: string
  strategy: {
    brand_name: string
    category: string
    mission: string
    positioning_statement: string
    value_proposition: string
    brand_archetype: string
    personality_traits: string[]
    differentiators: string[]
    competitor_contrast: string[]
  }
  audiences: Array<{
    label: string
    age_range: string
    description: string
    psychographics: string[]
    jobs_to_be_done: string[]
    pain_points: string[]
    cultural_codes: string[]
    media_habits: Channel[]
  }>
  verbal: {
    tone_attributes: Array<{
      name: string; definition: string; intensity: number
      sounds_like: string; does_not_sound_like: string
    }>
    voice_spectrum: {
      formal_vs_casual: number
      serious_vs_playful: number
      respectful_vs_irreverent: number
      factual_vs_enthusiastic: number
    }
    preferred_terms: Array<{ use: string; instead_of: string[]; rationale: string }>
    forbidden_terms: Array<{
      term: string; reason: string; severity: Severity
      replacement: string; match_mode: 'exact' | 'stem' | 'regex'
    }>
    forbidden_claims: Array<{
      term: string; reason: string; severity: Severity
      replacement: string; match_mode: 'exact' | 'stem' | 'regex'
    }>
    grammar_style: Record<string, unknown>
    messaging_pillars: Array<{
      name: string; description: string; proof_points: string[]; sample_headlines: string[]
    }>
    taglines: string[]
    boilerplate: string
    channel_guidelines: Array<{
      channel: Channel; max_chars: number; structure: string
      cta_style: string; hashtag_policy: string; tone_adjustment: string
    }>
    verbal_rules: Rule[]
  }
  visual: {
    color_palette: ColorSpec[]
    forbidden_colors: ColorSpec[]
    typography: Array<{
      family: string; fallback: string; role: string; weights: string[]
      min_size_px_digital: number; line_height: string; case_rules: string
    }>
    forbidden_fonts: string[]
    logo: {
      approved_variants: string[]
      clear_space_multiplier: number
      min_size_px_digital: number
      min_size_mm_print: number
      min_relative_width_pct: number
      allowed_placements: string[]
      allowed_backgrounds: string[]
      forbidden_usages: string[]
    }
    photography: {
      mood: string; lighting: string; color_grading: string
      people_representation: string; hero_product_min_area_pct: number
      forbidden_imagery: string[]; prompt_seed: string
    }
    composition: {
      grid: string; safe_area_pct: number; visual_hierarchy: string[]
      max_text_coverage_pct: number; min_text_contrast_ratio: number
      white_space_policy: string; forbidden_layouts: string[]
    }
    iconography: Record<string, unknown>
    packaging: {
      mandatory_elements: string[]; front_panel_hierarchy: string[]
      legal_zone_notes: string; material_and_finish: string
    }
    visual_rules: Rule[]
  }
  compliance: {
    market: string
    regulatory_notes: string[]
    required_disclaimers: string[]
    restricted_claims: Rule[]
  }
}

/* ─────────────────────────── RAG ─────────────────────────── */

export interface RagResult {
  chunk_id: string
  section: string
  rule_type: RuleType
  modality: Modality
  severity: Severity
  heading: string
  content: string
  rule_ids: string[]
  similarity: number
}

export interface RagSearchResponse {
  results: RagResult[]
  latency_ms: number
  applied_filters: Record<string, unknown>
}
