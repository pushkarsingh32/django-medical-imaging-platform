import { apiClient } from '../client';

export interface ContactFormData {
  name: string;
  email: string;
  phone?: string;
  subject: string;
  message: string;
}

export interface ContactResponse {
  success: boolean;
  message: string;
  data: {
    id: number;
    name: string;
    email: string;
    phone: string;
    subject: string;
    message: string;
    created_at: string;
  };
}

export const contactService = {
  /**
   * Submit contact form
   */
  submitContact: (data: ContactFormData): Promise<ContactResponse> => {
    return apiClient.post('/contact/', data);
  },
};
