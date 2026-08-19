/**
 * Contraste WCAG en el cliente.
 *
 * Se calcula de verdad en vez de asumir: el texto de cada swatch se pinta en
 * blanco o negro según el ratio real, y el badge AA/AAA sale de la aritmética.
 * Es un detalle pequeño que separa una demo de un producto — y aquí además
 * importa, porque el manual declara un contraste mínimo como regla auditable.
 *
 * Duplica ~20 líneas de `backend/app/ai/color.py` a propósito: montar un paquete
 * compartido para esto costaría más de lo que ahorra.
 */

function normalizeHex(value: string): string | null {
  const match = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim())
  if (!match) return null
  let digits = match[1]
  if (digits.length === 3) digits = digits.split('').map((c) => c + c).join('')
  return `#${digits.toUpperCase()}`
}

function srgbChannel(value: number): number {
  const c = value / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

export function relativeLuminance(hex: string): number | null {
  const normalized = normalizeHex(hex)
  if (!normalized) return null
  const r = parseInt(normalized.slice(1, 3), 16)
  const g = parseInt(normalized.slice(3, 5), 16)
  const b = parseInt(normalized.slice(5, 7), 16)
  return 0.2126 * srgbChannel(r) + 0.7152 * srgbChannel(g) + 0.0722 * srgbChannel(b)
}

export function contrastRatio(a: string, b: string): number | null {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  if (la === null || lb === null) return null
  const [lighter, darker] = la > lb ? [la, lb] : [lb, la]
  return (lighter + 0.05) / (darker + 0.05)
}

export function wcagLevel(ratio: number): 'AAA' | 'AA' | 'fail' {
  if (ratio >= 7) return 'AAA'
  if (ratio >= 4.5) return 'AA'
  return 'fail'
}

/** Color de texto legible sobre un fondo dado. */
export function readableTextOn(background: string): '#FFFFFF' | '#111111' {
  const conBlanco = contrastRatio(background, '#FFFFFF') ?? 0
  const conNegro = contrastRatio(background, '#111111') ?? 0
  return conBlanco >= conNegro ? '#FFFFFF' : '#111111'
}

/** Nivel WCAG del mejor texto posible sobre ese fondo. */
export function bestLevelOn(background: string): 'AAA' | 'AA' | 'fail' {
  const mejor = Math.max(
    contrastRatio(background, '#FFFFFF') ?? 0,
    contrastRatio(background, '#111111') ?? 0,
  )
  return wcagLevel(mejor)
}
