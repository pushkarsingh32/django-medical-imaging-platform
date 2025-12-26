import { apiClient } from '../client';
import {
  ImagingStudy,
  ImagingStudyDetail,
  PaginatedResponse,
  StudyQueryParams,
  StudyStatistics,
} from '../types';

export const studyService = {
  /**
   * Get paginated list of studies with optional filters
   */
  getAll: (params?: StudyQueryParams): Promise<PaginatedResponse<ImagingStudy>> => {
    return apiClient.get('/studies/', params);
  },

  /**
   * Get single study by ID with images and diagnosis
   */
  getById: (id: number): Promise<ImagingStudyDetail> => {
    return apiClient.get(`/studies/${id}/`);
  },

  /**
   * Get images for a study
   */
  getImages: (id: number): Promise<any[]> => {
    return apiClient.get(`/images/`, { study: id });
  },

  /**
   * Create new study
   */
  create: (data: any): Promise<ImagingStudy> => {
    return apiClient.post('/studies/', data);
  },

  /**
   * Update existing study
   */
  update: (id: number, data: any): Promise<ImagingStudy> => {
    return apiClient.patch(`/studies/${id}/`, data);
  },

  /**
   * Add diagnosis to study
   */
  addDiagnosis: (studyId: number, data: any) => {
    return apiClient.post(`/studies/${studyId}/diagnosis/`, data);
  },

  /**
   * Get pending studies
   */
  getPending: (): Promise<ImagingStudy[]> => {
    return apiClient.get('/studies/pending/');
  },

  /**
   * Get study statistics
   */
  getStatistics: (): Promise<StudyStatistics> => {
    return apiClient.get('/studies/statistics/');
  },
};
