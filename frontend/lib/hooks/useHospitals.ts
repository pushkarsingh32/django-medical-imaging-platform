import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { hospitalService } from '../api';

export const hospitalKeys = {
  all: ['hospitals'] as const,
  lists: () => [...hospitalKeys.all, 'list'] as const,
  list: (params?: { search?: string }) => [...hospitalKeys.lists(), params] as const,
  details: () => [...hospitalKeys.all, 'detail'] as const,
  detail: (id: number) => [...hospitalKeys.details(), id] as const,
};

/**
 * Hook to fetch all hospitals with optional search filter
 */
export function useHospitals(params?: { search?: string }) {
  return useQuery({
    queryKey: hospitalKeys.list(params),
    queryFn: () => hospitalService.getAll(params),
  });
}

/**
 * Hook to fetch single hospital
 */
export function useHospital(id: number) {
  return useQuery({
    queryKey: hospitalKeys.detail(id),
    queryFn: () => hospitalService.getById(id),
    enabled: !!id,
  });
}

/**
 * Hook to create new hospital
 */
export function useCreateHospital() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => hospitalService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: hospitalKeys.lists() });
    },
  });
}

/**
 * Hook to update hospital
 */
export function useUpdateHospital() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) =>
      hospitalService.update(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: hospitalKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: hospitalKeys.lists() });
    },
  });
}

/**
 * Hook to delete hospital
 */
export function useDeleteHospital() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => hospitalService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: hospitalKeys.lists() });
    },
  });
}
