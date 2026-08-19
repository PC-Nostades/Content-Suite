/**
 * Lectura y validación de las variables de entorno de Vite.
 *
 * Se centraliza aquí para que ningún otro archivo toque `import.meta.env`:
 * así un typo en el nombre de una variable falla en un solo sitio.
 */

const bool = (value: string | undefined, fallback = false): boolean => {
  if (value === undefined) return fallback
  return value === 'true' || value === '1'
}

export const env = {
  /**
   * Por defecto relativo: mismo origen que el SPA. En producción el rewrite de
   * Render lo reenvía a la API; en local lo hace el proxy de Vite.
   */
  API_BASE_URL: (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/$/, ''),

  SHOW_DEMO_CREDENTIALS: bool(import.meta.env.VITE_SHOW_DEMO_CREDENTIALS, true),

  ENABLE_MODULE_CONTENT: bool(import.meta.env.VITE_ENABLE_MODULE_CONTENT, false),
  ENABLE_MODULE_GOVERNANCE: bool(import.meta.env.VITE_ENABLE_MODULE_GOVERNANCE, false),

  IS_DEV: import.meta.env.DEV,
} as const
