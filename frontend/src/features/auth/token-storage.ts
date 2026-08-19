import type { JwtPayload } from '@/types/api'

const TOKEN_KEY = 'cs.auth.token'

/**
 * El JWT vive en localStorage y viaja como Bearer.
 *
 * Trade-off documentado en el README: como el SPA proxea /api/* desde su propio
 * origen, una cookie httpOnly + SameSite=Lax SÍ sería viable y es más segura.
 * Se descarta porque (a) dependería de que el proxy de rewrite de Render reenvíe
 * Set-Cookie/Cookie correctamente — justo el eslabón no verificado del despliegue,
 * y el auth no debe depender de él; y (b) Bearer funciona idéntico en same-origin
 * y en cross-origin, así que el plan B de CORS no obliga a tocar nada de auth.
 *
 * Sin cookies no hay superficie CSRF. La mitigación de XSS es que todo el
 * contenido generado se renderiza como datos tipados, nunca con dangerouslySetInnerHTML.
 */
export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null // modo privado o storage deshabilitado
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* no-op: la sesión durará solo lo que viva la pestaña */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* no-op */
  }
}

/** Decodifica el payload SIN verificar la firma.
 *  Solo para pintar el shell de inmediato; la autoridad es siempre el backend. */
export function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const [, payload] = token.split('.')
    if (!payload) return null
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const json = decodeURIComponent(
      atob(normalized)
        .split('')
        .map((c) => `%${c.charCodeAt(0).toString(16).padStart(2, '0')}`)
        .join(''),
    )
    return JSON.parse(json) as JwtPayload
  } catch {
    return null
  }
}

export function isExpired(payload: JwtPayload, skewSeconds = 30): boolean {
  return payload.exp * 1000 <= Date.now() + skewSeconds * 1000
}

/** Token válido y no expirado, o null. Limpia el storage si estaba caducado. */
export function readValidSession(): { token: string; payload: JwtPayload } | null {
  const token = getToken()
  if (!token) return null
  const payload = decodeJwtPayload(token)
  if (!payload || isExpired(payload)) {
    clearToken()
    return null
  }
  return { token, payload }
}
