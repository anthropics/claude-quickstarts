"use client";

import { Check, Link as LinkIcon, Loader2, Radar } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AzimuthControls, type GpsStatus } from "@/components/AzimuthControls";
import { CalibrationPanel, type MarkMode } from "@/components/CalibrationPanel";
import { ShadowReadout } from "@/components/ShadowReadout";
import { Button } from "@/components/ui/button";
import { haversineDistanceM, type LatLon } from "@/lib/geometry";
import { decodeSession, loadSession, saveSession, shareUrl, type SessionState } from "@/lib/persist";
import { calibrateFromReference, type ImageryCalibration } from "@/lib/relief";
import type { AzimuthRay, ShadowProbeResponse } from "@/lib/types";

const AzimuthMap = dynamic(() => import("@/components/AzimuthMap"), { ssr: false });

/**
 * Ignore GPS fixes that haven't actually moved. A high-accuracy watch reports
 * a new position roughly once a second and consumer GPS jitters by well under
 * a metre between fixes, so without this the map re-renders (and every ray is
 * re-projected) continuously while standing still.
 */
const MIN_GPS_MOVE_M = 0.5;

function defaultRays(): AzimuthRay[] {
  return [
    {
      id: typeof crypto !== "undefined" ? crypto.randomUUID() : "ray-1",
      azimuthDeg: 45,
      distanceM: 1000,
      beamwidthDeg: null,
      label: "Ray 1",
    },
  ];
}

