import { apiClient } from '../client';
import { Hospital, PaginatedResponse } from '../types';

export const hospitalService = {
  /**
   * Get all hospitals
   */
  getAll: (): Promise<PaginatedResponse<Hospital>> => {
    return apiClient.get('/hospitals/');
  },

  /**
   * Get single hospital by ID
   */
  getById: (id: number): Promise<Hospital> => {
    return apiClient.get(`/hospitals/${id}/`);
  },
};
