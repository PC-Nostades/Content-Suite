import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router'

import { useAuth } from '../auth-context'
import type { Role } from '@/types/api'

/**
 * Guarda de rutas. Se usa ANIDADA en el router, no repetida ruta por ruta:
 *
 *   { element: <ProtectedRoute /> , children: [
 *       { element: <ProtectedRoute allow={['creator']} />, children: [...] }
 *   ]}
 *
 * Ocultar rutas aquí es UX. El control real lo hace el backend con
 * `require_role`: un aprobador que fuerce POST /brands recibe 403.
 */
export function ProtectedRoute({ allow }: { allow?: Role[] }) {
  const { state } = useAuth()
  const location = useLocation()

  if (state.status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="text-muted-foreground size-6 animate-spin" />
      </div>
    )
  }

  if (state.status === 'anonymous') {
    const next = encodeURIComponent(location.pathname + location.search)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  if (allow && !allow.includes(state.user.role) && state.user.role !== 'admin') {
    return <Navigate to="/403" replace />
  }

  return <Outlet />
}
