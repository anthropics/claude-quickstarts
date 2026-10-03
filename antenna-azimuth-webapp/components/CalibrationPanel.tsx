"use client";

import { Crosshair, Loader2, Ruler, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { LatLon } from "@/lib/geometry";
import type { ImageryCalibration } from "@/lib/relief";
import type { ShadowProbeResponse } from "@/lib/types";

export type MarkMode = "none" | "base" | "top" | "target";

interface CalibrationPanelProps {
  base: LatLon | null;
  top: LatLon | null;
  heightM: number | null;
  calibration: ImageryCalibration | null;
  markMode: MarkMode;
  onMarkModeChange: (mode: MarkMode) => void;
  onHeightChange: (heightM: number | null) => void;
  onClear: () => void;
  onMeasureShadow: () => void;
  probing: boolean;
  probe: ShadowProbeResponse | null;
}

function fmt(n: number, digits = 1) {
  return n.toFixed(digits);
}

export function CalibrationPanel({
  base,
  top,
  heightM,
  calibration,
  markMode,
  onMarkModeChange,
  onHeightChange,
  onClear,
  onMeasureShadow,
  probing,
  probe,
}: CalibrationPanelProps) {
  const markButton = (mode: Exclude<MarkMode, "none" | "target">, label: string, set: boolean) => (
    <Button
      variant={markMode === mode ? "brand" : set ? "secondary" : "outline"}
      size="sm"
      className="flex-1"
      onClick={() => onMarkModeChange(markMode === mode ? "none" : mode)}
    >
      <Crosshair className="mr-1.5 h-3.5 w-3.5" />
      {markMode === mode ? "Click map…" : label}
    </Button>
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-sm">
          <span>Imagery calibration</span>
          {calibration && <Badge>calibrated</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Tall things lean in satellite imagery, away from the satellite. Mark one
          upright object&rsquo;s base and its apparent top to measure that lean, and
          bearings to elevated targets get corrected for it.
        </p>

        <div className="flex gap-2">
          {markButton("base", base ? "Base ✓" : "Mark base", Boolean(base))}
          {markButton("top", top ? "Top ✓" : "Mark top", Boolean(top))}
        </div>

        <div className="flex items-end gap-2">
          <div className="flex-1">
            <Label htmlFor="ref-height">Object height m</Label>
            <Input
              id="ref-height"
              type="number"
              min={1}
              placeholder="e.g. 30"
              value={heightM ?? ""}
              onChange={(e) => onHeightChange(e.target.value === "" ? null : Number(e.target.value))}
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onMeasureShadow}
            disabled={probing || !base}
            title={base ? "Measure the object's shadow to get its height" : "Mark the base first"}
          >
            {probing ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Ruler className="mr-1.5 h-3.5 w-3.5" />
            )}
            From shadow
          </Button>
        </div>

        {probe && !probe.found && !probe.error && (
          <p className="text-[11px] text-muted-foreground">
            No usable shadow found near the base — enter the height manually instead.
          </p>
        )}
        {probe?.error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-[11px] text-destructive">
            {probe.error}
          </p>
        )}
        {probe?.found && probe.referenceHeightM != null && (
          <p className="text-[11px] text-muted-foreground">
            Shadow {fmt(probe.shadowLengthM ?? 0)} m with the sun{" "}
            {fmt(probe.sun.elevationDeg)}° up ⇒ {fmt(probe.referenceHeightM)} m (
            {probe.confidence} confidence).
          </p>
        )}

        {calibration ? (
          <div className="space-y-1 rounded-md border border-border bg-background p-2 font-mono text-[11px] tabular-nums">
            <div>
              lean {fmt(calibration.leanPerMetre, 2)} m per m, toward{" "}
              {fmt(calibration.displacementBearingDeg)}°
            </div>
            <div className="text-muted-foreground">
              satellite {fmt(calibration.satelliteElevationDeg)}° up at{" "}
              {fmt(calibration.satelliteAzimuthDeg)}° ·{" "}
              {fmt(90 - calibration.satelliteElevationDeg)}° off-nadir
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-muted-foreground">
            Needs a base, a top and a height.
          </p>
        )}

        {(base || top || heightM) && (
          <Button variant="ghost" size="sm" className="h-auto p-0 text-[11px]" onClick={onClear}>
            <X className="mr-1 h-3 w-3" />
            Clear calibration
          </Button>
        )}

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          Only valid for this patch of imagery, and only affects targets above
          ground — a target at ground level needs no correction, and the error
          shrinks toward nothing with distance.
        </p>
      </CardContent>
    </Card>
  );
}
