import axios, { AxiosInstance } from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: true, // Send cookies for session auth
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add CSRF token for non-GET requests
        if (config.method && config.method.toLowerCase() !== 'get') {
          const csrfToken = this.getCsrfToken();
          if (csrfToken) {
            config.headers['X-CSRFToken'] = csrfToken;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        // Handle authentication errors
        if (error.response?.status === 401 || error.response?.status === 403) {
          // Only redirect if we're in the browser
          if (typeof window !== 'undefined') {
            // Save current path to redirect back after login
            const currentPath = window.location.pathname;
            window.location.href = `/auth/login?redirect=${encodeURIComponent(currentPath)}`;
          }
        }
        return Promise.reject(error);
      }
    );
  }

  private getCsrfToken(): string | null {
    if (typeof document === 'undefined') return null;
    const cookie = document.cookie
      .split('; ')
      .find(row => row.startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : null;
  }

  async get<T>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: any): Promise<T> {
    // If data is FormData, let the browser set the Content-Type header
    const config = data instanceof FormData ? {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    } : undefined;

    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async patch<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }
}

export const apiClient = new ApiClient();