export default function Home() {
  const [liveOrigin, setLiveOrigin] = useState<LatLon | null>(null);
  const [manualOrigin, setManualOrigin] = useState<LatLon | null>(null);
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>("idle");
  const [gpsAccuracyM, setGpsAccuracyM] = useState<number | null>(null);
  const [headingDeg, setHeadingDeg] = useState<number | null>(null);
  const [rays, setRays] = useState<AzimuthRay[]>(defaultRays);
  const [probe, setProbe] = useState<ShadowProbeResponse | null>(null);
  const [probing, setProbing] = useState(false);
  const [copied, setCopied] = useState(false);

  const [markMode, setMarkMode] = useState<MarkMode>("none");
  const [pickingRayId, setPickingRayId] = useState<string | null>(null);
  const [calibrationBase, setCalibrationBase] = useState<LatLon | null>(null);
  const [calibrationTop, setCalibrationTop] = useState<LatLon | null>(null);
  const [referenceHeightM, setReferenceHeightM] = useState<number | null>(null);

  const restored = useRef(false);

  // Restore from a shared link if present, otherwise from the last session.
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    const fragment = window.location.hash.startsWith("#s=") ? window.location.hash.slice(3) : "";
    const state = decodeSession(fragment) ?? loadSession();
    if (!state) return;
    if (state.rays?.length) setRays(state.rays);
    if (state.origin) setManualOrigin(state.origin);
    if (state.calibrationBase) setCalibrationBase(state.calibrationBase);
    if (state.calibrationTop) setCalibrationTop(state.calibrationTop);
    if (state.referenceHeightM != null) setReferenceHeightM(state.referenceHeightM);
  }, []);

  useEffect(() => {
    if (typeof navigator === "undefined" || !("geolocation" in navigator)) {
      setGpsStatus("unsupported");
      return;
    }
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        setLiveOrigin((prev) =>
          prev && haversineDistanceM(prev, next) < MIN_GPS_MOVE_M ? prev : next
        );
        // Rounded because it's displayed to the metre — keeping the raw float
        // would re-render on every fix even when nothing visibly changed.
        setGpsAccuracyM(Math.round(pos.coords.accuracy));
        if (pos.coords.heading != null && !Number.isNaN(pos.coords.heading)) {
          setHeadingDeg(Math.round(pos.coords.heading));
        }
        setGpsStatus("watching");
      },
      (err) => {
        setGpsStatus(err.code === err.PERMISSION_DENIED ? "denied" : "error");
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  const origin = manualOrigin ?? liveOrigin;

  const calibration: ImageryCalibration | null = useMemo(() => {
    if (!calibrationBase || !calibrationTop || !referenceHeightM) return null;
    return calibrateFromReference({
      base: calibrationBase,
      top: calibrationTop,
      heightM: referenceHeightM,
    });
  }, [calibrationBase, calibrationTop, referenceHeightM]);

  const sessionState: SessionState = useMemo(
    () => ({
      origin,
      rays,
      calibration,
      calibrationBase,
      calibrationTop,
      referenceHeightM,
    }),
    [origin, rays, calibration, calibrationBase, calibrationTop, referenceHeightM]
  );

  useEffect(() => {
    saveSession(sessionState);
  }, [sessionState]);

  const handleUseLiveGps = useCallback(() => setManualOrigin(null), []);

  const handlePick = useCallback(
    (mode: Exclude<MarkMode, "none">, at: LatLon) => {
      if (mode === "base") setCalibrationBase(at);
      else if (mode === "top") setCalibrationTop(at);
      else if (mode === "target" && pickingRayId) {
        setRays((prev) =>
          prev.map((r) =>
            r.id === pickingRayId ? { ...r, target: { apparent: at, heightM: r.target?.heightM ?? 20 } } : r
          )
        );
        setPickingRayId(null);
      }
      setMarkMode("none");
    },
    [pickingRayId]
  );

  const handlePickTarget = useCallback(
    (rayId: string) => {
      if (markMode === "target" && pickingRayId === rayId) {
        setMarkMode("none");
        setPickingRayId(null);
      } else {
        setMarkMode("target");
        setPickingRayId(rayId);
      }
    },
    [markMode, pickingRayId]
  );

  const runProbe = useCallback(async () => {
    const at = calibrationBase ?? origin;
    if (!at) return;
    setProbing(true);
    try {
      const resp = await fetch("/api/shadow-estimate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ lat: at.lat, lon: at.lon }),
      });
      const data: ShadowProbeResponse = await resp.json();
      setProbe(data);
      if (data.found && data.referenceHeightM != null && referenceHeightM == null) {
        setReferenceHeightM(Number(data.referenceHeightM.toFixed(1)));
      }
    } catch (err) {
      setProbe({
        found: false,
        sun: { azimuthDeg: 0, elevationDeg: 0 },
        captureDatetime: new Date().toISOString(),
        error: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setProbing(false);
    }
  }, [calibrationBase, origin, referenceHeightM]);

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl(sessionState));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — nothing useful to say */
    }
  }, [sessionState]);

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      <div className="relative h-[45vh] p-3 md:h-full md:flex-1 md:p-4">
        <AzimuthMap
          origin={origin}
          rays={rays}
          shadowProbe={probe}
          calibration={calibration}
          calibrationBase={calibrationBase}
          calibrationTop={calibrationTop}
          markMode={markMode}
          onPick={handlePick}
          onOriginMove={setManualOrigin}
        />
      </div>

      <aside className="flex min-h-0 flex-1 flex-col overflow-y-auto border-t border-border md:h-full md:w-[400px] md:flex-none md:border-l md:border-t-0">
        <div className="flex flex-none items-start justify-between gap-2 border-b border-border px-4 py-3">
          <div>
            <h1 className="text-sm font-bold uppercase tracking-wide text-brand">Azimuth Mapper</h1>
            <p className="text-[11px] text-muted-foreground">
              Live GPS + satellite azimuth, corrected for imagery lean
            </p>
          </div>
          <Button variant="ghost" size="sm" onClick={handleCopyLink} title="Copy a link to this session">
            {copied ? <Check className="h-3.5 w-3.5" /> : <LinkIcon className="h-3.5 w-3.5" />}
          </Button>
        </div>

        <div className="flex flex-col gap-4 p-4 pb-0">
          <CalibrationPanel
            base={calibrationBase}
            top={calibrationTop}
            heightM={referenceHeightM}
            calibration={calibration}
            markMode={markMode}
            onMarkModeChange={setMarkMode}
            onHeightChange={setReferenceHeightM}
            onClear={() => {
              setCalibrationBase(null);
              setCalibrationTop(null);
              setReferenceHeightM(null);
              setProbe(null);
            }}
            onMeasureShadow={runProbe}
            probing={probing}
            probe={probe}
          />
        </div>

        <AzimuthControls
          rays={rays}
          onRaysChange={setRays}
          origin={origin}
          gpsStatus={gpsStatus}
          gpsAccuracyM={manualOrigin ? null : gpsAccuracyM}
          headingDeg={headingDeg}
          manualOverride={manualOrigin !== null}
          onManualOriginChange={setManualOrigin}
          onUseLiveGps={handleUseLiveGps}
          calibration={calibration}
          markMode={markMode}
          onPickTarget={handlePickTarget}
          pickingRayId={pickingRayId}
        />

        <div className="flex-none space-y-3 px-4 pb-4">
          {!probe && (
            <Button variant="outline" className="w-full" onClick={runProbe} disabled={!origin || probing}>
              {probing ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Radar className="mr-1.5 h-4 w-4" />
              )}
              Probe imagery for a reference shadow
            </Button>
          )}
          {probe && <ShadowReadout result={probe} onRetry={runProbe} retrying={probing} />}
        </div>
      </aside>
    </main>
  );
}
