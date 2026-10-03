"use client";

import { Crosshair, Plus, Trash2 } from "lucide-react";

import type { MarkMode } from "@/components/CalibrationPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { haversineDistanceM, type LatLon } from "@/lib/geometry";
import { correctedAzimuth, type ImageryCalibration } from "@/lib/relief";
import { RAY_COLORS, type AzimuthRay } from "@/lib/types";

export type GpsStatus = "idle" | "watching" | "denied" | "unsupported" | "error";

interface AzimuthControlsProps {
  rays: AzimuthRay[];
  onRaysChange: (rays: AzimuthRay[]) => void;
  origin: LatLon | null;
  gpsStatus: GpsStatus;
  gpsAccuracyM: number | null;
  headingDeg: number | null;
  manualOverride: boolean;
  onManualOriginChange: (origin: LatLon) => void;
  onUseLiveGps: () => void;
  calibration: ImageryCalibration | null;
  markMode: MarkMode;
  onPickTarget: (rayId: string) => void;
  pickingRayId: string | null;
}

function newRay(index: number): AzimuthRay {
  return {
    id: crypto.randomUUID(),
    azimuthDeg: 0,
    distanceM: 1000,
    beamwidthDeg: null,
    label: `Ray ${index + 1}`,
  };
}

const GPS_STATUS_TEXT: Record<GpsStatus, string> = {
  idle: "Waiting for GPS…",
  watching: "Live GPS",
  denied: "Location permission denied",
  unsupported: "Geolocation not supported by this browser",
  error: "Could not get a GPS fix",
};

