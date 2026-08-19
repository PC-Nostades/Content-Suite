import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check, CircleCheck, CircleX, ImageUp, Loader2, ShieldAlert, TriangleAlert, X,
} from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useCurrentUser } from '@/features/auth/auth-context'
import { contentApi, type AuditResult, type Submission } from '@/features/content/api'

const ESTADO_LABEL: Record<string, string> = {
  pending_a: 'Pendiente · revisión de texto',
  pending_b: 'Pendiente · auditoría visual',
  approved: 'Aprobado',
  rejected: 'Rechazado',
  draft: 'Borrador',
}

const VEREDICTO = {
  pass: { icon: CircleCheck, cls: 'text-emerald-600', label: 'Cumple' },
  warn: { icon: TriangleAlert, cls: 'text-amber-600', label: 'Con reservas' },
  fail: { icon: CircleX, cls: 'text-red-600', label: 'Incumple' },
} as const

export default function ReviewPage() {
  const user = useCurrentUser()
  const queryClient = useQueryClient()
  const [comentario, setComentario] = useState('')

  const { data: submissions, isLoading } = useQuery({
    queryKey: ['submissions'],
    queryFn: () => contentApi.submissions(),
    refetchInterval: 15_000,
  })

  const esA = user.role === 'approver_a' || user.role === 'admin'
  const esB = user.role === 'approver_b' || user.role === 'admin'

  const decidir = useMutation({
    mutationFn: ({ id, decision, visual }: { id: string; decision: 'approved' | 'rejected'; visual: boolean }) =>
      visual
        ? contentApi.decideVisual(id, decision, comentario)
        : contentApi.decide(id, decision, comentario),
    onSuccess: (_d, v) => {
      setComentario('')
      void queryClient.invalidateQueries({ queryKey: ['submissions'] })
      toast.success(v.decision === 'approved' ? 'Aprobado' : 'Rechazado')
    },
    onError: (e) => toast.error((e as Error).message),
  })

  // Cada rol ve primero lo que le toca decidir: la misma pantalla, distinto foco.
  const miEtapa = esA ? 'pending_a' : esB ? 'pending_b' : null
  const pendientes = (submissions ?? []).filter((s) => s.status === miEtapa)
  const resto = (submissions ?? []).filter((s) => s.status !== miEtapa)

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Aprobaciones</h1>
        <p className="text-muted-foreground text-sm">
          {esA && 'Revisas el texto contra el manual de marca. Al aprobar, pasa a auditoría visual.'}
          {esB && !esA && 'Auditas las piezas gráficas contra las reglas visuales del manual.'}
        </p>
      </div>

      {isLoading && <Card><CardContent className="py-10 text-center"><Loader2 className="mx-auto size-5 animate-spin" /></CardContent></Card>}

      {submissions?.length === 0 && (
        <Card>
          <CardContent className="text-muted-foreground py-12 text-center text-sm">
            Aún no hay contenido enviado a aprobación. Genera una pieza en el Creative Engine.
          </CardContent>
        </Card>
      )}

      {pendientes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium uppercase tracking-wide">
            Requieren tu decisión ({pendientes.length})
          </h2>
          {pendientes.map((s) => (
            <SubmissionCard
              key={s.id}
              submission={s}
              puedeDecidirTexto={esA && s.status === 'pending_a'}
              puedeAuditar={esB && s.status === 'pending_b'}
              comentario={comentario}
              setComentario={setComentario}
              onDecidir={(decision) =>
                decidir.mutate({ id: s.id, decision, visual: s.status === 'pending_b' })
              }
              decidiendo={decidir.isPending}
            />
          ))}
        </section>
      )}

      {resto.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-muted-foreground text-sm font-medium uppercase tracking-wide">
            Resto del flujo ({resto.length})
          </h2>
          {resto.map((s) => (
            <SubmissionCard
              key={s.id}
              submission={s}
              puedeDecidirTexto={false}
              puedeAuditar={esB && s.status === 'pending_b'}
              comentario={comentario}
              setComentario={setComentario}
              onDecidir={() => undefined}
              decidiendo={false}
            />
          ))}
        </section>
      )}
    </div>
  )
}

