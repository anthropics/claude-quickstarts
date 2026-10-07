"use client";

import { useEffect } from "react";

/** Development removes this app's old worker; production never caches user data. */
export function RegisterServiceWorker() {
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    let disposed = false;
    let registration: ServiceWorkerRegistration | undefined;
    const update = () => { if (!disposed) void registration?.update().catch(() => {}); };
    if (process.env.NODE_ENV !== "production") {
      void (async () => {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.filter(item => {
          const worker = item.active ?? item.waiting ?? item.installing;
          return worker && new URL(worker.scriptURL).origin === window.location.origin &&
            new URL(worker.scriptURL).pathname === "/sw.js";
        }).map(item => item.unregister()));
        if ("caches" in window) {
          const keys = await caches.keys();
          await Promise.all(keys.filter(key => key.startsWith("azimuth-shell-")).map(key => caches.delete(key)));
        }
      })().catch(() => {});
      return;
    }
    void navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" }).then(item => {
      if (disposed) return;
      registration = item;
      update();
    }).catch(() => {});
    window.addEventListener("focus", update);
    return () => { disposed = true; window.removeEventListener("focus", update); };
  }, []);
  return null;
}
