import { useState } from 'react'
import { Check, Copy, ShieldAlert, X } from 'lucide-react'
import { toast } from 'sonner'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { bestLevelOn, readableTextOn } from '@/lib/contrast'
import type { BrandManual, Rule } from '@/types/api'

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <Card id={id} className="scroll-mt-20">
      <CardHeader className="pb-3">
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <p className="text-muted-foreground text-sm">{description}</p>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

/** Slider de solo lectura. Se lee en dos segundos y parece producto de diseño. */
function SpectrumBar({ left, right, value }: { left: string; right: string; value: number }) {
  return (
    <div className="space-y-1">
      <div className="text-muted-foreground flex justify-between text-xs">
        <span>{left}</span>
        <span>{right}</span>
      </div>
      <div className="bg-muted relative h-2 rounded-full">
        <div
          className="bg-primary absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-white dark:ring-neutral-900"
          style={{ left: `${value}%` }}
        />
      </div>
    </div>
  )
}

function RuleList({ rules }: { rules: Rule[] }) {
  return (
    <ul className="space-y-3">
      {rules.map((r) => (
        <li key={r.id} className="border-l-2 pl-3" style={{ borderColor: r.severity === 'hard' ? '#dc2626' : '#d4d4d8' }}>
          <div className="flex flex-wrap items-start gap-2">
            <Badge variant={r.severity === 'hard' ? 'destructive' : 'secondary'} className="text-[10px]">
              {r.severity}
            </Badge>
            <span className="flex-1 text-sm font-medium">{r.statement}</span>
          </div>
          {/* El check_hint es lo que convierte la regla en auditable: se muestra
              porque es exactamente lo que consumirá el Módulo III. */}
          <p className="text-muted-foreground mt-1 font-mono text-xs">
            ✓ {r.check_hint}
          </p>
          <p className="text-muted-foreground/70 mt-0.5 font-mono text-[10px]">{r.id}</p>
        </li>
      ))}
    </ul>
  )
}

