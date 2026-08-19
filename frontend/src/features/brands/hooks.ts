import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { BrandBrief } from '@/types/api'
import { brandsApi } from './api'

export const brandKeys = {
  all: ['brands'] as const,
  list: (q: string) => [...brandKeys.all, 'list', q] as const,
  detail: (id: string) => [...brandKeys.all, 'detail', id] as const,
  status: (id: string) => [...brandKeys.all, 'status', id] as const,
}

const EN_CURSO = (estado?: string | null) => estado === 'generating'

export function useBrands(q = '') {
  return useQuery({
    queryKey: brandKeys.list(q),
    queryFn: () => brandsApi.list(q),
    // Si alguna marca está generándose, la lista se refresca sola para que su
    // badge de estado no se quede congelado.
    refetchInterval: (query) =>
      query.state.data?.some((b) => EN_CURSO(b.manual_status)) ? 4000 : false,
  })
}

export function useBrand(brandId: string) {
  return useQuery({
    queryKey: brandKeys.detail(brandId),
    queryFn: () => brandsApi.get(brandId),
    enabled: Boolean(brandId),
  })
}

/**
 * Polling del estado de generación.
 *
 * `refetchInterval` como función es lo que hace que el polling **se apague solo**
 * al llegar a un estado terminal. Hacerlo a mano serían ~60 líneas de useEffect +
 * setInterval + limpieza + carrera con el desmontaje, y habría que repetirlo en
 * el Módulo III.
 */
export function useBrandStatus(brandId: string, activo: boolean) {
  const queryClient = useQueryClient()

  return useQuery({
    queryKey: brandKeys.status(brandId),
    queryFn: async () => {
      const estado = await brandsApi.status(brandId)
      // Al terminar, invalidamos el detalle para que traiga el manual completo.
      if (!EN_CURSO(estado.manual_status)) {
        void queryClient.invalidateQueries({ queryKey: brandKeys.detail(brandId) })
        void queryClient.invalidateQueries({ queryKey: brandKeys.all })
      }
      return estado
    },
    enabled: Boolean(brandId) && activo,
    refetchInterval: (query) => (EN_CURSO(query.state.data?.manual_status) ? 2500 : false),
    // No quema peticiones si el evaluador cambia de pestaña.
    refetchIntervalInBackground: false,
  })
}

export function useCreateBrand() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (brief: BrandBrief) => brandsApi.create(brief),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: brandKeys.all }),
  })
}

export function useRegenerate(brandId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => brandsApi.regenerate(brandId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: brandKeys.detail(brandId) })
      void queryClient.invalidateQueries({ queryKey: brandKeys.status(brandId) })
    },
  })
}
