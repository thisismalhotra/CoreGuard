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

  // Allow OAuth callback with auth code (code exchange happens client-side)
  const authCode = request.nextUrl.searchParams.get("code");
  if (authCode) {
    return NextResponse.next();
  }

  // Check for auth indicator cookie set by AuthProvider after successful login.
  // This is NOT a security gate (JWT validation happens backend-side on every API call).
  // It prevents SSR pages from flashing unauthenticated content before the
  // client-side AuthProvider redirects.
  const hasAuth = request.cookies.get("cg_auth");
  if (!hasAuth) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
