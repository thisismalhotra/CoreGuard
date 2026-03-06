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

// Check if there's a pending auth code in the URL that needs exchanging.
// Returns the code if present (and cleans the URL), null otherwise.
function extractAuthCode(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (code) {
    // Clean the URL immediately so code isn't visible / bookmarkable
    window.history.replaceState({}, "", window.location.pathname);
    return code;
  }
  return null;
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cg_token");
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken);
  const [loading, setLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem("cg_token");
    document.cookie = "cg_auth=; path=/; max-age=0";
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  }, []);

  // On mount: exchange auth code if present, then fetch user profile
  useEffect(() => {
    const code = extractAuthCode();

    async function init() {
      let activeToken = token;

      // If we have an auth code from OAuth callback, exchange it for a JWT
      if (code) {
        try {
          const res = await fetch(`${API_BASE}/api/auth/exchange`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code }),
          });
          if (!res.ok) throw new Error("Code exchange failed");
          const data = await res.json();
          activeToken = data.token;
          localStorage.setItem("cg_token", activeToken!);
          setToken(activeToken);
        } catch {
          setLoading(false);
          return;
        }
      }

      if (!activeToken) {
        setLoading(false);
        return;
      }

      // Fetch user profile with the token
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${activeToken}` },
        });
        if (!res.ok) throw new Error("Unauthorized");
        const data = await res.json();
        setUser(data);
        // Set indicator cookie so middleware can prevent SSR flash
        document.cookie = "cg_auth=1; path=/; max-age=86400; SameSite=Lax";
      } catch {
        localStorage.removeItem("cg_token");
        document.cookie = "cg_auth=; path=/; max-age=0";
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
