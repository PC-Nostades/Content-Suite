import { lazy, Suspense } from 'react'
import { Loader2 } from 'lucide-react'
import { createBrowserRouter, Navigate } from 'react-router'

import { ProtectedRoute } from '@/features/auth/components/ProtectedRoute'
import { AppShell } from '@/layouts/AppShell'
import { AuthLayout } from '@/layouts/AuthLayout'
import { ForbiddenPage, NotFoundPage } from '@/pages/ErrorPages'

const LoginPage = lazy(() => import('@/features/auth/pages/LoginPage'))
const BrandsListPage = lazy(() => import('@/features/brands/pages/BrandsListPage'))
const BrandNewPage = lazy(() => import('@/features/brands/pages/BrandNewPage'))
const BrandDetailPage = lazy(() => import('@/features/brands/pages/BrandDetailPage'))

function Fallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center">
      <Loader2 className="text-muted-foreground size-6 animate-spin" />
    </div>
  )
}

const lazyEl = (node: React.ReactNode) => <Suspense fallback={<Fallback />}>{node}</Suspense>

/**
 * PUNTO DE REGISTRO de rutas.
 *
 * Las guardas de rol se anidan en vez de repetirse ruta por ruta: así una ruta
 * nueva hereda la protección sin que haya que recordar añadirla.
 */
export const router = createBrowserRouter([
  {
    element: <AuthLayout />,
    children: [{ path: '/login', element: lazyEl(<LoginPage />) }],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <Navigate to="/brands" replace /> },
          { path: 'brands', element: lazyEl(<BrandsListPage />) },

          // Solo el Creador muta marcas. Guarda anidada, no repetida: una ruta
          // nueva aquí hereda la protección sin que haya que recordar añadirla.
          {
            element: <ProtectedRoute allow={['creator']} />,
            children: [{ path: 'brands/new', element: lazyEl(<BrandNewPage />) }],
          },

          // Va DESPUÉS de 'brands/new' para que la ruta estática gane al param.
          { path: 'brands/:brandId', element: lazyEl(<BrandDetailPage />) },

          // Módulo II  → { element: <ProtectedRoute allow={['creator']} />, children: [{ path: 'studio', ... }] }
          // Módulo III → { element: <ProtectedRoute allow={['approver_a','approver_b']} />, children: [{ path: 'review', ... }] }
        ],
      },
    ],
  },
  { path: '/403', element: <ForbiddenPage /> },
  { path: '*', element: <NotFoundPage /> },
])
