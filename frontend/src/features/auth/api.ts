import { apiFetch } from '@/lib/api-client'
import type { LoginRequest, LoginResponse, User } from '@/types/api'

export const authApi = {
  login: (payload: LoginRequest) =>
    apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      body: payload,
      skipAuth: true,
      // Generoso: si el backend está dormido, el login es justo la petición que
      // paga el cold start de ~60 s.
      timeoutMs: 120_000,
    }),

  me: () => apiFetch<User>('/auth/me'),

  logout: () => apiFetch<void>('/auth/logout', { method: 'POST' }),
}
