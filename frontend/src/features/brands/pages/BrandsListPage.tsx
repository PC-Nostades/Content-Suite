import { BookMarked, Loader2, Plus, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useCurrentUser } from '@/features/auth/auth-context'
import { RoleGate } from '@/features/auth/components/RoleGate'
import { useBrands } from '../hooks'
import type { BrandListItem, ManualStatus } from '@/types/api'

function StatusBadge({ status }: { status: ManualStatus | null }) {
  if (status === 'generating') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="size-3 animate-spin" />
        Generando
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <Badge variant="destructive" className="gap-1">
        <TriangleAlert className="size-3" />
        Falló
      </Badge>
    )
  }
  if (status === 'published' || status === 'ready') {
    return (
      <Badge className="border-emerald-300 bg-emerald-100 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
        Listo
      </Badge>
    )
  }
  return <Badge variant="outline">Sin manual</Badge>
}

function BrandCard({ brand }: { brand: BrandListItem }) {
  const color = brand.primary_color_hex ?? '#a1a1aa'
  return (
    <Link to={`/brands/${brand.id}`}>
      <Card className="overflow-hidden transition hover:shadow-md">
        {/* Barra superior con el color primario del manual: identifica la marca
            de un vistazo en la grilla. */}
        <div className="h-1.5 w-full" style={{ backgroundColor: color }} />
        <CardContent className="space-y-2 pt-4">
          <div className="flex items-start justify-between gap-2">
            <h3 className="font-medium leading-tight">{brand.brand_name}</h3>
            <StatusBadge status={brand.manual_status} />
          </div>
          <p className="text-muted-foreground line-clamp-2 text-sm">{brand.product_category}</p>
          <p className="text-muted-foreground/70 text-xs">
            {brand.created_by_name} · {brand.market}
          </p>
        </CardContent>
      </Card>
    </Link>
  )
}

export default function BrandsListPage() {
  const user = useCurrentUser()
  const { data: brands, isLoading, error } = useBrands()

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
          <Button asChild>
            <Link to="/brands/new">
              <Plus className="size-4" />
              Nueva marca
            </Link>
          </Button>
        </RoleGate>
      </div>

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      )}

      {error && (
        <Card>
          <CardContent className="text-destructive pt-6 text-sm">
            No se pudieron cargar las marcas. {(error as Error).message}
          </CardContent>
        </Card>
      )}

      {brands && brands.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
            <BookMarked className="text-muted-foreground size-8" />
            <div>
              <p className="font-medium">Aún no hay manuales</p>
              <p className="text-muted-foreground text-sm">
                {user.role === 'creator'
                  ? 'Crea tu primera marca para generar un Manual de Marca con IA.'
                  : 'Cuando un Creador publique un manual, aparecerá aquí en modo lectura.'}
              </p>
            </div>
            <RoleGate allow={['creator']}>
              <Button asChild variant="outline">
                <Link to="/brands/new">Crear la primera marca</Link>
              </Button>
            </RoleGate>
          </CardContent>
        </Card>
      )}

      {brands && brands.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {brands.map((b) => (
            <BrandCard key={b.id} brand={b} />
          ))}
        </div>
      )}
    </div>
  )
}
