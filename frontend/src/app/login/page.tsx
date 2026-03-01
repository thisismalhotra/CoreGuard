"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Shield } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function LoginPage() {
  const { user, loading } = useAuth();

  // If already logged in, redirect to home
  useEffect(() => {
    if (!loading && user) {
      window.location.href = "/";
    }
  }, [user, loading]);

  const errorParam = typeof window !== "undefined"
    ? new URLSearchParams(window.location.search).get("error")
    : null;

  const handleLogin = () => {
    window.location.href = `${API_BASE}/api/auth/login`;
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-2xl">Core-Guard</CardTitle>
          <p className="text-sm text-muted-foreground">
            Autonomous Supply Chain Operating System
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {errorParam && (
            <p className="text-center text-sm text-destructive">
              Login failed. Please try again.
            </p>
          )}
          <Button onClick={handleLogin} className="w-full" size="lg">
            Sign in with Google
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
