"use client";

import { RefreshCw, WifiOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ShadowProbeResponse } from "@/lib/types";

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

const BADGE_VARIANT: Record<"low" | "medium" | "high", "muted" | "outline" | "default"> = {
  low: "muted",
  medium: "outline",
  high: "default",
};

export function ShadowReadout({
  result,
  onRetry,
  retrying,
}: {
  result: ShadowProbeResponse;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const captureTime = new Date(result.captureDatetime);
  const offline = typeof navigator !== "undefined" && navigator.onLine === false;

  return (
    <Card>
      <CardContent className="space-y-2 p-4 text-xs">
        <div className="flex items-baseline gap-2">
          <span className="w-14 flex-none text-[10px] uppercase tracking-wide text-muted-foreground">
            Sun
          </span>
          <span className="font-mono tabular-nums">
            az {result.sun.azimuthDeg.toFixed(1)}° · elev {result.sun.elevationDeg >= 0 ? "+" : ""}
            {result.sun.elevationDeg.toFixed(1)}° ·{" "}
            {captureTime.toISOString().slice(0, 16).replace("T", " ")} UTC (assumed)
          </span>
        </div>

        {result.error && (
          <div className="space-y-2 rounded-md border border-destructive/40 bg-destructive/10 p-2 text-destructive">
            <div className="flex items-start gap-1.5">
              {offline && <WifiOff className="mt-0.5 h-3.5 w-3.5 flex-none" />}
              <span>{offline ? "You appear to be offline — imagery can't be fetched." : result.error}</span>
            </div>
            {onRetry && (
              <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
                <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${retrying ? "animate-spin" : ""}`} />
                Try again
              </Button>
            )}
          </div>
        )}

        {!result.error && !result.found && (
          <div className="flex items-center gap-2 rounded-md border border-border bg-background p-2">
            <Badge variant="muted">no shadow</Badge>
            <span className="text-muted-foreground">
              No usable shadow found here — enter the reference height by hand instead.
            </span>
          </div>
        )}

        {result.found && (
          <div className="flex flex-wrap items-baseline gap-2 rounded-md border border-border bg-background p-2">
            <Badge variant={BADGE_VARIANT[result.confidence ?? "low"]}>
              {result.confidence} confidence
            </Badge>
            <span className="text-muted-foreground">
              shadow {formatDistance(result.shadowLengthM ?? 0)} ⇒ reference object ≈{" "}
              {result.referenceHeightM != null
                ? `${result.referenceHeightM.toFixed(1)} m`
                : "n/a — sun too low"}{" "}
              ({(result.angularErrorDeg ?? 0).toFixed(0)}° off the expected sun-shadow direction)
            </span>
          </div>
        )}

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          The height is measured only to calibrate how far this imagery leans — the
          shadow direction itself is checked against the true sun position as a
          sanity check on the measurement.
        </p>
      </CardContent>
    </Card>
  );
}
