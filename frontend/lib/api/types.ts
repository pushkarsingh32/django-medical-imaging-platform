// Common types
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// Hospital types
export interface Hospital {
  id: number;
  name: string;
  address: string;
  contact_email: string;
  contact_phone: string;
  patient_count: number;
  created_at: string;
}

// Patient types
export interface Patient {
  id: number;
  medical_record_number: string;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string;
  age: number;
  gender: 'M' | 'F' | 'O';
  phone?: string;
  email?: string;
  address?: string;
  hospital: number;
  hospital_name: string;
  created_at: string;
}

export interface PatientDetail extends Patient {
  total_studies: number;
  recent_studies: ImagingStudy[];
  updated_at: string;
}

export interface CreatePatientData {
  medical_record_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: 'M' | 'F' | 'O';
  phone?: string;
  email?: string;
  address?: string;
  hospital: number;
}

// Imaging Study types
export interface ImagingStudy {
  id: number;
  patient: number;
  patient_name: string;
  patient_mrn: string;
  study_date: string;
  modality: 'CT' | 'MRI' | 'XRAY' | 'ULTRASOUND';
  body_part: string;
  status: 'pending' | 'in_progress' | 'completed' | 'archived';
  image_count: number;
  has_diagnosis: boolean;
  created_at: string;
}

export interface ImagingStudyDetail extends ImagingStudy {
  hospital: number;
  hospital_name: string;
  description?: string;
  diagnosed_at?: string;
  diagnosis?: Diagnosis;
  referring_physician?: string;
  clinical_notes?: string;
  images?: DicomImage[];
  updated_at: string;
}

// DICOM Image types
export interface DicomImage {
  id: number;
  study: number;
  instance_number: number;
  image_file: string;
  image_url: string;
  slice_thickness?: number;
  pixel_spacing?: string;
  file_size_bytes: number;
  uploaded_at: string;
}

// Diagnosis types
export interface Diagnosis {
  id: number;
  study: number;
  radiologist: number;
  radiologist_name: string;
  findings: string;
  impression: string;
  severity: 'normal' | 'minor' | 'moderate' | 'severe';
  recommendations: string;
  diagnosed_at: string;
  updated_at: string;
}

// Statistics types
export interface StudyStatistics {
  total_studies: number;
  pending: number;
  in_progress: number;
  completed: number;
  by_modality: Array<{
    modality: string;
    count: number;
  }>;
}

export interface DashboardStats {
  total_patients: number;
  total_studies: number;
  total_images: number;
  total_hospitals: number;
  new_patients_this_month: number;
  studies_this_week: number;
}

export interface StudyTrend {
  date: string;
  count: number;
}

export interface ModalityDistribution {
  modality: string;
  count: number;
}

export interface RecentActivity {
  id: number;
  modality: string;
  body_part: string;
  patient_name: string;
  hospital_name: string;
  status: string;
  study_date: string;
}

// Query params
export interface PatientQueryParams {
  search?: string;
  gender?: string;
  hospital?: number;
  page?: number;
}

export interface StudyQueryParams {
  patient?: number;
  modality?: string;
  status?: string;
  page?: number;
}
