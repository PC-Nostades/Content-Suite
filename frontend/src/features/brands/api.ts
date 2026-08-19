import { apiFetch } from '@/lib/api-client'
import type {
  BrandBrief,
  BrandDetail,
  BrandListItem,
  BrandStatusResponse,
  Modality,
  RagSearchResponse,
} from '@/types/api'

export const brandsApi = {
  list: (q = '') =>
    apiFetch<BrandListItem[]>(`/brands${q ? `?q=${encodeURIComponent(q)}` : ''}`),

  get: (brandId: string) => apiFetch<BrandDetail>(`/brands/${brandId}`),

  /** Payload mínimo: se pide cada 2,5 s mientras el manual se genera. */
  status: (brandId: string) =>
    apiFetch<BrandStatusResponse>(`/brands/${brandId}/status`, { timeoutMs: 20_000 }),

  /** Devuelve 202: la generación corre en background y se sigue por polling. */
  create: (brief: BrandBrief) =>
    apiFetch<BrandStatusResponse>('/brands', { method: 'POST', body: { brief } }),

  regenerate: (brandId: string) =>
    apiFetch<BrandStatusResponse>(`/brands/${brandId}/regenerate`, { method: 'POST' }),

  ragSearch: (params: {
    brand_id: string
    query: string
    modality?: Modality | null
    top_k?: number
  }) => apiFetch<RagSearchResponse>('/rag/search', { method: 'POST', body: params }),
}
