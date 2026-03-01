"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";

type User = {
  id: number;
  email: string;
  name: string;
  picture: string | null;
  role: "admin" | "operator" | "approver" | "viewer";
  is_active: boolean;
};

type AuthContextType = {
  user: User | null;
  token: string | null;
  loading: boolean;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  logout: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function hasRole(user: User | null, ...roles: string[]): boolean {
  return user !== null && roles.includes(user.role);
}

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("cg_token");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  // On mount: check for token in URL (OAuth redirect) or localStorage
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");

    if (urlToken) {
      localStorage.setItem("cg_token", urlToken);
      setToken(urlToken);
      // Clean the URL
      window.history.replaceState({}, "", window.location.pathname);
    } else {
      const stored = localStorage.getItem("cg_token");
      if (stored) {
        setToken(stored);
      } else {
        setLoading(false);
      }
    }
  }, []);

  // When token changes, fetch user profile
  useEffect(() => {
    if (!token) return;

    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Unauthorized");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem("cg_token");
        setToken(null);
        setUser(null);
        setLoading(false);
      });
  }, [token]);

  return (
    <AuthContext.Provider value={{ user, token, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
