"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
  useCallback,
} from "react";
import { allauth } from "@/lib/allauth";

// Types
interface User {
  id: number;
  email: string;
  display?: string;
  has_usable_password: boolean;
  is_staff: boolean; // Can access Django admin
  is_superuser: boolean; // Has all permissions
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean; // Convenience: is_staff OR is_superuser
  isStaff: boolean; // User has staff status
  isSuperuser: boolean; // User has superuser status
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
}

// Context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Provider Component
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshSession = useCallback(async () => {
    try {
      const response = await allauth.auth.getSession();
      if ((response.data as any)?.user) {
        setUser((response.data as any).user);
      } else {
        setUser(null);
      }
    } catch (error) {
      setUser(null);
      allauth.clearSession();
    }
  }, []);

  useEffect(() => {
    // Initialize allauth and fetch session on mount
    allauth.initialize();
    refreshSession().finally(() => setIsLoading(false));
  }, [refreshSession]);

  const login = async (email: string, password: string) => {
    try {
      const response = await allauth.auth.login(email, password);
      if ((response.data as any)?.user) {
        setUser((response.data as any).user);
      }
    } catch (error) {
      throw error;
    }
  };

  const signup = async (email: string, password: string) => {
    try {
      const response = await allauth.auth.signup(email, password);
      if ((response.data as any)?.user) {
        setUser((response.data as any).user);
      }
    } catch (error) {
      throw error;
    }
  };

  const logout = async () => {
    try {
      await allauth.auth.logout();
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      allauth.clearSession();
      setUser(null);
    }
  };

  // Computed admin status values
  const isStaff = user?.is_staff ?? false;
  const isSuperuser = user?.is_superuser ?? false;
  const isAdmin = isStaff || isSuperuser;

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        isAdmin,
        isStaff,
        isSuperuser,
        login,
        signup,
        logout,
        refreshSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// Hook
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
