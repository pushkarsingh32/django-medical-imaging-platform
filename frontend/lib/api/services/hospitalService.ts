import { apiClient } from '../client';
import { Hospital, PaginatedResponse } from '../types';

export const hospitalService = {
  /**
   * Get all hospitals with optional search filter
   */
  getAll: (params?: { search?: string }): Promise<Hospital[] | PaginatedResponse<Hospital>> => {
    return apiClient.get('/hospitals/', params);
  },

  /**
   * Get single hospital by ID
   */
  getById: (id: number): Promise<Hospital> => {
    return apiClient.get(`/hospitals/${id}/`);
  },

  /**
   * Create new hospital
   */
  create: (data: any): Promise<Hospital> => {
    return apiClient.post('/hospitals/', data);
  },

  /**
   * Update existing hospital
   */
  update: (id: number, data: any): Promise<Hospital> => {
    return apiClient.patch(`/hospitals/${id}/`, data);
  },

  /**
   * Delete hospital
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete(`/hospitals/${id}/`);
  },
};
