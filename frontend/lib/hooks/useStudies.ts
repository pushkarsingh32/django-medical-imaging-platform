import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studyService } from '../api';

export const studyKeys = {
  all: ['studies'] as const,
  lists: () => [...studyKeys.all, 'list'] as const,
  list: (params?: any) => [...studyKeys.lists(), params] as const,
  details: () => [...studyKeys.all, 'detail'] as const,
  detail: (id: number) => [...studyKeys.details(), id] as const,
  images: (id: number) => [...studyKeys.detail(id), 'images'] as const,
  diagnosis: (id: number) => [...studyKeys.detail(id), 'diagnosis'] as const,
};

/**
 * Hook to fetch paginated studies
 */
export function useStudies(params?: any) {
  return useQuery({
    queryKey: studyKeys.list(params),
    queryFn: () => studyService.getAll(params),
  });
}

/**
 * Hook to fetch single study
 */
export function useStudy(id: number) {
  return useQuery({
    queryKey: studyKeys.detail(id),
    queryFn: () => studyService.getById(id),
    enabled: !!id,
  });
}

/**
 * Hook to fetch study images
 */
export function useStudyImages(id: number) {
  return useQuery({
    queryKey: studyKeys.images(id),
    queryFn: () => studyService.getImages(id),
    enabled: !!id,
  });
}

/**
 * Hook to create new study
 */
export function useCreateStudy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => studyService.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: studyKeys.lists() });
    },
  });
}

/**
 * Hook to update study
 */
export function useUpdateStudy(id: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => studyService.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: studyKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: studyKeys.lists() });
    },
  });
}

/**
 * Hook to add diagnosis to study
 */
export function useAddDiagnosis(studyId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => studyService.addDiagnosis(studyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: studyKeys.detail(studyId) });
      queryClient.invalidateQueries({ queryKey: studyKeys.diagnosis(studyId) });
    },
  });
}

/**
 * Hook to update existing diagnosis
 */
export function useUpdateDiagnosis(studyId: number) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ diagnosisId, data }: { diagnosisId: number; data: any }) =>
      studyService.updateDiagnosis(diagnosisId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: studyKeys.detail(studyId) });
      queryClient.invalidateQueries({ queryKey: studyKeys.diagnosis(studyId) });
    },
  });
}
