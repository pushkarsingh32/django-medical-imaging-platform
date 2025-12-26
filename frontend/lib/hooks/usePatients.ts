import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { patientService } from '../api';
import type { PatientQueryParams, CreatePatientData } from '../api';

// Query keys
export const patientKeys = {
  all: ['patients'] as const,
  lists: () => [...patientKeys.all, 'list'] as const,
  list: (params?: PatientQueryParams) => [...patientKeys.lists(), params] as const,
  details: () => [...patientKeys.all, 'detail'] as const,
  detail: (id: number) => [...patientKeys.details(), id] as const,
};

/**
 * Hook to fetch paginated patients with filters
 */
export function usePatients(params?: PatientQueryParams) {
  return useQuery({
    queryKey: patientKeys.list(params),
    queryFn: () => patientService.getAll(params),
  });
}

/**
 * Hook to fetch single patient details
 */
export function usePatient(id: number) {
  return useQuery({
    queryKey: patientKeys.detail(id),
    queryFn: () => patientService.getById(id),
    enabled: !!id, // Only fetch if id exists
  });
}

/**
 * Hook to create new patient
 */
export function useCreatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePatientData) => patientService.create(data),
    onSuccess: () => {
      // Invalidate and refetch patients list
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}

/**
 * Hook to update patient
 */
export function useUpdatePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<CreatePatientData> }) =>
      patientService.update(id, data),
    onSuccess: (_, variables) => {
      // Invalidate specific patient and lists
      queryClient.invalidateQueries({ queryKey: patientKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}

/**
 * Hook to delete patient
 */
export function useDeletePatient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => patientService.delete(id),
    onSuccess: () => {
      // Invalidate patients list
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() });
    },
  });
}
