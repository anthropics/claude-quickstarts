import { NextRequest, NextResponse } from "next/server";
import { AUTH, verifySessionToken } from "./lib/auth";

/**
 * Global auth gate (edge). Pages without a valid session redirect to /login;
 * API calls get 401 JSON. Public surface: login, auth endpoints, public
 * careers pages + apply API, and the kiosk (which does its own PIN auth).
 */
const PUBLIC_PREFIXES = [
  "/login",
  "/api/auth/login",
  "/careers",
  "/api/careers",
  "/kiosk",
  "/api/kiosk",
  "/_next",
  "/favicon.ico",
];

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next();
  }

  const token = req.cookies.get(AUTH.cookieName)?.value;
  const session = token ? await verifySessionToken(token) : null;

  if (!session) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const login = new URL("/login", req.url);
    if (pathname !== "/") login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
