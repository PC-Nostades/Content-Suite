import type { Role } from '@/types/api'

/** Etiqueta y color por rol. Que cada rol se vea distinto en la topbar es la
 *  forma más directa de evidenciar las "vistas diferenciadas" que pide el reto:
 *  se aprecia en una sola captura de pantalla. */
export const ROLE_META: Record<Role, { label: string; short: string; className: string }> = {
  creator: {
    label: 'Creador',
    short: 'CR',
    className: 'bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-950 dark:text-blue-200',
  },
  approver_a: {
    label: 'Aprobador A · Texto',
    short: 'AA',
    className:
      'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-200',
  },
  approver_b: {
    label: 'Aprobador B · Visual',
    short: 'AB',
    className:
      'bg-violet-100 text-violet-900 border-violet-300 dark:bg-violet-950 dark:text-violet-200',
  },
  admin: {
    label: 'Administrador',
    short: 'AD',
    className: 'bg-neutral-200 text-neutral-900 border-neutral-400',
  },
}

export const ALL_ROLES: Role[] = ['creator', 'approver_a', 'approver_b', 'admin']

/** Los aprobadores leen los manuales pero no los mutan. El porqué está en el
 *  README: en el Módulo III el Aprobador A juzga si un texto respeta el léxico
 *  y el B si una imagen respeta la paleta — sin acceso al manual, aprobar sería
 *  arbitrario. La restricción va sobre las mutaciones, y la aplica el backend. */
export const canCreateBrands = (role: Role): boolean => role === 'creator' || role === 'admin'