function SubmissionCard({
  submission: s,
  puedeDecidirTexto,
  puedeAuditar,
  comentario,
  setComentario,
  onDecidir,
  decidiendo,
}: {
  submission: Submission
  puedeDecidirTexto: boolean
  puedeAuditar: boolean
  comentario: string
  setComentario: (v: string) => void
  onDecidir: (d: 'approved' | 'rejected') => void
  decidiendo: boolean
}) {
  const [auditoria, setAuditoria] = useState<AuditResult | null>(null)
  const inputFile = useRef<HTMLInputElement>(null)

  const auditar = useMutation({
    mutationFn: (file: File) => contentApi.auditImage(s.brand_id, file, s.id),
    onSuccess: (r) => {
      setAuditoria(r)
      toast.success(`Auditoría: ${VEREDICTO[r.verdict].label}`)
    },
    onError: (e) => toast.error((e as Error).message),
  })

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">{s.title || '(sin título)'}</CardTitle>
            <p className="text-muted-foreground text-xs">
              {s.brand_name} · {s.type} · {s.channel} · por {s.created_by_name}
            </p>
          </div>
          <Badge
            variant={s.status === 'approved' ? 'default' : s.status === 'rejected' ? 'destructive' : 'secondary'}
          >
            {ESTADO_LABEL[s.status] ?? s.status}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{s.body}</p>

        {s.fixed_violations.length > 0 && (
          <p className="text-muted-foreground text-xs">
            El guardrail ya corrigió {s.fixed_violations.length} violación(es) al generar:{' '}
            {s.fixed_violations.map((v) => v.matched).join(', ')}
          </p>
        )}

        {s.retrieved_rule_ids.length > 0 && (
          <details className="text-xs">
            <summary className="text-muted-foreground cursor-pointer">
              Reglas del manual aplicadas ({s.retrieved_rule_ids.length})
            </summary>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {s.retrieved_rule_ids.map((id) => (
                <Badge key={id} variant="outline" className="font-mono text-[9px] font-normal">{id}</Badge>
              ))}
            </div>
          </details>
        )}

        {s.approvals.length > 0 && (
          <div className="space-y-1 border-t pt-3">
            {s.approvals.map((a) => (
              <p key={a.id} className="text-muted-foreground text-xs">
                Etapa {a.stage.toUpperCase()} · {a.decision === 'approved' ? '✓ aprobado' : '✕ rechazado'}{' '}
                por {a.approver_name}
                {a.comment && ` — «${a.comment}»`}
              </p>
            ))}
          </div>
        )}

        {/* ─────────────────── Auditoría multimodal (Aprobador B) ─────────────── */}
        {puedeAuditar && (
          <div className="space-y-3 border-t pt-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Auditoría visual</span>
              <input
                ref={inputFile}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (f) auditar.mutate(f)
                }}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={auditar.isPending}
                onClick={() => inputFile.current?.click()}
              >
                {auditar.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <ImageUp className="size-3.5" />}
                {auditar.isPending ? 'Analizando…' : 'Subir pieza gráfica'}
              </Button>
            </div>

            {auditar.isPending && (
              <p className="text-muted-foreground text-xs">
                Recuperando reglas visuales del manual y contrastándolas con la imagen…
              </p>
            )}

            {auditoria && <AuditPanel result={auditoria} />}
          </div>
        )}

        {/* ─────────────────────────── Decisión ──────────────────────────────── */}
        {(puedeDecidirTexto || puedeAuditar) && (
          <div className="space-y-2 border-t pt-3">
            <Textarea
              rows={2}
              placeholder="Comentario (opcional)"
              value={comentario}
              onChange={(e) => setComentario(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" disabled={decidiendo} onClick={() => onDecidir('approved')}>
                <Check className="size-3.5" />
                Aprobar
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={decidiendo}
                onClick={() => onDecidir('rejected')}
              >
                <X className="size-3.5" />
                Rechazar
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AuditPanel({ result }: { result: AuditResult }) {
  const meta = VEREDICTO[result.verdict]
  const Icono = meta.icon

  return (
    <div className="space-y-3 rounded-lg border p-3">
      <div className="flex items-center gap-2">
        <Icono className={`size-5 ${meta.cls}`} />
        <span className={`font-medium ${meta.cls}`}>{meta.label}</span>
        <span className="text-muted-foreground text-xs">
          {result.findings.length} reglas evaluadas · {result.latency_ms} ms · {result.model}
        </span>
      </div>

      {result.summary && <p className="text-sm">{result.summary}</p>}

      <ul className="space-y-2">
        {result.findings
          // Los incumplimientos primero: es lo que el aprobador necesita ver.
          .slice()
          .sort((a, b) => (a.verdict === 'fail' ? -1 : 1) - (b.verdict === 'fail' ? -1 : 1))
          .map((f, i) => {
            const m = VEREDICTO[f.verdict]
            const I = m.icon
            return (
              <li key={i} className="flex gap-2 text-xs">
                <I className={`mt-0.5 size-3.5 shrink-0 ${m.cls}`} />
                <div className="min-w-0">
                  <p className="font-medium">{f.rule_statement}</p>
                  <p className="text-muted-foreground">{f.evidence}</p>
                  {/* La cita del rule_id es lo que convierte esto en gobernanza
                      y no en una opinión del modelo. */}
                  <p className="text-muted-foreground/60 font-mono text-[9px]">
                    {f.rule_id} · confianza {f.confidence}
                  </p>
                </div>
              </li>
            )
          })}
      </ul>

      {result.verdict === 'fail' && (
        <Alert variant="destructive">
          <ShieldAlert />
          <AlertDescription className="text-xs">
            La pieza incumple al menos una regla de severidad alta del manual.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