export function AzimuthControls({
  rays,
  onRaysChange,
  origin,
  gpsStatus,
  gpsAccuracyM,
  headingDeg,
  manualOverride,
  onManualOriginChange,
  onUseLiveGps,
  calibration,
  markMode,
  onPickTarget,
  pickingRayId,
}: AzimuthControlsProps) {
  function updateRay(id: string, patch: Partial<AzimuthRay>) {
    onRaysChange(rays.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  function removeRay(id: string) {
    onRaysChange(rays.filter((r) => r.id !== id));
  }

  const gpsOk = gpsStatus === "watching" && !manualOverride;

  return (
    <div className="flex flex-col gap-4 p-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center justify-between text-sm">
            <span>Position</span>
            <span
              className={
                "text-[11px] font-normal " + (gpsOk ? "text-brand" : "text-muted-foreground")
              }
            >
              {manualOverride ? "Manual override" : GPS_STATUS_TEXT[gpsStatus]}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label htmlFor="lat">Latitude</Label>
              <Input
                id="lat"
                type="number"
                step="0.000001"
                value={origin ? origin.lat.toFixed(6) : ""}
                onChange={(e) =>
                  onManualOriginChange({ lat: Number(e.target.value), lon: origin?.lon ?? 0 })
                }
              />
            </div>
            <div>
              <Label htmlFor="lon">Longitude</Label>
              <Input
                id="lon"
                type="number"
                step="0.000001"
                value={origin ? origin.lon.toFixed(6) : ""}
                onChange={(e) =>
                  onManualOriginChange({ lat: origin?.lat ?? 0, lon: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>
              {gpsAccuracyM ? `Accuracy ~${Math.round(gpsAccuracyM)} m` : " "}
              {headingDeg != null && ` · facing ${Math.round(headingDeg)}°`}
            </span>
            {manualOverride && (
              <Button variant="link" size="sm" className="h-auto p-0 text-[11px]" onClick={onUseLiveGps}>
                Use live GPS instead
              </Button>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Tip: drag the white marker on the map to reposition it.
          </p>
        </CardContent>
      </Card>

      <Card className="flex-1">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Azimuths</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {rays.map((ray, i) => {
            const color = RAY_COLORS[i % RAY_COLORS.length];
            const correction =
              ray.target && origin
                ? correctedAzimuth(origin, ray.target.apparent, ray.target.heightM, calibration)
                : null;
            const rangeM =
              ray.target && origin ? haversineDistanceM(origin, ray.target.apparent) : null;

            return (
              <div key={ray.id} className="rounded-lg border border-border p-3">
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 flex-none rounded-full"
                    style={{ background: color }}
                  />
                  <Input
                    className="h-7 border-0 bg-transparent px-1 font-sans text-sm shadow-none"
                    value={ray.label}
                    onChange={(e) => updateRay(ray.id, { label: e.target.value })}
                    placeholder="Label"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 flex-none"
                    onClick={() => removeRay(ray.id)}
                    aria-label={`Remove ${ray.label}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>

                {ray.target ? (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <Label htmlFor={`h-${ray.id}`}>Target height m</Label>
                        <Input
                          id={`h-${ray.id}`}
                          type="number"
                          min={0}
                          value={ray.target.heightM}
                          onChange={(e) =>
                            updateRay(ray.id, {
                              target: { ...ray.target!, heightM: Number(e.target.value) },
                            })
                          }
                        />
                      </div>
                      <div>
                        <Label>Range</Label>
                        <div className="flex h-9 items-center font-mono text-sm tabular-nums">
                          {rangeM != null
                            ? rangeM >= 1000
                              ? `${(rangeM / 1000).toFixed(2)} km`
                              : `${Math.round(rangeM)} m`
                            : "—"}
                        </div>
                      </div>
                    </div>

                    {correction && (
                      <div className="space-y-0.5 rounded-md border border-border bg-background p-2 font-mono text-[11px] tabular-nums">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">as picked</span>
                          <span>{correction.rawDeg.toFixed(2)}°</span>
                        </div>
                        <div className="flex justify-between font-semibold text-brand">
                          <span>corrected</span>
                          <span>{correction.correctedDeg.toFixed(2)}°</span>
                        </div>
                        <div className="flex justify-between text-muted-foreground">
                          <span>Δ</span>
                          <span>
                            {correction.deltaDeg >= 0 ? "+" : ""}
                            {correction.deltaDeg.toFixed(2)}°
                          </span>
                        </div>
                      </div>
                    )}
                    {!calibration && (
                      <p className="text-[11px] text-muted-foreground">
                        Calibrate the imagery above to correct this bearing.
                      </p>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-auto p-0 text-[11px]"
                      onClick={() => updateRay(ray.id, { target: undefined })}
                    >
                      Use a typed azimuth instead
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <Label htmlFor={`az-${ray.id}`}>Azimuth °</Label>
                        <Input
                          id={`az-${ray.id}`}
                          type="number"
                          value={ray.azimuthDeg}
                          onChange={(e) => updateRay(ray.id, { azimuthDeg: Number(e.target.value) })}
                        />
                      </div>
                      <div>
                        <Label htmlFor={`dist-${ray.id}`}>Distance m</Label>
                        <Input
                          id={`dist-${ray.id}`}
                          type="number"
                          value={ray.distanceM}
                          onChange={(e) => updateRay(ray.id, { distanceM: Number(e.target.value) })}
                        />
                      </div>
                      <div>
                        <Label htmlFor={`bw-${ray.id}`}>Beamwidth °</Label>
                        <Input
                          id={`bw-${ray.id}`}
                          type="number"
                          placeholder="line"
                          value={ray.beamwidthDeg ?? ""}
                          onChange={(e) =>
                            updateRay(ray.id, {
                              beamwidthDeg: e.target.value === "" ? null : Number(e.target.value),
                            })
                          }
                        />
                      </div>
                    </div>
                    <Button
                      variant={markMode === "target" && pickingRayId === ray.id ? "brand" : "outline"}
                      size="sm"
                      className="w-full"
                      onClick={() => onPickTarget(ray.id)}
                    >
                      <Crosshair className="mr-1.5 h-3.5 w-3.5" />
                      {markMode === "target" && pickingRayId === ray.id
                        ? "Click the target on the map…"
                        : "Pick target on map"}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => onRaysChange([...rays, newRay(rays.length)])}
          >
            <Plus className="mr-1.5 h-3.5 w-3.5" />
            Add azimuth
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
