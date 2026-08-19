import { BookMarked, ShieldCheck, Sparkles, type LucideIcon } from 'lucide-react'

import { env } from './env'
import type { Role } from '@/types/api'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles: Role[]
  enabled: boolean
  badge?: string
}

/**
 * PUNTO DE REGISTRO de la navegación. Es una tabla de datos, no JSX: `AppShell`
 * renderiza `NAV_ITEMS.filter(i => i.roles.includes(user.role))`.
 *
 * Añadir el Módulo II = crear `features/content/`, una fila aquí y un <Route>
 * lazy en `app/router.tsx`. Cero refactor del layout.
 *
 * Los módulos futuros se dejan visibles pero deshabilitados: comunica que el
 * sistema completo está pensado, no solo la parte entregada.
 */
export const NAV_ITEMS: NavItem[] = [
  {
    to: '/brands',
    label: 'Manuales de Marca',
    icon: BookMarked,
    roles: ['creator', 'approver_a', 'approver_b', 'admin'],
    enabled: true,
  },
  {
    to: '/studio',
    label: 'Creative Engine',
    icon: Sparkles,
    roles: ['creator', 'admin'],
    enabled: env.ENABLE_MODULE_CONTENT,
    badge: 'Módulo II',
  },
  {
    to: '/review',
    label: 'Aprobaciones',
    icon: ShieldCheck,
    roles: ['approver_a', 'approver_b', 'admin'],
    enabled: env.ENABLE_MODULE_GOVERNANCE,
    badge: 'Módulo III',
  },
]

export const navItemsForRole = (role: Role): NavItem[] =>
  NAV_ITEMS.filter((item) => item.roles.includes(role))
