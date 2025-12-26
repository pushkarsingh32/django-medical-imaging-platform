import { useQuery } from '@tanstack/react-query';
import { statsService } from '../api';

export const statsKeys = {
  all: ['stats'] as const,
  dashboard: () => [...statsKeys.all, 'dashboard'] as const,
  trends: (params?: any) => [...statsKeys.all, 'trends', params] as const,
  modality: () => [...statsKeys.all, 'modality'] as const,
  activity: (limit?: number) => [...statsKeys.all, 'activity', limit] as const,
};

/**
 * Hook to fetch dashboard statistics
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: statsKeys.dashboard(),
    queryFn: () => statsService.getDashboardStats(),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to fetch study trends
 */
export function useStudyTrends(params?: { days?: number }) {
  return useQuery({
    queryKey: statsKeys.trends(params),
    queryFn: () => statsService.getStudyTrends(params),
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook to fetch modality distribution
 */
export function useModalityDistribution() {
  return useQuery({
    queryKey: statsKeys.modality(),
    queryFn: () => statsService.getModalityDistribution(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Hook to fetch recent activity
 */
export function useRecentActivity(limit?: number) {
  return useQuery({
    queryKey: statsKeys.activity(limit),
    queryFn: () => statsService.getRecentActivity(limit),
    staleTime: 60 * 1000, // 1 minute
  });
}
