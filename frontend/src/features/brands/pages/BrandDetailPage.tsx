import { AlertCircle, ArrowLeft, Copy, ExternalLink, Loader2, RefreshCw } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { RoleGate } from '@/features/auth/components/RoleGate'
import { GenerationProgress } from '../components/GenerationProgress'
import { ManualViewer } from '../components/ManualViewer'
import { useBrand, useBrandStatus, useRegenerate } from '../hooks'

export default function BrandDetailPage() {
  const { brandId = '' } = useParams()
  const { data: brand, isLoading } = useBrand(brandId)

  const generando = brand?.manual_status === 'generating'
  const { data: estado } = useBrandStatus(brandId, generando)
  const regenerar = useRegenerate(brandId)

  // El estado del polling manda mientras genera: el detalle se refresca más lento.
  const status = estado?.manual_status ?? brand?.manual_status ?? null
  const stage = estado?.generation_stage ?? brand?.generation_stage ?? null

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Skeleton className="h-28 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (!brand) {
    return (
      <div className="mx-auto max-w-4xl">
        <Alert variant="destructive">
          <AlertCircle />
          <AlertDescription>No se encontró la marca.</AlertDescription>
        </Alert>
      </div>
    )
  }

  const paleta = brand.manual?.visual.color_palette ?? []
  const degradado =
    paleta.length >= 2
      ? `linear-gradient(135deg, ${paleta[0].hex}22, ${paleta[1].hex}22)`
      : undefined

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to="/brands">
          <ArrowLeft className="size-4" />
          Manuales de Marca
        </Link>
      </Button>

      {/* ──────────────────────────────── Hero ─────────────────────────────── */}
      <Card className="overflow-hidden">
        <div style={{ background: degradado }}>
          <CardContent className="space-y-3 pt-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <h1 className="text-2xl font-semibold tracking-tight">
                  {brand.brief.brand_name}
                </h1>
                <p className="text-muted-foreground text-sm">
                  {brand.brief.product_category} · {brand.brief.target_audience}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {brand.version && <Badge variant="outline">v{brand.version}</Badge>}
                {brand.model && (
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {brand.model}
                  </Badge>
                )}
              </div>
            </div>

            {paleta.length > 0 && (
              <div className="flex gap-1.5">
                {paleta.slice(0, 6).map((c) => (
                  <span
                    key={c.hex + c.name}
                    className="size-6 rounded-full ring-1 ring-black/10"
                    style={{ backgroundColor: c.hex }}
                    title={`${c.name} ${c.hex}`}
                  />
                ))}
              </div>
            )}

            {brand.manual?.executive_summary && (
              <p className="max-w-2xl text-sm leading-relaxed">
                {brand.manual.executive_summary}
              </p>
            )}

            <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
              {brand.stats.chunks > 0 && (
                <span>{brand.stats.chunks} chunks indexados en pgvector</span>
              )}
              {brand.stats.visual_rules ? (
                <span>{brand.stats.visual_rules} reglas visuales auditables</span>
              ) : null}
              {brand.generation_ms ? (
                <span>generado en {(brand.generation_ms / 1000).toFixed(0)}s</span>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-2 pt-1">
              <RoleGate allow={['creator']}>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={generando || regenerar.isPending}
                  onClick={() => {
                    regenerar.mutate(undefined, {
                      onSuccess: () => toast.success('Regenerando el manual…'),
                      onError: (e) => toast.error((e as Error).message),
                    })
                  }}
                >
                  {regenerar.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  Regenerar
                </Button>
                {brand.manual && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      void navigator.clipboard.writeText(JSON.stringify(brand.manual, null, 2))
                      toast.success('JSON del manual copiado')
                    }}
                  >
                    <Copy className="size-3.5" />
                    Copiar JSON
                  </Button>
                )}
              </RoleGate>
              {brand.langfuse_trace_id && (
                <Badge variant="outline" className="gap-1 font-mono text-[10px]">
                  <ExternalLink className="size-3" />
                  trace {brand.langfuse_trace_id.slice(0, 12)}…
                </Badge>
              )}
            </div>
          </CardContent>
        </div>
      </Card>

      {/* ─────────────────────────────── Estados ───────────────────────────── */}
      {status === 'generating' && (
        <GenerationProgress stage={stage} elapsedMs={estado?.elapsed_ms ?? null} />
      )}

      {status === 'failed' && (
        <Alert variant="destructive">
          <AlertCircle />
          <AlertTitle>La generación falló</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{brand.error_message ?? 'Error desconocido.'}</p>
            <RoleGate allow={['creator']}>
              <Button size="sm" variant="outline" onClick={() => regenerar.mutate()}>
                <RefreshCw className="size-3.5" />
                Reintentar
              </Button>
            </RoleGate>
          </AlertDescription>
        </Alert>
      )}

      {brand.manual && <ManualViewer manual={brand.manual} />}
    </div>
  )
}
