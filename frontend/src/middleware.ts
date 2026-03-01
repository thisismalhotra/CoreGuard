import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Allow static assets and API routes
  if (pathname.startsWith("/_next") || pathname.startsWith("/api") || pathname.includes(".")) {
    return NextResponse.next();
  }

  // Check for token in URL param (OAuth redirect lands on / with ?token=)
  const urlToken = request.nextUrl.searchParams.get("token");
  if (urlToken) {
    return NextResponse.next();
  }

  // Note: We use localStorage for JWT storage, so middleware cannot validate
  // tokens server-side. The real auth protection comes from:
  // 1. AuthProvider — redirects to /login client-side if no token or token is invalid
  // 2. Backend — returns 401 on every API call without valid JWT
  // 3. api.ts — redirects to /login on 401 response
  // If cookie-based auth is added later, server-side validation can happen here.
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
