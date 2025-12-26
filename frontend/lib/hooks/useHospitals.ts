import { useQuery } from '@tanstack/react-query';
import { hospitalService } from '../api';

export const hospitalKeys = {
  all: ['hospitals'] as const,
  lists: () => [...hospitalKeys.all, 'list'] as const,
  details: () => [...hospitalKeys.all, 'detail'] as const,
  detail: (id: number) => [...hospitalKeys.details(), id] as const,
};

/**
 * Hook to fetch all hospitals
 */
export function useHospitals() {
  return useQuery({
    queryKey: hospitalKeys.lists(),
    queryFn: () => hospitalService.getAll(),
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
