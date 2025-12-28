// Export all services from a single entry point
export { patientService } from './services/patientService';
export { hospitalService } from './services/hospitalService';
export { studyService } from './services/studyService';
export { statsService } from './services/statsService';
export { contactService } from './services/contactService';
export { healthService } from './services/healthService';

// Export API client (for accessing correlation ID)
export { apiClient } from './client';

// Export types
export * from './types';
