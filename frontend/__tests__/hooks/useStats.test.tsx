import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDashboardStats, useStudyTrends, useModalityDistribution, useRecentActivity } from '@/lib/hooks/useStats';
import { statsService } from '@/lib/api';

// Mock the statsService
jest.mock('@/lib/api', () => ({
  statsService: {
    getDashboardStats: jest.fn(),
    getStudyTrends: jest.fn(),
    getModalityDistribution: jest.fn(),
    getRecentActivity: jest.fn(),
  },
}));

describe('useStats Hooks', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    // Create a new QueryClient for each test
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    jest.clearAllMocks();
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  describe('useDashboardStats', () => {
    it('fetches dashboard stats successfully', async () => {
      const mockStats = {
        total_patients: 100,
        total_studies: 200,
        total_images: 500,
        total_hospitals: 5,
        new_patients_this_month: 10,
        studies_this_week: 25,
      };

      (statsService.getDashboardStats as jest.Mock).mockResolvedValue(mockStats);

      const { result } = renderHook(() => useDashboardStats(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockStats);
      expect(statsService.getDashboardStats).toHaveBeenCalledTimes(1);
    });

    it('handles error state', async () => {
      (statsService.getDashboardStats as jest.Mock).mockRejectedValue(new Error('API Error'));

      const { result } = renderHook(() => useDashboardStats(), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeTruthy();
    });
  });

  describe('useStudyTrends', () => {
    it('fetches study trends successfully', async () => {
      const mockTrends = [
        { date: '2025-12-01', count: 10 },
        { date: '2025-12-02', count: 15 },
      ];

      (statsService.getStudyTrends as jest.Mock).mockResolvedValue(mockTrends);

      const { result } = renderHook(() => useStudyTrends(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockTrends);
    });
  });

  describe('useModalityDistribution', () => {
    it('fetches modality distribution successfully', async () => {
      const mockDistribution = [
        { modality: 'CT', count: 50 },
        { modality: 'MRI', count: 30 },
      ];

      (statsService.getModalityDistribution as jest.Mock).mockResolvedValue(mockDistribution);

      const { result } = renderHook(() => useModalityDistribution(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockDistribution);
    });
  });

  describe('useRecentActivity', () => {
    it('fetches recent activity successfully', async () => {
      const mockActivity = [
        {
          id: 1,
          modality: 'CT',
          body_part: 'Chest',
          patient_name: 'John Doe',
          hospital_name: 'City Hospital',
          status: 'completed',
          study_date: '2025-12-27',
        },
      ];

      (statsService.getRecentActivity as jest.Mock).mockResolvedValue(mockActivity);

      const { result } = renderHook(() => useRecentActivity(10), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockActivity);
      expect(statsService.getRecentActivity).toHaveBeenCalledWith(10);
    });
  });
});
