import { NextResponse, type NextRequest } from "next/server";

/**
 * Gate on every `/api/*` route. The routes spend this machine's Anthropic
 * credentials and have no login, so the one thing they can check is that the
 * request came from this app's own page.
 *
 * Two attacks this stops, both from a web page open in the same browser while
 * `next dev` is running:
 *
 * - A cross-site POST. `fetch("http://localhost:3000/api/session", { method:
 *   "POST", mode: "no-cors" })` needs no preflight, and the route parses the
 *   body whatever its content type, so any site could create sessions here.
 *   A browser always sends `Origin` on a cross-origin POST, and it will not
 *   match `Host`.
 * - DNS rebinding. The attacker's hostname is pointed at 127.0.0.1, which
 *   makes their page same-origin with this server, so `Origin` matches. The
 *   `Host` header still carries their hostname, and it is not on the list.
 */

const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

// Hostnames this app is served from besides loopback, for example
// ALLOWED_HOSTS=trips.example.com. Compared without the port.
const allowedHosts = new Set(
  (process.env.ALLOWED_HOSTS ?? "")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean),
);

function hostname(hostHeader: string): string {
  // "[::1]:3000" keeps its brackets, "localhost:3000" loses its port.
  return hostHeader.toLowerCase().replace(/:\d+$/, "");
}

function refuse(reason: string): NextResponse {
  return NextResponse.json({ error: reason }, { status: 403 });
}

export function proxy(request: NextRequest): NextResponse {
  const host = request.headers.get("host") ?? "";
  const name = hostname(host);
  if (!LOOPBACK.has(name) && !allowedHosts.has(name)) {
    return refuse("Host is not allowed. Set ALLOWED_HOSTS to serve this app from another hostname.");
  }

  const origin = request.headers.get("origin");
  if (origin !== null) {
    let originHost: string;
    try {
      originHost = new URL(origin).host.toLowerCase();
    } catch {
      return refuse("Origin is not a URL.");
    }
    if (originHost !== host.toLowerCase()) return refuse("Cross-origin requests are not allowed.");
  }

  // Browsers that send Fetch Metadata say outright when another site made the
  // request. This also covers a cross-site GET to /api/stream, which carries
  // no Origin when it is a plain navigation or an <img>.
  if (request.headers.get("sec-fetch-site") === "cross-site") {
    return refuse("Cross-site requests are not allowed.");
  }

  return NextResponse.next();
}

export const config = { matcher: "/api/:path*" };
