"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { compassHeading, type CompassSample } from "@/lib/compass";

type CompassStatus = "off" | "waiting" | "live" | "denied" | "unavailable";
type PermissionConstructor = typeof DeviceOrientationEvent & {
  requestPermission?: (absolute?: boolean) => Promise<string>;
};

export function MobileCompass() {
  const [status, setStatus] = useState<CompassStatus>("off");
  const [heading, setHeading] = useState<number | null>(null);
  const stop = useRef<(() => void) | null>(null);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => { active.current = false; stop.current?.(); };
  }, []);

  async function enable() {
    stop.current?.();
    setHeading(null);
    if (!window.isSecureContext || typeof DeviceOrientationEvent === "undefined") {
      setStatus("unavailable");
      return;
    }
    setStatus("waiting");
    try {
      const orientation = DeviceOrientationEvent as PermissionConstructor;
      if (orientation.requestPermission && await orientation.requestPermission(true) !== "granted") {
        if (active.current) setStatus("denied");
        return;
      }
    } catch {
      if (active.current) setStatus("denied");
      return;
    }
    if (!active.current) return;
    let timer: number;
    const invalidate = () => { setHeading(null); setStatus("unavailable"); };
    const armExpiry = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(invalidate, 5000);
    };
    const visibility = () => {
      invalidate();
      window.clearTimeout(timer);
      if (!document.hidden) armExpiry();
    };
    const receive = (event: Event) => {
      const sample = event as DeviceOrientationEvent & CompassSample;
      if (document.hidden) return;
      // Android can deliver both relative and absolute events. Ignore relative
      // events rather than erasing the valid heading from the absolute stream.
      if (!sample.absolute && sample.webkitCompassHeading == null) return;
      const value = compassHeading(sample,
        window.screen.orientation?.angle ?? (typeof window.orientation === "number" ? window.orientation : 0));
      if (value == null) {
        setHeading(null);
        setStatus("unavailable");
        return;
      }
      armExpiry();
      setHeading(Math.round(value) % 360);
      setStatus("live");
    };
    window.addEventListener("deviceorientation", receive);
    window.addEventListener("deviceorientationabsolute", receive);
    document.addEventListener("visibilitychange", visibility);
    armExpiry();
    stop.current = () => {
      window.removeEventListener("deviceorientation", receive);
      window.removeEventListener("deviceorientationabsolute", receive);
      document.removeEventListener("visibilitychange", visibility);
      window.clearTimeout(timer);
    };
  }

  return (
    <section className="space-y-2 rounded-lg border border-border p-3" aria-label="Phone compass">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold">Phone compass</span>
        <output className="font-mono text-xl" aria-live="polite">{heading == null ? "—" : `${heading}°`}</output>
      </div>
      <Button variant="outline" className="min-h-11 w-full" onClick={enable} disabled={status === "waiting" || status === "live"}>
        {status === "live" ? "Compass active" : status === "waiting" ? "Waiting for compass…" : "Enable compass"}
      </Button>
      <p className="text-xs text-muted-foreground">
        {status === "denied" ? "Compass permission was denied. Map bearings still work." :
          status === "unavailable" ? "No reliable compass reading. Hold the phone flat in portrait orientation; map bearings still work." :
          "Hold the phone flat in portrait orientation, with its top edge pointing ahead."}
      </p>
      <p className="text-xs text-muted-foreground">Sensor north may differ from the map’s true north. Use this as an orientation aid, not confirmation of antenna alignment.</p>
    </section>
  );
}
