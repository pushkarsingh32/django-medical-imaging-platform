import { apiClient } from '../client';

/**
 * Health check response from backend
 */
export interface HealthCheck {
  status: 'healthy' | 'unhealthy' | 'alive' | 'ready' | 'not_ready';
  checks?: {
    database: ComponentHealth;
    redis: ComponentHealth;
    celery: ComponentHealth;
    storage: ComponentHealth;
  };
  timestamp?: string;
}

export interface ComponentHealth {
  status: 'healthy' | 'unhealthy';
  details: string;
  latency_ms?: number;
  active_workers?: number;
  workers?: string[];
}

/**
 * Health Service
 *
 * Provides methods to check system health status.
 * Useful for admin dashboards and monitoring pages.
 */
class HealthService {
  /**
   * Get comprehensive system health status
   *
   * @returns Health check with all components
   *
   * Example response:
   * {
   *   "status": "healthy",
   *   "checks": {
   *     "database": { "status": "healthy", "details": "Connection successful" },
   *     "redis": { "status": "healthy", "latency_ms": 5.2 },
   *     "celery": { "status": "healthy", "active_workers": 3 },
   *     "storage": { "status": "healthy" }
   *   }
   * }
   */
  async getHealth(): Promise<HealthCheck> {
    return apiClient.get<HealthCheck>('/health/');
  }

  /**
   * Check if application is alive (liveness probe)
   *
   * Returns true if application process is running.
   * Does not check external dependencies.
   *
   * @returns True if alive, false otherwise
   */
  async isAlive(): Promise<boolean> {
    try {
      const response = await apiClient.get<HealthCheck>('/health/liveness/');
      return response.status === 'alive';
    } catch (error) {
      return false;
    }
  }

  /**
   * Check if application is ready to serve traffic (readiness probe)
   *
   * Returns true if critical services (DB, Redis) are healthy.
   *
   * @returns True if ready, false otherwise
   */
  async isReady(): Promise<boolean> {
    try {
      const response = await apiClient.get<HealthCheck>('/health/readiness/');
      return response.status === 'ready';
    } catch (error) {
      return false;
    }
  }

  /**
   * Check if all systems are healthy
   *
   * Convenience method that checks comprehensive health status.
   *
   * @returns True if all systems healthy, false otherwise
   */
  async isHealthy(): Promise<boolean> {
    try {
      const health = await this.getHealth();
      return health.status === 'healthy';
    } catch (error) {
      return false;
    }
  }

  /**
   * Get unhealthy components
   *
   * Returns list of components that are unhealthy.
   * Useful for displaying warnings in admin UI.
   *
   * @returns Array of unhealthy component names
   *
   * Example: ['database', 'celery']
   */
  async getUnhealthyComponents(): Promise<string[]> {
    try {
      const health = await this.getHealth();
      if (!health.checks) return [];

      return Object.entries(health.checks)
        .filter(([_, check]) => check.status === 'unhealthy')
        .map(([name, _]) => name);
    } catch (error) {
      return ['api']; // API itself is unreachable
    }
  }
}

export const healthService = new HealthService();
