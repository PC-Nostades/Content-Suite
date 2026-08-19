import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { UNAUTHORIZED_EVENT } from '@/lib/api-client'
import type { LoginRequest, User } from '@/types/api'
import { authApi } from './api'
import { clearToken, readValidSession, setToken } from './token-storage'

type AuthState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'authenticated'; user: User; token: string }

interface AuthContextValue {
  state: AuthState
  login: (payload: LoginRequest) => Promise<User>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })
  // Evita un setState tras desmontar si /auth/me responde tarde (cold start).
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  /**
   * Rehidratación optimista: si hay un token no expirado, entramos directo a
   * `authenticated` con el usuario derivado del payload y confirmamos contra
   * /auth/me en segundo plano. Sin esto, cada recarga mostraría el login por
   * un instante — y con el backend dormido ese instante duraría 60 s.
   */
  useEffect(() => {
    const session = readValidSession()
    if (!session) {
      setState({ status: 'anonymous' })
      return
    }

    setState({
      status: 'authenticated',
      token: session.token,
      user: {
        id: session.payload.sub,
        email: session.payload.email,
        role: session.payload.role,
        full_name: session.payload.email.split('@')[0] ?? '',
        created_at: new Date(session.payload.iat * 1000).toISOString(),
      },
    })

    authApi
      .me()
      .then((user) => {
        if (mounted.current) {
          setState({ status: 'authenticated', token: session.token, user })
        }
      })
      .catch(() => {
        // Un 401 ya disparó UNAUTHORIZED_EVENT y limpió el token. Si fue un
        // fallo de red (servidor dormido), se conserva la sesión optimista.
      })
  }, [])

  // Sesión invalidada por el servidor desde cualquier request.
  useEffect(() => {
    const onUnauthorized = () => {
      clearToken()
      if (mounted.current) setState({ status: 'anonymous' })
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const login = useCallback(async (payload: LoginRequest) => {
    const response = await authApi.login(payload)
    setToken(response.access_token)
    setState({ status: 'authenticated', token: response.access_token, user: response.user })
    return response.user
  }, [])

  const logout = useCallback(() => {
    // Fire-and-forget: el JWT es stateless, el logout del servidor es un no-op
    // de auditoría. No hacemos esperar al usuario por él.
    void authApi.logout().catch(() => undefined)
    clearToken()
    setState({ status: 'anonymous' })
  }, [])

  const value = useMemo<AuthContextValue>(() => ({ state, login, logout }), [state, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}

/** Atajo para vistas que ya están detrás de <ProtectedRoute>. */
export function useCurrentUser(): User {
  const { state } = useAuth()
  if (state.status !== 'authenticated') {
    throw new Error('useCurrentUser requiere una sesión activa')
  }
  return state.user
}
