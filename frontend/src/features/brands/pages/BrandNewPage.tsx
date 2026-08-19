import { useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { AlertCircle, Loader2, Sparkles, Wand2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { useNavigate } from 'react-router'
import { z } from 'zod'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ApiError } from '@/lib/api-client'
import { useCreateBrand } from '../hooks'
import type { BrandBrief } from '@/types/api'

const schema = z.object({
  brand_name: z.string().min(2, 'Mínimo 2 caracteres').max(60),
  product_category: z.string().min(3, 'Describe la categoría').max(120),
  tone: z.string().min(3, 'Describe el tono').max(120),
  target_audience: z.string().min(3, 'Describe el público').max(160),
  key_differentiator: z.string().max(240).optional(),
  market: z.string().max(80).optional(),
  constraints: z.string().max(500).optional(),
})

type FormValues = z.infer<typeof schema>

/** Presets de un clic. Es el elemento de mayor ROI de toda la UI: el evaluador
 *  genera en un clic en vez de tipear cuatro campos. */
const PRESETS: Array<{ label: string; hint: string; brief: FormValues }> = [
  {
    label: 'Snack de quinua · Gen Z',
    hint: 'Kiwicha Pop',
    brief: {
      brand_name: 'Kiwicha Pop',
      product_category: 'snack saludable de quinua inflada',
      tone: 'divertido pero profesional',
      target_audience: 'Gen Z urbana peruana, 18-26 años',
      key_differentiator: 'grano de Puno, sin azúcar añadida',
      market: 'Perú',
      constraints: 'Cumplir la Ley 30021 de Alimentación Saludable (octógonos).',
    },
  },
  {
    label: 'Aceite premium · Amas de casa',
    hint: 'Valle Dorado',
    brief: {
      brand_name: 'Valle Dorado',
      product_category: 'aceite de oliva extra virgen premium',
      tone: 'cálido y confiable, con autoridad culinaria',
      target_audience: 'cocineros aficionados de 35-55 años, NSE B/C',
      key_differentiator: 'prensado en frío de olivares de Tacna',
      market: 'Perú',
      constraints: '',
    },
  },
  {
    label: 'Bebida deportiva · Millennials',
    hint: 'Volt Andino',
    brief: {
      brand_name: 'Volt Andino',
      product_category: 'bebida deportiva isotónica natural',
      tone: 'enérgico y retador, sin agresividad',
      target_audience: 'millennials deportistas de 27-38 años',
      key_differentiator: 'electrolitos de sal rosada, sin colorantes artificiales',
      market: 'Perú',
      constraints: '',
    },
  },
]

const SUGERENCIAS_TONO = ['divertido pero profesional', 'cercano y cálido', 'premium y sobrio', 'enérgico y retador']
const SUGERENCIAS_PUBLICO = ['Gen Z urbana', 'Millennials deportistas', 'Madres jóvenes', 'Cocineros aficionados']

export default function BrandNewPage() {
  const navigate = useNavigate()
  const crear = useCreateBrand()
  const [error, setError] = useState<string | null>(null)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      brand_name: '', product_category: '', tone: '', target_audience: '',
      key_differentiator: '', market: 'Perú', constraints: '',
    },
  })

  const aplicarPreset = (preset: (typeof PRESETS)[number]) => {
    form.reset(preset.brief)
  }

  const onSubmit = async (values: FormValues) => {
    setError(null)
    try {
      const brief: BrandBrief = { ...values, language: 'es-PE' }
      const creada = await crear.mutateAsync(brief)
      // Navega de inmediato: el progreso se sigue en el detalle, no aquí.
      navigate(`/brands/${creada.id}`, { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.detail?.message ?? 'No se pudo crear la marca.')
          : 'No se pudo contactar al servidor.',
      )
    }
  }

  const enviando = form.formState.isSubmitting || crear.isPending
  const valores = form.watch()

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Nueva marca</h1>
        <p className="text-muted-foreground text-sm">
          Con unos pocos parámetros, la IA redacta un Manual de Marca completo y lo indexa para RAG.
        </p>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} className="grid gap-6 lg:grid-cols-5">
        {/* ─────────────────────────── Formulario ─────────────────────────── */}
        <div className="space-y-4 lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Producto</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="brand_name">Nombre de la marca *</Label>
                <Input id="brand_name" placeholder="Kiwicha Pop" {...form.register('brand_name')} />
                {form.formState.errors.brand_name && (
                  <p className="text-destructive text-xs">{form.formState.errors.brand_name.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="product_category">Categoría de producto *</Label>
                <Textarea
                  id="product_category"
                  rows={2}
                  placeholder="snack saludable de quinua inflada"
                  {...form.register('product_category')}
                />
                {form.formState.errors.product_category && (
                  <p className="text-destructive text-xs">{form.formState.errors.product_category.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="key_differentiator">Diferenciador clave</Label>
                <Input
                  id="key_differentiator"
                  placeholder="grano de Puno, sin azúcar añadida"
                  {...form.register('key_differentiator')}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Audiencia y tono</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="target_audience">Público objetivo *</Label>
                <Input id="target_audience" placeholder="Gen Z urbana peruana, 18-26 años" {...form.register('target_audience')} />
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {SUGERENCIAS_PUBLICO.map((s) => (
                    <Badge
                      key={s}
                      variant="outline"
                      className="cursor-pointer text-xs font-normal hover:bg-accent"
                      onClick={() => form.setValue('target_audience', s, { shouldValidate: true })}
                    >
                      {s}
                    </Badge>
                  ))}
                </div>
                {form.formState.errors.target_audience && (
                  <p className="text-destructive text-xs">{form.formState.errors.target_audience.message}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="tone">Tono deseado *</Label>
                <Input id="tone" placeholder="divertido pero profesional" {...form.register('tone')} />
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {SUGERENCIAS_TONO.map((s) => (
                    <Badge
                      key={s}
                      variant="outline"
                      className="cursor-pointer text-xs font-normal hover:bg-accent"
                      onClick={() => form.setValue('tone', s, { shouldValidate: true })}
                    >
                      {s}
                    </Badge>
                  ))}
                </div>
                {form.formState.errors.tone && (
                  <p className="text-destructive text-xs">{form.formState.errors.tone.message}</p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Mercado y restricciones</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="market">Mercado</Label>
                <Input id="market" placeholder="Perú" {...form.register('market')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="constraints">Restricciones legales o de negocio</Label>
                <Textarea
                  id="constraints"
                  rows={3}
                  placeholder="No usar 'saludable' sin respaldo nutricional; cumplir la Ley de Alimentación Saludable (octógonos)."
                  {...form.register('constraints')}
                />
              </div>
            </CardContent>
          </Card>

          {error && (
            <Alert variant="destructive">
              <AlertCircle />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" size="lg" className="w-full" disabled={enviando}>
            {enviando ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {enviando ? 'Creando…' : 'Generar Manual de Marca'}
          </Button>
        </div>

        {/* ──────────────────────── Panel lateral ─────────────────────────── */}
        <div className="space-y-4 lg:col-span-2">
          <Card className="lg:sticky lg:top-20">
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <Wand2 className="size-4" />
                Ejemplos listos
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {PRESETS.map((p) => (
                <Button
                  key={p.label}
                  type="button"
                  variant="outline"
                  className="h-auto w-full justify-start py-2.5 text-left"
                  onClick={() => aplicarPreset(p)}
                  disabled={enviando}
                >
                  <span className="flex flex-col items-start">
                    <span className="text-sm font-medium">{p.label}</span>
                    <span className="text-muted-foreground text-xs font-normal">{p.hint}</span>
                  </span>
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Resumen</CardTitle>
            </CardHeader>
            <CardContent className="text-muted-foreground text-sm">
              {valores.brand_name ? (
                <p>
                  Manual para <strong className="text-foreground">{valores.brand_name}</strong>
                  {valores.product_category && <>, un <strong className="text-foreground">{valores.product_category}</strong></>}
                  {valores.tone && <>, con tono <strong className="text-foreground">{valores.tone}</strong></>}
                  {valores.target_audience && <>, dirigido a <strong className="text-foreground">{valores.target_audience}</strong></>}.
                </p>
              ) : (
                <p>Completa los campos o usa un ejemplo para ver el resumen aquí.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Qué se va a generar</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="text-muted-foreground space-y-1 text-sm">
                {[
                  'Estrategia, arquetipo y audiencias',
                  'Tono de voz y espectro de marca',
                  'Léxico preferido y prohibido',
                  'Pilares de mensaje y guías por canal',
                  'Paleta, tipografía y reglas de logo',
                  'Estilo fotográfico y composición',
                  'Reglas verificables para auditoría',
                  'Cumplimiento normativo',
                ].map((s) => (
                  <li key={s}>· {s}</li>
                ))}
              </ul>
              <p className="text-muted-foreground/70 mt-3 text-xs">
                Tarda entre 60 y 90 segundos. Puedes cerrar la pestaña: el progreso se guarda.
              </p>
            </CardContent>
          </Card>
        </div>
      </form>
    </div>
  )
}
