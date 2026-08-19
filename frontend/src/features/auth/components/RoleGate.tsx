import type { ReactNode } from 'react'

import { useAuth } from '../auth-context'
import type { Role } from '@/types/api'

/**
 * Muestra sus hijos solo si el rol actual está permitido.
 * Para elementos de UI (botones, acciones), no para rutas: eso es <ProtectedRoute>.
 */
export function RoleGate({
  allow,
  children,
  fallback = null,
}: {
  allow: Role[]
  children: ReactNode
  fallback?: ReactNode
}) {
  const { state } = useAuth()
  if (state.status !== 'authenticated') return fallback
  const permitido = allow.includes(state.user.role) || state.user.role === 'admin'
  return permitido ? children : fallback
}
