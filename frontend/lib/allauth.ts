// Django-Allauth Headless API Wrapper - Modular & DRY

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_PREFIX = '/_allauth/browser/v1';

// Types
interface AuthResponse<T = any> {
  status: number;
  data: T;
  meta?: {
    session_token?: string;
    access_token?: string;
    refresh_token?: string;
    is_authenticated?: boolean;
  };
}

// Storage Helper
class StorageHelper {
  static get(key: string): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(key);
  }

  static set(key: string, value: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem(key, value);
    }
  }

  static remove(key: string): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem(key);
    }
  }

  static clear(keys: string[]): void {
    keys.forEach(key => this.remove(key));
  }
}

// HTTP Client
class HttpClient {
  constructor(private getToken: () => string | null) {}

  async request<T>(endpoint: string, method: string = 'GET', body?: any): Promise<AuthResponse<T>> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    const token = this.getToken();
    if (token) {
      headers['X-Session-Token'] = token;
    }

    const response = await fetch(`${API_BASE}${API_PREFIX}${endpoint}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'include',
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.errors?.[0]?.message || `Request failed with status ${response.status}`
      );
    }

    return {
      status: response.status,
      data: data.data,
      meta: data.meta,
    };
  }
}

// Auth Module
class AuthModule {
  constructor(private client: HttpClient, private onTokenUpdate: (token: string) => void) {}

  async signup(email: string, password: string) {
    const response = await this.client.request('/auth/signup', 'POST', { email, password });
    this.handleTokenUpdate(response);
    return response;
  }

  async login(email: string, password: string) {
    const response = await this.client.request('/auth/login', 'POST', { email, password });
    this.handleTokenUpdate(response);
    return response;
  }

  async logout() {
    const response = await this.client.request('/auth/session', 'DELETE');
    return response;
  }

  async getSession() {
    return this.client.request('/auth/session', 'GET');
  }

  async getProviders() {
    return this.client.request('/auth/providers', 'GET');
  }

  async redirectToProvider(provider: string, callbackUrl: string) {
    return this.client.request('/auth/provider/redirect', 'POST', {
      provider,
      callback_url: callbackUrl,
      process: 'login',
    });
  }

  private handleTokenUpdate(response: AuthResponse) {
    if (response.meta?.session_token) {
      this.onTokenUpdate(response.meta.session_token);
    }
  }
}

// Email Module
class EmailModule {
  constructor(private client: HttpClient) {}

  async verify(key: string) {
    return this.client.request('/auth/email/verify', 'POST', { key });
  }

  async requestVerification(email: string) {
    return this.client.request('/account/email', 'POST', { email });
  }
}

// Password Module
class PasswordModule {
  constructor(private client: HttpClient) {}

  async requestReset(email: string) {
    return this.client.request('/auth/password/reset', 'POST', { email });
  }

  async resetWithKey(key: string, password: string) {
    return this.client.request('/auth/password/reset', 'POST', { key, password });
  }

  async change(currentPassword: string, newPassword: string) {
    return this.client.request('/account/password/change', 'POST', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}

// MFA Module
class MFAModule {
  constructor(private client: HttpClient) {}

  // TOTP
  totp = {
    activate: () => this.client.request('/mfa/authenticators/totp', 'POST'),
    get: () => this.client.request('/mfa/authenticators/totp', 'GET'),
    deactivate: () => this.client.request('/mfa/authenticators/totp', 'DELETE'),
  };

  // Recovery Codes
  recoveryCodes = {
    get: () => this.client.request('/mfa/authenticators/recovery-codes', 'GET'),
    generate: () => this.client.request('/mfa/authenticators/recovery-codes', 'POST'),
  };

  async authenticate(code: string) {
    return this.client.request('/auth/2fa/authenticate', 'POST', { code });
  }
}

// Main API Class
export class AllauthAPI {
  private sessionToken: string | null = null;
  private client: HttpClient;

  // Modules
  auth: AuthModule;
  email: EmailModule;
  password: PasswordModule;
  mfa: MFAModule;

  constructor() {
    this.client = new HttpClient(() => this.sessionToken);

    this.auth = new AuthModule(this.client, (token) => this.updateToken(token));
    this.email = new EmailModule(this.client);
    this.password = new PasswordModule(this.client);
    this.mfa = new MFAModule(this.client);
  }

  // Session Management
  initialize() {
    this.sessionToken = StorageHelper.get('session_token');
  }

  private updateToken(token: string) {
    this.sessionToken = token;
    StorageHelper.set('session_token', token);
  }

  clearSession() {
    this.sessionToken = null;
    StorageHelper.clear(['session_token', 'access_token', 'refresh_token']);
  }
}

// Export singleton instance
export const allauth = new AllauthAPI();
