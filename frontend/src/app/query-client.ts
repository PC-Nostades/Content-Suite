import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '@/lib/api-client'

/**
 * Configuración global ajustada al free tier:
 *
 * - `refetchOnWindowFocus: false` — evita ráfagas de peticiones contra un backend
 *   que puede estar dormido, y no quema cupo de Gemini sin necesidad.
 * - `retry` no reintenta errores de cliente (401/403/404/422): reintentarlos no
 *   los va a arreglar y solo retrasa el mensaje de error.
 * - `retryDelay` exponencial 1s → 2s → 4s: cubre el despertar de Render sin
 *   mostrarle al usuario un error falso.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError && [401, 403, 404, 422].includes(error.status)) {
          return false
        }
        return failureCount < 3
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 15_000),
    },
    mutations: { retry: 0 },
  },
})
