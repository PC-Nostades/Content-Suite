import { QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import { Toaster } from '@/components/ui/sonner'
import { AuthProvider } from '@/features/auth/auth-context'
import { queryClient } from './query-client'

/** Orden intencional: Query envuelve a Auth porque el AuthProvider dispara
 *  peticiones (/auth/me) durante la rehidratación. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </QueryClientProvider>
  )
}
