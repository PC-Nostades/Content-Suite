import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { AlertCircle, Loader2, Sparkles } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { env } from '@/config/env'
import { ApiError, ApiTimeoutError, pingHealth } from '@/lib/api-client'
import { useAuth } from '../auth-context'
import { DemoCredentialsCard } from '../components/DemoCredentialsCard'

const schema = z.object({
  email: z.string().min(1, 'Ingresa tu correo').email('Correo no válido'),
  password: z.string().min(1, 'Ingresa tu contraseña'),
})

type FormValues = z.infer<typeof schema>

export default function LoginPage() {
  const { state, login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [wakingUp, setWakingUp] = useState(false)

  const next = searchParams.get('next') ?? '/brands'

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  })

  /**
   * Despertamos el backend en cuanto se monta el login, sin esperar a que el
   * usuario envíe el formulario. Así el cold start de Render corre en paralelo
   * con el tiempo que la persona tarda en escribir sus credenciales.
   */
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      if (!cancelled) setWakingUp(true)
    }, 2500)

    void pingHealth().finally(() => {
      cancelled = true
      clearTimeout(timer)
      setWakingUp(false)
    })

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [])

  if (state.status === 'authenticated') return <Navigate to={next} replace />

  const onSubmit = async (values: FormValues) => {
    setError(null)
    try {
      await login(values)
      navigate(next, { replace: true })
    } catch (err) {
      if (err instanceof ApiTimeoutError) {
        setError(
          'El servidor tardó demasiado en responder. Suele ser el arranque del plan gratuito: espera unos segundos y reintenta.',
        )
      } else if (err instanceof ApiError) {
        setError(err.detail?.message ?? 'No se pudo iniciar sesión.')
      } else {
        setError('No se pudo contactar al servidor. Revisa tu conexión.')
      }
    }
  }

  const submitting = form.formState.isSubmitting

  const pickDemo = (email: string, password: string) => {
    form.setValue('email', email)
    form.setValue('password', password)
    void form.handleSubmit(onSubmit)()
  }

  return (
    <div className="mx-auto w-full max-w-sm space-y-4">
      <div className="space-y-2 text-center">
        <div className="bg-primary text-primary-foreground mx-auto flex size-11 items-center justify-center rounded-xl">
          <Sparkles className="size-6" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Content Suite</h1>
        <p className="text-muted-foreground text-sm">
          Consistencia de marca para lanzamientos masivos
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Iniciar sesión</CardTitle>
          <CardDescription>Accede con las credenciales de tu rol.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <div className="space-y-2">
              <Label htmlFor="email">Correo</Label>
              <Input
                id="email"
                type="email"
                autoComplete="username"
                placeholder="creator@alicorp.demo"
                disabled={submitting}
                {...form.register('email')}
              />
              {form.formState.errors.email && (
                <p className="text-destructive text-xs">{form.formState.errors.email.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Contraseña</Label>
              <Input
                id="password"
                type="password"
                autoComplete="current-password"
                disabled={submitting}
                {...form.register('password')}
              />
              {form.formState.errors.password && (
                <p className="text-destructive text-xs">{form.formState.errors.password.message}</p>
              )}
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertCircle />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting && <Loader2 className="size-4 animate-spin" />}
              {submitting ? 'Entrando…' : 'Entrar'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {wakingUp && (
        <Alert>
          <Loader2 className="animate-spin" />
          <AlertDescription>
            Despertando el servidor gratuito… La primera petición puede tardar hasta un minuto.
          </AlertDescription>
        </Alert>
      )}

      {env.SHOW_DEMO_CREDENTIALS && (
        <DemoCredentialsCard onPick={pickDemo} disabled={submitting} />
      )}
    </div>
  )
}
