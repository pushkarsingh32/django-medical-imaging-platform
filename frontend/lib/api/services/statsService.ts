import { apiClient } from '../client';
import type { DashboardStats, StudyTrend, ModalityDistribution, RecentActivity } from '../types';

export const statsService = {
  getDashboardStats: () => apiClient.get<DashboardStats>('/api/stats/'),
  getStudyTrends: (params?: { days?: number }) =>
    apiClient.get<StudyTrend[]>('/api/stats/trends/', params),
  getModalityDistribution: () =>
    apiClient.get<ModalityDistribution[]>('/api/stats/modality-distribution/'),
  getRecentActivity: (limit?: number) =>
    apiClient.get<RecentActivity[]>('/api/stats/recent-activity/', { limit }),
};
