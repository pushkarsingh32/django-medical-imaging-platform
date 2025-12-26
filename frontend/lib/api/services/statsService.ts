import { apiClient } from '../client';
import type { DashboardStats, StudyTrend, ModalityDistribution, RecentActivity } from '../types';

export const statsService = {
  getDashboardStats: () => apiClient.get<DashboardStats>('/stats/'),
  getStudyTrends: (params?: { days?: number }) =>
    apiClient.get<StudyTrend[]>('/stats/trends/', params),
  getModalityDistribution: () =>
    apiClient.get<ModalityDistribution[]>('/stats/modality-distribution/'),
  getRecentActivity: (limit?: number) =>
    apiClient.get<RecentActivity[]>('/stats/recent-activity/', { limit }),
};
