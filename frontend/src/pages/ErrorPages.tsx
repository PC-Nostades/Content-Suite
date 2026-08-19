import { ShieldOff, SearchX } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'

function Shell({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="bg-muted text-muted-foreground flex size-14 items-center justify-center rounded-2xl">
        {icon}
      </div>
      <div className="space-y-1">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-muted-foreground max-w-md text-sm">{description}</p>
      </div>
      <Button asChild variant="outline">
        <Link to="/brands">Volver a Manuales de Marca</Link>
      </Button>
    </div>
  )
}

export function ForbiddenPage() {
  return (
    <Shell
      icon={<ShieldOff className="size-7" />}
      title="Sin permisos"
      description="Tu rol no tiene acceso a esta sección. El control se aplica también en el servidor: una petición directa a la API devolvería 403."
    />
  )
}

export function NotFoundPage() {
  return (
    <Shell
      icon={<SearchX className="size-7" />}
      title="Página no encontrada"
      description="La ruta que buscas no existe o cambió de lugar."
    />
  )
}
