import { useEffect, useState } from 'react'
import { AlertCircle, Check, Loader2 } from 'lucide-react'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import type { GenerationStage } from '@/types/api'

/**
 * Pantalla de generación. **No es un spinner.**
 *
 * Una barra que avanza por etapas nombradas durante 80 s se percibe como un
 * sistema serio; un spinner durante 80 s se percibe como un cuelgue. Las etapas
 * son reales: vienen de `generation_stage`, que el agente persiste al avanzar.
 */

const ETAPAS: Array<{ key: GenerationStage; label: string }> = [
  { key: 'queued', label: 'Analizando los parámetros de marca' },
  { key: 'drafting_strategy', label: 'Definiendo estrategia, arquetipo y audiencia' },
  { key: 'drafting_visual', label: 'Redactando identidad verbal, visual y cumplimiento' },
  { key: 'postprocessing', label: 'Verificando reglas, colores y coherencia' },
  { key: 'embedding', label: 'Indexando el manual en pgvector para RAG' },
  { key: 'done', label: 'Listo' },
]

const ORDEN: GenerationStage[] = [
  'queued', 'drafting_strategy', 'drafting_verbal', 'drafting_visual',
  'drafting_compliance', 'postprocessing', 'chunking', 'embedding', 'done',
]

function indiceDe(stage: GenerationStage | null): number {
  if (!stage) return 0
  const i = ORDEN.indexOf(stage)
  if (i < 0) return 0
  // Las etapas intermedias del fan-out se agrupan bajo 'drafting_visual'.
  if (stage === 'drafting_verbal' || stage === 'drafting_compliance') return 2
  if (stage === 'chunking') return 4
  return ETAPAS.findIndex((e) => e.key === stage) >= 0
    ? ETAPAS.findIndex((e) => e.key === stage)
    : Math.min(4, Math.floor(i / 2))
}

export function GenerationProgress({
  stage,
  elapsedMs,
}: {
  stage: GenerationStage | null
  elapsedMs: number | null
}) {
  const [segundos, setSegundos] = useState(Math.floor((elapsedMs ?? 0) / 1000))

  useEffect(() => {
    const t = setInterval(() => setSegundos((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (elapsedMs != null) setSegundos(Math.floor(elapsedMs / 1000))
  }, [elapsedMs])

  const activo = indiceDe(stage)
  const mm = String(Math.floor(segundos / 60)).padStart(2, '0')
  const ss = String(segundos % 60).padStart(2, '0')

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm font-medium">
              <Loader2 className="text-primary size-4 animate-spin" />
              Generando el Manual de Marca
            </span>
            <span className="text-muted-foreground font-mono text-sm tabular-nums">
              {mm}:{ss}
            </span>
          </div>

          <ol className="space-y-2.5">
            {ETAPAS.slice(0, -1).map((etapa, i) => {
              const hecho = i < activo
              const enCurso = i === activo
              return (
                <li
                  key={etapa.key}
                  className={cn(
                    'flex items-center gap-3 text-sm',
                    hecho && 'text-muted-foreground',
                    enCurso && 'text-foreground font-medium',
                    !hecho && !enCurso && 'text-muted-foreground/50',
                  )}
                >
                  <span className="flex size-5 shrink-0 items-center justify-center">
                    {hecho ? (
                      <Check className="size-4 text-emerald-600" />
                    ) : enCurso ? (
                      <Loader2 className="text-primary size-4 animate-spin" />
                    ) : (
                      <span className="border-muted-foreground/30 size-2 rounded-full border" />
                    )}
                  </span>
                  {etapa.label}
                </li>
              )
            })}
          </ol>
        </CardContent>
      </Card>

      {segundos > 90 && (
        <Alert>
          <AlertCircle />
          <AlertDescription>
            Está tardando más de lo habitual. El servidor gratuito puede estar despertando;
            el estado se conserva aunque recargues la página.
          </AlertDescription>
        </Alert>
      )}

      {/* Skeletons con la GEOMETRÍA del resultado: una fila de círculos donde irá
          la paleta y dos columnas de chips donde irá el léxico. Un skeleton
          genérico de barras grises no comunica nada; uno isomórfico anticipa. */}
      <Card>
        <CardContent className="space-y-6 pt-6">
          <div className="space-y-2">
            <Skeleton className="h-4 w-32" />
            <div className="flex gap-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="size-16 rounded-xl" />
              ))}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-6">
            {[0, 1].map((col) => (
              <div key={col} className="space-y-2">
                <Skeleton className="h-4 w-28" />
                <div className="flex flex-wrap gap-1.5">
                  {Array.from({ length: 7 }).map((_, i) => (
                    <Skeleton key={i} className="h-6 w-20 rounded-full" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
