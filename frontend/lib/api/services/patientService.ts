import { apiClient } from '../client';
import {
  Patient,
  PatientDetail,
  CreatePatientData,
  PaginatedResponse,
  PatientQueryParams,
  UploadResponse,
  PatientReport,
} from '../types';

export const patientService = {
  /**
   * Get paginated list of patients with optional filters
   */
  getAll: (params?: PatientQueryParams): Promise<PaginatedResponse<Patient>> => {
    return apiClient.get('/patients/', params);
  },

  /**
   * Get single patient by ID with detailed information
   */
  getById: (id: number): Promise<PatientDetail> => {
    return apiClient.get(`/patients/${id}/`);
  },

  /**
   * Create new patient
   */
  create: (data: CreatePatientData): Promise<Patient> => {
    return apiClient.post('/patients/', data);
  },

  /**
   * Update existing patient
   */
  update: (id: number, data: Partial<CreatePatientData>): Promise<Patient> => {
    return apiClient.put(`/patients/${id}/`, data);
  },

  /**
   * Partially update patient
   */
  patch: (id: number, data: Partial<CreatePatientData>): Promise<Patient> => {
    return apiClient.patch(`/patients/${id}/`, data);
  },

  /**
   * Delete patient
   */
  delete: (id: number): Promise<void> => {
    return apiClient.delete(`/patients/${id}/`);
  },

  /**
   * Get patient's imaging studies
   */
  getStudies: (id: number) => {
    return apiClient.get(`/patients/${id}/studies/`);
  },

  /**
   * Generate PDF report for patient (async with Celery)
   */
  generateReport: (id: number): Promise<UploadResponse> => {
    return apiClient.post(`/patients/${id}/generate_report/`, {});
  },

  /**
   * Get all PDF reports for a patient
   */
  getReports: (id: number): Promise<PatientReport[]> => {
    return apiClient.get(`/patients/${id}/reports/`);
  },
};
