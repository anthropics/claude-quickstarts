/**
 * Local persistence + shareable links for a survey session.
 *
 * Both encode the same shape: this is a field tool, so a session usually
 * means "one site, a handful of bearings", and losing it to a page refresh
 * or being unable to send it to someone is pure friction.
 */
import type { LatLon } from "./geometry";
import type { ImageryCalibration } from "./relief";
import type { AzimuthRay } from "./types";

export interface SessionState {
  origin: LatLon | null;
  rays: AzimuthRay[];
  calibration: ImageryCalibration | null;
  calibrationBase: LatLon | null;
  calibrationTop: LatLon | null;
  referenceHeightM: number | null;
}

const STORAGE_KEY = "antenna-azimuth-session-v1";

export function loadSession(): Partial<SessionState> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Partial<SessionState>) : null;
  } catch {
    // Corrupt or unavailable storage should never break the app.
    return null;
  }
}

export function saveSession(state: SessionState): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private mode / quota — not worth surfacing.
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Encode a session into a URL fragment.
 *
 * The fragment rather than the query string: it never reaches the server, so
 * a shared link doesn't put someone's position in access logs.
 */
export function encodeSession(state: SessionState): string {
  const json = JSON.stringify(state);
  const b64 =
    typeof window === "undefined"
      ? Buffer.from(json, "utf8").toString("base64")
      : window.btoa(unescape(encodeURIComponent(json)));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function decodeSession(fragment: string): Partial<SessionState> | null {
  if (!fragment) return null;
  try {
    const b64 = fragment.replace(/-/g, "+").replace(/_/g, "/");
    const json =
      typeof window === "undefined"
        ? Buffer.from(b64, "base64").toString("utf8")
        : decodeURIComponent(escape(window.atob(b64)));
    return JSON.parse(json) as Partial<SessionState>;
  } catch {
    return null;
  }
}

export function shareUrl(state: SessionState): string {
  const base = typeof window === "undefined" ? "" : window.location.origin + window.location.pathname;
  return `${base}#s=${encodeSession(state)}`;
}
