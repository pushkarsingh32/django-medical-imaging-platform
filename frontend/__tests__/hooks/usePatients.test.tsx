import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { usePatients, usePatient } from '@/lib/hooks/usePatients';
import { patientService } from '@/lib/api';

// Mock the patientService
jest.mock('@/lib/api', () => ({
  patientService: {
    getAll: jest.fn(),
    getById: jest.fn(),
  },
}));

describe('usePatients Hooks', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
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

  describe('usePatients', () => {
    it('fetches patients list successfully', async () => {
      const mockResponse = {
        results: [
          {
            id: 1,
            medical_record_number: 'MRN-001',
            full_name: 'John Doe',
            age: 45,
            gender: 'M',
            hospital_name: 'City Hospital',
          },
        ],
        count: 1,
        next: null,
        previous: null,
      };

      (patientService.getAll as jest.Mock).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => usePatients(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockResponse);
      expect(patientService.getAll).toHaveBeenCalled();
    });

    it('passes query params correctly', async () => {
      const mockResponse = {
        results: [],
        count: 0,
        next: null,
        previous: null,
      };

      (patientService.getAll as jest.Mock).mockResolvedValue(mockResponse);

      const params = { search: 'John', page: 1 };
      const { result } = renderHook(() => usePatients(params), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(patientService.getAll).toHaveBeenCalledWith(params);
    });

    it('handles error state', async () => {
      (patientService.getAll as jest.Mock).mockRejectedValue(new Error('Failed to fetch'));

      const { result } = renderHook(() => usePatients(), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeTruthy();
    });
  });

  describe('usePatient', () => {
    it('fetches single patient successfully', async () => {
      const mockPatient = {
        id: 1,
        medical_record_number: 'MRN-001',
        full_name: 'John Doe',
        age: 45,
        gender: 'M',
        hospital_name: 'City Hospital',
        total_studies: 5,
        recent_studies: [],
      };

      (patientService.getById as jest.Mock).mockResolvedValue(mockPatient);

      const { result } = renderHook(() => usePatient(1), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      expect(result.current.data).toEqual(mockPatient);
      expect(patientService.getById).toHaveBeenCalledWith(1);
    });

    it('handles error when patient not found', async () => {
      (patientService.getById as jest.Mock).mockRejectedValue(new Error('Patient not found'));

      const { result } = renderHook(() => usePatient(999), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));

      expect(result.current.error).toBeTruthy();
    });
  });
});
