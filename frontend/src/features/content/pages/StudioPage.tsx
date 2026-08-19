import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertCircle, Copy, Loader2, ShieldCheck, Sparkles, Wand2 } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useBrands } from '@/features/brands/hooks'
import { contentApi, type ContentPiece, type ContentType } from '../api'

const TIPOS: Array<{ value: ContentType; label: string }> = [
  { value: 'product_description', label: 'Descripción de producto' },
  { value: 'video_script', label: 'Guion de video' },
  { value: 'image_prompt', label: 'Prompt de imagen' },
  { value: 'social_post', label: 'Post para redes' },
]

const CANALES = ['instagram', 'tiktok', 'ecommerce_pdp', 'packaging', 'email', 'web']

export default function StudioPage() {
  const { data: brands } = useBrands()
  const listos = (brands ?? []).filter((b) => b.manual_status === 'published')

  const [brandId, setBrandId] = useState('')
  const [tipo, setTipo] = useState<ContentType>('product_description')
  const [canal, setCanal] = useState('instagram')
  const [brief, setBrief] = useState('')
  const [pieza, setPieza] = useState<ContentPiece | null>(null)

  const historial = useQuery({
    queryKey: ['content', brandId],
    queryFn: () => contentApi.list(brandId || undefined),
    enabled: Boolean(brandId),
  })

  const generar = useMutation({
    mutationFn: () => contentApi.generate({ brand_id: brandId, type: tipo, channel: canal, brief }),
    onSuccess: (p) => {
      setPieza(p)
      void historial.refetch()
      toast.success('Contenido generado y enviado a aprobación')
    },
    onError: (e) => toast.error((e as Error).message),
  })

  const puedeGenerar = brandId && brief.trim().length >= 5 && !generar.isPending

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Creative Engine</h1>
        <p className="text-muted-foreground text-sm">
          Antes de escribir una sola palabra, el sistema consulta el manual de marca y aplica sus
          reglas. Las prohibiciones se verifican con código, no con criterio del modelo.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Qué generar</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Marca</Label>
              <Select value={brandId} onValueChange={setBrandId}>
                <SelectTrigger><SelectValue placeholder="Elige una marca" /></SelectTrigger>
                <SelectContent>
                  {listos.map((b) => (
                    <SelectItem key={b.id} value={b.id}>{b.brand_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {listos.length === 0 && (
                <p className="text-muted-foreground text-xs">
                  Necesitas una marca con manual publicado.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Tipo de contenido</Label>
              <Select value={tipo} onValueChange={(v) => setTipo(v as ContentType)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TIPOS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Canal</Label>
              <Select value={canal} onValueChange={setCanal}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CANALES.map((c) => (
                    <SelectItem key={c} value={c}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="brief">Brief</Label>
              <Textarea
                id="brief"
                rows={4}
                value={brief}
                onChange={(e) => setBrief(e.target.value)}
                placeholder="Lanzamiento del formato 30 g para vuelta a clases. Resaltar energía y origen."
              />
            </div>

            <Button className="w-full" disabled={!puedeGenerar} onClick={() => generar.mutate()}>
              {generar.isPending ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {generar.isPending ? 'Generando…' : 'Generar contenido'}
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4 lg:col-span-3">
          {generar.isPending && (
            <Card>
              <CardContent className="text-muted-foreground space-y-2 pt-6 text-sm">
                <p className="flex items-center gap-2">
                  <Loader2 className="size-4 animate-spin" /> Recuperando reglas del manual…
                </p>
                <p className="pl-6">Generando con el contexto recuperado…</p>
                <p className="pl-6">Validando contra el léxico prohibido…</p>
              </CardContent>
            </Card>
          )}

          {pieza && <ResultCard pieza={pieza} />}

          {!pieza && !generar.isPending && (
            <Card>
              <CardContent className="text-muted-foreground py-12 text-center text-sm">
                <Wand2 className="mx-auto mb-2 size-8 opacity-40" />
                El contenido generado aparecerá aquí, junto con las reglas que se aplicaron.
              </CardContent>
            </Card>
          )}

          {historial.data && historial.data.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Historial</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {historial.data.slice(0, 6).map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPieza(p)}
                    className="hover:bg-accent flex w-full items-center gap-2 rounded-md border p-2 text-left text-sm"
                  >
                    <Badge variant="outline" className="shrink-0 text-[10px]">{p.status}</Badge>
                    <span className="flex-1 truncate">{p.title || p.brief}</span>
                  </button>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function ResultCard({ pieza }: { pieza: ContentPiece }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{pieza.title}</CardTitle>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard.writeText(`${pieza.title}\n\n${pieza.body}`)
              toast.success('Copiado')
            }}
          >
            <Copy className="size-3.5" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{pieza.body}</p>

        {pieza.rationale && (
          <p className="text-muted-foreground border-l-2 pl-3 text-xs italic">
            {pieza.rationale}
          </p>
        )}

        {/* ⭐ La evidencia de que el RAG se respeta y no solo se consulta. */}
        {pieza.fixed_violations.length > 0 && (
          <Alert>
            <ShieldCheck />
            <AlertTitle>
              El guardrail corrigió {pieza.fixed_violations.length} violación(es)
              {pieza.repair_attempts > 0 && ` en ${pieza.repair_attempts} reintento(s)`}
            </AlertTitle>
            <AlertDescription>
              <ul className="mt-1 space-y-1 text-xs">
                {pieza.fixed_violations.map((v, i) => (
                  <li key={i}>
                    <span className="line-through">{v.matched}</span> → <strong>{v.replacement}</strong>
                    <span className="text-muted-foreground"> · {v.reason}</span>
                  </li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {pieza.remaining_violations.length > 0 && (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>Violaciones no resueltas</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 space-y-1 text-xs">
                {pieza.remaining_violations.map((v, i) => (
                  <li key={i}>«{v.matched}» — debería ser «{v.replacement}»</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        <div>
          <p className="text-muted-foreground mb-1.5 text-xs font-medium uppercase">
            Reglas del manual aplicadas ({pieza.retrieved_rule_ids.length})
          </p>
          <div className="flex flex-wrap gap-1">
            {pieza.retrieved_rule_ids.slice(0, 12).map((id) => (
              <Badge key={id} variant="outline" className="font-mono text-[9px] font-normal">
                {id}
              </Badge>
            ))}
          </div>
        </div>

        <p className="text-muted-foreground text-xs">
          Estado: <Badge variant="secondary" className="text-[10px]">{pieza.status}</Badge>
          {' '}· enviado a la bandeja de aprobación
        </p>
      </CardContent>
    </Card>
  )
}
