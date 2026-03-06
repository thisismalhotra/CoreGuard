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

// Extract initial token synchronously so it's available before any child effects run.
// This prevents the race condition where CommandCenter's useEffect fires API calls
// before the token is saved to localStorage.
function getInitialToken(): string | null {
  if (typeof window === "undefined") return null;

  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get("token");

  if (urlToken) {
    localStorage.setItem("cg_token", urlToken);
    // Clean the URL so token isn't visible / bookmarkable
    window.history.replaceState({}, "", window.location.pathname);
    return urlToken;
  }

  return localStorage.getItem("cg_token");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getInitialToken);
  // If there's no token at init, we already know there's no user — skip loading state
  const [loading, setLoading] = useState(() => getInitialToken() !== null);

  const logout = useCallback(() => {
    localStorage.removeItem("cg_token");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
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
