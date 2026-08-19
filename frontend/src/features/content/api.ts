import { apiFetch } from '@/lib/api-client'
import { env } from '@/config/env'
import { getToken } from '@/features/auth/token-storage'

export type ContentType = 'product_description' | 'video_script' | 'image_prompt' | 'social_post'

export interface Violation {
  term: string
  matched: string
  replacement: string
  severity: string
  reason: string
  kind: string
}

export interface ContentPiece {
  id: string
  brand_id: string
  brand_name: string
  type: ContentType
  channel: string
  status: 'draft' | 'pending_a' | 'pending_b' | 'approved' | 'rejected'
  brief: string
  title: string
  body: string
  rationale: string
  retrieved_rule_ids: string[]
  fixed_violations: Violation[]
  remaining_violations: Violation[]
  repair_attempts: number
  langfuse_trace_id: string | null
  created_by_name: string
  created_at: string
}

export interface Approval {
  id: string
  stage: string
  decision: string
  comment: string
  approver_name: string
  created_at: string
}

export interface Submission extends Omit<ContentPiece, 'rationale' | 'repair_attempts' | 'langfuse_trace_id'> {
  approvals: Approval[]
}

export interface Finding {
  rule_id: string
  rule_statement: string
  verdict: 'pass' | 'warn' | 'fail'
  evidence: string
  confidence: string
}

export interface AuditResult {
  id: string
  brand_id: string
  content_piece_id: string | null
  verdict: 'pass' | 'warn' | 'fail'
  summary: string
  findings: Finding[]
  checked_rule_ids: string[]
  model: string
  latency_ms: number | null
  created_at: string
}

export const contentApi = {
  generate: (payload: { brand_id: string; type: ContentType; channel: string; brief: string }) =>
    // El grafo puede recorrer el ciclo de reparación: se le da margen.
    apiFetch<ContentPiece>('/content', { method: 'POST', body: payload, timeoutMs: 180_000 }),

  list: (brandId?: string) =>
    apiFetch<ContentPiece[]>(`/content${brandId ? `?brand_id=${brandId}` : ''}`),

  submissions: () => apiFetch<Submission[]>('/submissions'),

  decide: (pieceId: string, decision: 'approved' | 'rejected', comment = '') =>
    apiFetch<Submission>(`/submissions/${pieceId}/decision`, {
      method: 'POST',
      body: { decision, comment },
    }),

  decideVisual: (pieceId: string, decision: 'approved' | 'rejected', comment = '') =>
    apiFetch<Submission>(`/submissions/${pieceId}/visual-decision`, {
      method: 'POST',
      body: { decision, comment },
    }),

  /** Multipart: no pasa por `apiFetch`, que asume JSON. */
  auditImage: async (brandId: string, file: File, contentPieceId?: string) => {
    const form = new FormData()
    form.append('brand_id', brandId)
    form.append('file', file)
    if (contentPieceId) form.append('content_piece_id', contentPieceId)

    const token = getToken()
    const response = await fetch(`${env.API_BASE_URL}/audit/image`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(payload?.detail?.message ?? `Error ${response.status}`)
    }
    return (await response.json()) as AuditResult
  },
}
