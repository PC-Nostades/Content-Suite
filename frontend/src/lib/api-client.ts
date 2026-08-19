import { env } from '@/config/env'
import type { ApiErrorDetail } from '@/types/api'
import { clearToken, getToken } from '@/features/auth/token-storage'

/** Evento global de sesión inválida.
 *  El cliente HTTP lo emite y el AuthProvider lo escucha: así el cliente no
 *  necesita conocer el router, y no hay dependencia circular entre ambos. */
export const UNAUTHORIZED_EVENT = 'cs:unauthorized'

export class ApiError extends Error {
  readonly status: number
  readonly detail: ApiErrorDetail | null

  constructor(status: number, detail: ApiErrorDetail | null) {
    super(detail?.message ?? `Error HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  get code(): ApiErrorDetail['code'] {
    return this.detail?.code ?? 'internal_error'
  }
}

/** Se lanza cuando el request se aborta por timeout, para distinguirlo de un
 *  error del servidor: el mensaje al usuario es distinto (servidor dormido vs. fallo). */
export class ApiTimeoutError extends Error {
  readonly timeoutMs: number

  constructor(timeoutMs: number) {
    super('La petición tardó demasiado. El servidor gratuito puede estar despertando.')
    this.name = 'ApiTimeoutError'
    this.timeoutMs = timeoutMs
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** 90 s por defecto: absorbe el cold start de ~60 s del free tier de Render. */
  timeoutMs?: number
  /** Para endpoints públicos (login): no adjunta el header Authorization. */
  skipAuth?: boolean
}

const DEFAULT_TIMEOUT_MS = 90_000

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeoutMs = DEFAULT_TIMEOUT_MS, skipAuth = false, ...init } = options

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)

  const token = skipAuth ? null : getToken()
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  try {
    const response = await fetch(`${env.API_BASE_URL}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })

    if (response.status === 401 && !skipAuth) {
      clearToken()
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new ApiError(response.status, payload?.detail ?? null)
    }

    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiTimeoutError(timeoutMs)
    }
    throw error
  } finally {
    clearTimeout(timer)
  }
}

/** Liveness del backend. Sirve para mostrar el banner de "despertando servidor"
 *  antes de que el usuario intente cualquier acción. */
export async function pingHealth(timeoutMs = 90_000): Promise<boolean> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch('/health', { signal: controller.signal })
    return response.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}
