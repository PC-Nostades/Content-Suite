import { LogOut, Sparkles } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { navItemsForRole } from '@/config/nav'
import { ROLE_META } from '@/config/roles'
import { useAuth, useCurrentUser } from '@/features/auth/auth-context'
import { cn } from '@/lib/utils'

function initials(fullName: string, email: string): string {
  const source = fullName.trim() || email
  const parts = source.split(/[\s.@]+/).filter(Boolean)
  return (parts[0]?.[0] ?? '?').concat(parts[1]?.[0] ?? '').toUpperCase()
}

export function AppShell() {
  const user = useCurrentUser()
  const { logout } = useAuth()
  const items = navItemsForRole(user.role)
  const roleMeta = ROLE_META[user.role]

  return (
    <div className="flex min-h-screen">
      {/* ---------------------------------------------------------- Sidebar */}
      <aside className="bg-sidebar hidden w-64 shrink-0 flex-col border-r md:flex">
        <div className="flex h-14 items-center gap-2 border-b px-4">
          <div className="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-md">
            <Sparkles className="size-4" />
          </div>
          <span className="font-semibold tracking-tight">Content Suite</span>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {items.map((item) => {
            const Icon = item.icon

            // Los módulos aún no implementados se muestran deshabilitados con su
            // badge: el evaluador ve el alcance completo del sistema de un vistazo.
            if (!item.enabled) {
              return (
                <div
                  key={item.to}
                  className="text-muted-foreground/60 flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm"
                  title="Próximamente"
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badge && (
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {item.badge}
                    </Badge>
                  )}
                </div>
              )
            }

            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'text-foreground/80 hover:bg-accent hover:text-accent-foreground',
                  )
                }
              >
                <Icon className="size-4 shrink-0" />
                <span className="flex-1 truncate">{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        <div className="text-muted-foreground border-t p-3 text-xs">
          Módulo I — Brand DNA Architect
        </div>
      </aside>

      {/* ------------------------------------------------- Contenido + topbar */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="bg-background/95 sticky top-0 z-10 flex h-14 items-center justify-between gap-3 border-b px-4 backdrop-blur">
          <div className="flex items-center gap-2 md:hidden">
            <Sparkles className="size-4" />
            <span className="font-semibold">Content Suite</span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            {/* El badge de rol coloreado es la evidencia visual de las "vistas
                diferenciadas": se aprecia en una sola captura de pantalla. */}
            <Badge variant="outline" className={cn('font-medium', roleMeta.className)}>
              {roleMeta.label}
            </Badge>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <span className="bg-muted flex size-8 items-center justify-center rounded-full text-xs font-semibold">
                    {initials(user.full_name, user.email)}
                  </span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel className="font-normal">
                  <div className="flex flex-col space-y-0.5">
                    <span className="text-sm font-medium">{user.full_name || user.email}</span>
                    <span className="text-muted-foreground truncate text-xs">{user.email}</span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={logout}>
                  <LogOut className="size-4" />
                  Cerrar sesión
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="min-w-0 flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
