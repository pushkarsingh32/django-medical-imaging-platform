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

        // Add correlation ID for distributed tracing
        // Check if correlation ID already exists in session storage
        let correlationId = this.getCorrelationId();
        if (!correlationId) {
          // Generate new correlation ID (simple UUID v4)
          correlationId = this.generateCorrelationId();
          this.setCorrelationId(correlationId);
        }
        config.headers['X-Correlation-ID'] = correlationId;

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        // Capture correlation ID from response headers for tracing
        const correlationId = response.headers['x-correlation-id'];
        if (correlationId) {
          this.setCorrelationId(correlationId);
        }
        return response;
      },
      (error) => {
        // Capture correlation ID from error response for debugging
        const correlationId = error.response?.headers?.['x-correlation-id'];
        if (correlationId) {
          this.setCorrelationId(correlationId);
          // Log error with correlation ID for easier debugging
          console.error(`[Correlation ID: ${correlationId}] API Error:`, {
            url: error.config?.url,
            method: error.config?.method,
            status: error.response?.status,
            message: error.response?.data?.message || error.message
          });
        }

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

  /**
   * Generate a simple UUID v4 for correlation ID.
   * Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
   */
  private generateCorrelationId(): string {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Get correlation ID from sessionStorage.
   * Session-scoped (persists during user session, cleared on tab close).
   */
  private getCorrelationId(): string | null {
    if (typeof window === 'undefined') return null;
    return sessionStorage.getItem('correlation-id');
  }

  /**
   * Set correlation ID in sessionStorage.
   * Used to track requests across the user's session.
   */
  private setCorrelationId(correlationId: string): void {
    if (typeof window === 'undefined') return;
    sessionStorage.setItem('correlation-id', correlationId);
  }

  /**
   * Get current correlation ID for debugging/logging.
   * Useful for displaying in UI (e.g., error messages).
   */
  public getCurrentCorrelationId(): string | null {
    return this.getCorrelationId();
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
