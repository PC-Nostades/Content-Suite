import { KeyRound } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ROLE_META } from '@/config/roles'
import type { Role } from '@/types/api'

export const DEMO_ACCOUNTS: Array<{ email: string; role: Role; hint: string }> = [
  { email: 'creator@alicorp.demo', role: 'creator', hint: 'Crea marcas y genera manuales' },
  { email: 'approver.a@alicorp.demo', role: 'approver_a', hint: 'Revisa y aprueba textos' },
  { email: 'approver.b@alicorp.demo', role: 'approver_b', hint: 'Audita imágenes' },
]

export const DEMO_PASSWORD = 'Alicorp2026!'

/**
 * Tarjeta de acceso rápido para el evaluador: tres botones que rellenan y envían
 * el formulario. Permite probar las tres vistas en ~15 segundos en vez de
 * copiar y pegar credenciales del README.
 */
export function DemoCredentialsCard({
  onPick,
  disabled,
}: {
  onPick: (email: string, password: string) => void
  disabled?: boolean
}) {
  return (
    <Card className="border-dashed">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="size-4" />
          Cuentas de demostración
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {DEMO_ACCOUNTS.map(({ email, role, hint }) => (
          <Button
            key={email}
            type="button"
            variant="outline"
            disabled={disabled}
            onClick={() => onPick(email, DEMO_PASSWORD)}
            className="h-auto w-full justify-start gap-3 py-2.5 text-left"
          >
            <span
              className={`flex size-8 shrink-0 items-center justify-center rounded-md border text-xs font-semibold ${ROLE_META[role].className}`}
            >
              {ROLE_META[role].short}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">{ROLE_META[role].label}</span>
              <span className="text-muted-foreground truncate text-xs font-normal">{hint}</span>
            </span>
          </Button>
        ))}
        <p className="text-muted-foreground pt-1 text-xs">
          Contraseña común: <code className="font-mono">{DEMO_PASSWORD}</code>
        </p>
      </CardContent>
    </Card>
  )
}
