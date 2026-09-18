"use client";

import { useEffect } from "react";

/**
 * Registers the app-shell service worker in production only — in dev it would
 * shadow Next's hot-reload responses.
 */
export function RegisterServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Registration failures are not worth interrupting the user over.
    });
  }, []);
  return null;
}
