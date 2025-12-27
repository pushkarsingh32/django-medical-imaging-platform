import { apiClient } from '../client';
import {
  ImagingStudy,
  ImagingStudyDetail,
  PaginatedResponse,
  StudyQueryParams,
  StudyStatistics,
  UploadResponse,
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
  getImages: async (id: number): Promise<any[]> => {
    const response: any = await apiClient.get(`/images/`, { study: id });
    // Handle both paginated and array responses
    return Array.isArray(response) ? response : (response.results || []);
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
   * Update existing diagnosis
   */
  updateDiagnosis: (diagnosisId: number, data: any) => {
    return apiClient.patch(`/diagnoses/${diagnosisId}/`, data);
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

  /**
   * Upload images to a study
   */
  uploadImages: (studyId: number, formData: FormData): Promise<UploadResponse> => {
    return apiClient.post(`/studies/${studyId}/upload_images/`, formData);
  },
};
