import { BookMarked, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { RoleGate } from '@/features/auth/components/RoleGate'
import { useCurrentUser } from '@/features/auth/auth-context'
import { ROLE_META } from '@/config/roles'

/**
 * Placeholder del Día 1: valida el shell, el RBAC y el login end-to-end.
 * La grilla real de marcas llega con el resto del Módulo I.
 */
export default function BrandsListPage() {
  const user = useCurrentUser()

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Manuales de Marca</h1>
          <p className="text-muted-foreground text-sm">
            La fuente de verdad de cada marca. Los módulos siguientes la consultan vía RAG.
          </p>
        </div>

        {/* Ocultar el botón es UX; el backend rechaza con 403 igualmente. */}
        <RoleGate allow={['creator']}>
          <Button>
            <Plus className="size-4" />
            Nueva marca
          </Button>
        </RoleGate>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <BookMarked className="size-4" />
            Aún no hay manuales
          </CardTitle>
          <CardDescription>
            {user.role === 'creator'
              ? 'Crea tu primera marca para generar un Manual de Marca con IA.'
              : 'Cuando un Creador publique un manual, aparecerá aquí en modo lectura.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="text-muted-foreground space-y-1 text-sm">
          <p>
            Sesión activa: <span className="text-foreground font-medium">{user.email}</span>
          </p>
          <p>
            Rol: <span className="text-foreground font-medium">{ROLE_META[user.role].label}</span>
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