export function ManualViewer({ manual }: { manual: BrandManual }) {
  const [filtroLexico, setFiltroLexico] = useState('')

  const copiar = (texto: string, etiqueta: string) => {
    void navigator.clipboard.writeText(texto)
    toast.success(`${etiqueta} copiado`)
  }

  const q = filtroLexico.trim().toLowerCase()
  const preferidos = manual.verbal.preferred_terms.filter(
    (t) => !q || t.use.toLowerCase().includes(q) || t.instead_of.join(' ').toLowerCase().includes(q),
  )
  const prohibidos = manual.verbal.forbidden_terms.filter(
    (t) => !q || t.term.toLowerCase().includes(q) || t.replacement.toLowerCase().includes(q),
  )

  return (
    <div className="space-y-4">
      {/* ─────────────────────────────── Identidad ─────────────────────────── */}
      <Section id="identidad" title="1 · Identidad y estrategia">
        <div className="space-y-4">
          <blockquote className="border-primary border-l-4 pl-4 text-lg italic">
            {manual.strategy.positioning_statement}
          </blockquote>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">Misión</p>
              <p className="text-sm">{manual.strategy.mission}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs font-medium uppercase">Arquetipo</p>
              <p className="text-sm capitalize">{manual.strategy.brand_archetype}</p>
            </div>
          </div>
          <div>
            <p className="text-muted-foreground mb-1.5 text-xs font-medium uppercase">Personalidad</p>
            <div className="flex flex-wrap gap-1.5">
              {manual.strategy.personality_traits.map((t) => (
                <Badge key={t} variant="secondary">{t}</Badge>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-muted-foreground mb-1 text-xs font-medium uppercase">Diferenciadores</p>
              <ul className="space-y-1 text-sm">
                {manual.strategy.differentiators.map((d) => (
                  <li key={d} className="flex gap-2">
                    <Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600" />{d}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-muted-foreground mb-1 text-xs font-medium uppercase">Lo que NO es</p>
              <ul className="space-y-1 text-sm">
                {manual.strategy.competitor_contrast.map((c) => (
                  <li key={c} className="flex gap-2">
                    <X className="mt-0.5 size-3.5 shrink-0 text-red-500" />{c}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </Section>

      {/* ──────────────────────────── Tono de voz ──────────────────────────── */}
      <Section id="tono" title="2 · Tono de voz">
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <SpectrumBar left="Formal" right="Casual" value={manual.verbal.voice_spectrum.formal_vs_casual} />
            <SpectrumBar left="Serio" right="Juguetón" value={manual.verbal.voice_spectrum.serious_vs_playful} />
            <SpectrumBar left="Respetuoso" right="Irreverente" value={manual.verbal.voice_spectrum.respectful_vs_irreverent} />
            <SpectrumBar left="Factual" right="Entusiasta" value={manual.verbal.voice_spectrum.factual_vs_enthusiastic} />
          </div>

          <div className="space-y-3">
            {manual.verbal.tone_attributes.map((t) => (
              <div key={t.name} className="rounded-lg border p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-medium">{t.name}</span>
                  <Badge variant="outline" className="text-[10px]">{t.intensity}/5</Badge>
                </div>
                <p className="text-muted-foreground mb-2 text-sm">{t.definition}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <div className="rounded-md border border-emerald-200 bg-emerald-50 p-2 text-sm dark:border-emerald-900 dark:bg-emerald-950">
                    <span className="mb-0.5 flex items-center gap-1 text-xs font-medium text-emerald-800 dark:text-emerald-300">
                      <Check className="size-3" /> Suena así
                    </span>
                    <span className="text-emerald-950 dark:text-emerald-100">{t.sounds_like}</span>
                  </div>
                  <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm dark:border-red-900 dark:bg-red-950">
                    <span className="mb-0.5 flex items-center gap-1 text-xs font-medium text-red-800 dark:text-red-300">
                      <X className="size-3" /> No suena así
                    </span>
                    <span className="text-red-950 dark:text-red-100">{t.does_not_sound_like}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ────────────────────────────── Léxico ─────────────────────────────── */}
      <Section
        id="lexico"
        title="3 · Léxico"
        description="Las listas de abajo no son sugerencias: el Creative Engine las aplica como filtro determinista."
      >
        <div className="space-y-4">
          <Input
            placeholder="Filtrar términos…"
            value={filtroLexico}
            onChange={(e) => setFiltroLexico(e.target.value)}
            className="max-w-xs"
          />

          <div className="grid gap-5 sm:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-medium uppercase text-emerald-700 dark:text-emerald-400">
                Preferidos ({preferidos.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {preferidos.map((t) => (
                  <Popover key={t.use}>
                    <PopoverTrigger asChild>
                      <button className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs text-emerald-900 hover:bg-emerald-100 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
                        {t.use}
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-72 text-sm">
                      <p className="font-medium">{t.use}</p>
                      <p className="text-muted-foreground mt-1 text-xs">
                        En vez de: {t.instead_of.join(', ')}
                      </p>
                      <p className="mt-2 text-xs">{t.rationale}</p>
                    </PopoverContent>
                  </Popover>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs font-medium uppercase text-red-700 dark:text-red-400">
                Prohibidos ({prohibidos.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {prohibidos.map((t) => (
                  <Popover key={t.term}>
                    <PopoverTrigger asChild>
                      <button className="rounded-full border border-red-200 bg-red-50 px-2.5 py-1 text-xs text-red-900 line-through hover:bg-red-100 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
                        {t.term}
                      </button>
                    </PopoverTrigger>
                    <PopoverContent className="w-72 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="font-medium line-through">{t.term}</span>
                        <Badge variant={t.severity === 'hard' ? 'destructive' : 'secondary'} className="text-[10px]">
                          {t.severity}
                        </Badge>
                        <Badge variant="outline" className="font-mono text-[10px]">{t.match_mode}</Badge>
                      </div>
                      <p className="text-muted-foreground mt-1.5 text-xs">{t.reason}</p>
                      <p className="mt-2 rounded bg-emerald-50 p-1.5 text-xs text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200">
                        Usa en su lugar: <strong>{t.replacement}</strong>
                      </p>
                    </PopoverContent>
                  </Popover>
                ))}
              </div>
            </div>
          </div>

          {manual.verbal.forbidden_claims.length > 0 && (
            <Alert>
              <ShieldAlert />
              <AlertTitle>Claims con riesgo regulatorio</AlertTitle>
              <AlertDescription>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {manual.verbal.forbidden_claims.map((c) => (
                    <Badge key={c.term} variant="outline" className="font-normal">
                      {c.term} → {c.replacement}
                    </Badge>
                  ))}
                </div>
              </AlertDescription>
            </Alert>
          )}
        </div>
      </Section>

      {/* ───────────────────────── Identidad visual ────────────────────────── */}
      <Section
        id="visual"
        title="4 · Identidad visual"
        description="Las reglas de esta sección son las que audita el Módulo III contra las imágenes."
      >
        <Tabs defaultValue="paleta">
          <TabsList>
            <TabsTrigger value="paleta">Paleta</TabsTrigger>
            <TabsTrigger value="tipografia">Tipografía</TabsTrigger>
            <TabsTrigger value="logo">Logo</TabsTrigger>
            <TabsTrigger value="foto">Fotografía</TabsTrigger>
          </TabsList>

          <TabsContent value="paleta" className="pt-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {manual.visual.color_palette.map((c) => {
                const texto = readableTextOn(c.hex)
                const nivel = bestLevelOn(c.hex)
                return (
                  <button
                    key={c.hex + c.name}
                    onClick={() => copiar(c.hex, c.hex)}
                    className="group relative flex h-28 flex-col justify-end rounded-xl p-2.5 text-left transition hover:scale-[1.02]"
                    style={{ backgroundColor: c.hex, color: texto }}
                  >
                    <Badge
                      variant="outline"
                      className="absolute right-2 top-2 border-current/30 text-[9px]"
                      style={{ color: texto }}
                    >
                      {nivel}
                    </Badge>
                    <span className="text-xs font-medium leading-tight">{c.name}</span>
                    <span className="flex items-center gap-1 font-mono text-[11px] opacity-80">
                      {c.hex} <Copy className="size-2.5 opacity-0 group-hover:opacity-100" />
                    </span>
                    <span className="text-[10px] opacity-70">máx {c.max_area_pct}%</span>
                  </button>
                )
              })}
            </div>
          </TabsContent>

          <TabsContent value="tipografia" className="space-y-3 pt-4">
            {manual.visual.typography.map((t, i) => (
              <div key={i} className="rounded-lg border p-3">
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="font-medium">{t.family}</span>
                  <Badge variant="outline" className="text-[10px]">{t.role}</Badge>
                  <span className="text-muted-foreground text-xs">
                    mín {t.min_size_px_digital}px · {t.weights.join('/')}
                  </span>
                </div>
                <p className="text-xl" style={{ fontFamily: `'${t.family}', ${t.fallback}` }}>
                  Empaca sabor andino en cada bocado
                </p>
                <p className="text-muted-foreground mt-1 text-xs">{t.case_rules}</p>
              </div>
            ))}
          </TabsContent>

          <TabsContent value="logo" className="space-y-3 pt-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border p-3">
                <p className="text-muted-foreground text-xs uppercase">Ancho mínimo</p>
                <p className="text-2xl font-semibold">{manual.visual.logo.min_relative_width_pct}%</p>
                <p className="text-muted-foreground text-xs">de la pieza</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-muted-foreground text-xs uppercase">Zona de resguardo</p>
                <p className="text-2xl font-semibold">{manual.visual.logo.clear_space_multiplier}×</p>
                <p className="text-muted-foreground text-xs">la altura del logo</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-muted-foreground text-xs uppercase">Tamaño mínimo</p>
                <p className="text-2xl font-semibold">{manual.visual.logo.min_size_px_digital}px</p>
                <p className="text-muted-foreground text-xs">/ {manual.visual.logo.min_size_mm_print}mm impreso</p>
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-xs font-medium uppercase text-red-700 dark:text-red-400">Prohibido</p>
              <ul className="space-y-1 text-sm">
                {manual.visual.logo.forbidden_usages.map((u) => (
                  <li key={u} className="flex gap-2">
                    <X className="mt-0.5 size-3.5 shrink-0 text-red-500" />{u}
                  </li>
                ))}
              </ul>
            </div>
          </TabsContent>

          <TabsContent value="foto" className="space-y-3 pt-4">
            <div className="grid gap-2 text-sm sm:grid-cols-2">
              <p><span className="text-muted-foreground">Iluminación:</span> {manual.visual.photography.lighting}</p>
              <p><span className="text-muted-foreground">Color grading:</span> {manual.visual.photography.color_grading}</p>
              <p><span className="text-muted-foreground">Producto mínimo:</span> {manual.visual.photography.hero_product_min_area_pct}% del encuadre</p>
              <p><span className="text-muted-foreground">Personas:</span> {manual.visual.photography.people_representation}</p>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium uppercase text-red-700 dark:text-red-400">Imágenes prohibidas</p>
              <div className="flex flex-wrap gap-1.5">
                {manual.visual.photography.forbidden_imagery.map((f) => (
                  <Badge key={f} variant="outline" className="font-normal">{f}</Badge>
                ))}
              </div>
            </div>
            <div className="bg-muted rounded-lg p-3">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-xs font-medium uppercase">Semilla de prompt</span>
                <button
                  onClick={() => copiar(manual.visual.photography.prompt_seed, 'Prompt')}
                  className="text-muted-foreground hover:text-foreground text-xs"
                >
                  <Copy className="mr-1 inline size-3" />copiar
                </button>
              </div>
              <p className="font-mono text-xs">{manual.visual.photography.prompt_seed}</p>
              <p className="text-muted-foreground mt-1.5 text-[10px]">
                Lista para el Creative Engine (Módulo II)
              </p>
            </div>
          </TabsContent>
        </Tabs>
      </Section>

      {/* ─────────────────────── Reglas verificables ───────────────────────── */}
      <Section
        id="reglas"
        title="5 · Reglas verificables"
        description="Cada regla lleva una instrucción de verificación medible. Sin eso, una auditoría automática sería imposible."
      >
        <Tabs defaultValue="visuales">
          <TabsList>
            <TabsTrigger value="visuales">
              Visuales ({manual.visual.visual_rules.length})
            </TabsTrigger>
            <TabsTrigger value="texto">
              De texto ({manual.verbal.verbal_rules.length})
            </TabsTrigger>
            <TabsTrigger value="compliance">
              Cumplimiento ({manual.compliance.restricted_claims.length})
            </TabsTrigger>
          </TabsList>
          <TabsContent value="visuales" className="pt-4">
            <RuleList rules={manual.visual.visual_rules} />
          </TabsContent>
          <TabsContent value="texto" className="pt-4">
            <RuleList rules={manual.verbal.verbal_rules} />
          </TabsContent>
          <TabsContent value="compliance" className="pt-4">
            <RuleList rules={manual.compliance.restricted_claims} />
          </TabsContent>
        </Tabs>
      </Section>

      {/* ─────────────────────────── Cumplimiento ──────────────────────────── */}
      <Section id="cumplimiento" title={`6 · Cumplimiento — ${manual.compliance.market}`}>
        <ul className="space-y-1.5 text-sm">
          {manual.compliance.regulatory_notes.map((n) => (
            <li key={n} className="flex gap-2">
              <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-amber-600" />{n}
            </li>
          ))}
        </ul>
        <p className="text-muted-foreground mt-4 border-t pt-3 text-xs">
          Contenido generado por IA. Requiere validación legal y nutricional antes de su uso comercial.
        </p>
      </Section>
    </div>
  )
}
