"use client";

import "leaflet/dist/leaflet.css";

import L, { type LeafletEventHandlerFnMap } from "leaflet";
import { Fragment, memo, useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";

import type { MarkMode } from "@/components/CalibrationPanel";
import { bearingBetween, destinationPoint, type LatLon } from "@/lib/geometry";
import { type ImageryCalibration, correctApparentPosition } from "@/lib/relief";
import { RAY_COLORS, type AzimuthRay, type ShadowProbeResponse } from "@/lib/types";

// Our own passthrough proxy (app/api/basemap/[z]/[x]/[y]/route.ts) — the
// browser does not need a provider API key. Source attribution and zoom
// limits are fetched from /api/basemap-meta before aerial tiles are shown.
const BASEMAP_TILE_URL = "/api/basemap/{z}/{x}/{y}";
const FALLBACK_ATTRIBUTION = "Map data © Seznam.cz, a.s. and its licensors";
const FALLBACK_MAX_ZOOM = 19;
const BASIC_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const BASIC_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

function dotIcon(color: string, size: number, opts: { ring?: boolean; grab?: boolean } = {}) {
  const { ring = true, grab = false } = opts;
  return L.divIcon({
    className: "",
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    html: `<span style="
      display:block;width:${size}px;height:${size}px;border-radius:999px;
      ${grab ? "cursor:grab;" : ""}
      background:${color};box-shadow:0 0 0 2px #fff${ring ? ", 0 0 0 4px " + color + "66" : ""}, 0 1px 4px rgba(0,0,0,.4);
    "></span>`,
  });
}

const originIcon = dotIcon("#ffffff", 18, { grab: true });
const shadowIcon = dotIcon("#ffffff", 12, { ring: false });
const baseIcon = dotIcon("#3ddc84", 12, { ring: false });
const topIcon = dotIcon("#ffd23f", 12, { ring: false });
const targetIcon = dotIcon("#c792ff", 13, { ring: false });
const correctedIcon = dotIcon("#ff6a3d", 13);

function wedgePoints(origin: LatLon, azimuthDeg: number, beamwidthDeg: number, distanceM: number) {
  const start = azimuthDeg - beamwidthDeg / 2;
  const end = azimuthDeg + beamwidthDeg / 2;
  const steps = Math.max(2, Math.round(Math.abs(beamwidthDeg) / 3));
  const points: [number, number][] = [[origin.lat, origin.lon]];
  for (let i = 0; i <= steps; i++) {
    const angle = start + ((end - start) * i) / steps;
    const dest = destinationPoint(origin, angle, distanceM);
    points.push([dest.lat, dest.lon]);
  }
  points.push([origin.lat, origin.lon]);
  return points;
}

function RecenterOnFirstFix({ origin }: { origin: LatLon | null }) {
  const map = useMap();
  const hasCentered = useRef(false);
  useEffect(() => {
    if (origin && !hasCentered.current) {
      map.setView([origin.lat, origin.lon], 18);
      hasCentered.current = true;
    }
  }, [origin, map]);
  return null;
}

function ScaleControl() {
  const map = useMap();
  useEffect(() => {
    const control = L.control.scale({ imperial: false }).addTo(map);
    return () => {
      control.remove();
    };
  }, [map]);
  return null;
}

/** Keep Leaflet sized when the status panel changes the available map height. */
function ResizeMap() {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  return null;
}

/** Routes map clicks to whichever point is currently being marked. */
function ClickCapture({
  markMode,
  onPick,
}: {
  markMode: MarkMode;
  onPick: (mode: Exclude<MarkMode, "none">, at: LatLon) => void;
}) {
  const map = useMapEvents({
    click(e) {
      if (markMode === "none") return;
      onPick(markMode, { lat: e.latlng.lat, lon: e.latlng.lng });
    },
  });
  useEffect(() => {
    const container = map.getContainer();
    container.style.cursor = markMode === "none" ? "" : "crosshair";
    return () => {
      container.style.cursor = "";
    };
  }, [map, markMode]);
  return null;
}

export interface AzimuthMapProps {
  origin: LatLon | null;
  rays: AzimuthRay[];
  shadowProbe: ShadowProbeResponse | null;
  calibration: ImageryCalibration | null;
  calibrationBase: LatLon | null;
  calibrationTop: LatLon | null;
  markMode: MarkMode;
  onPick: (mode: Exclude<MarkMode, "none">, at: LatLon) => void;
  onOriginMove?: (origin: LatLon) => void;
  onImageryAvailabilityChange?: (available: boolean) => void;
}

const FALLBACK_CENTER: [number, number] = [50.0755, 14.4378]; // Prague, shown until GPS resolves

type RayShape = {
  id: string;
  color: string;
  kind: "wedge" | "line";
  points: [number, number][];
};

type BasemapMetadata = {
  attribution: string;
  minZoom: number;
  maxZoom: number;
  name?: string;
  provider?: string;
};

function AzimuthMap({
  origin,
  rays,
  shadowProbe,
  calibration,
  calibrationBase,
  calibrationTop,
  markMode,
  onPick,
  onOriginMove,
  onImageryAvailabilityChange,
}: AzimuthMapProps) {
  // Remount each selected layer so Leaflet applies its attribution and zoom
  // limits together. Aerial calibration is available only after a tile loads.
  const [basemapMeta, setBasemapMeta] = useState<BasemapMetadata>({
    attribution: FALLBACK_ATTRIBUTION,
    minZoom: 0,
    maxZoom: FALLBACK_MAX_ZOOM,
  });
  const [layer, setLayer] = useState<"loading" | "aerial" | "basic">("loading");
  const layerRef = useRef<"loading" | "aerial" | "basic">("loading");
  const [aerialReady, setAerialReady] = useState(false);
  const [basicFailed, setBasicFailed] = useState(false);
  const [retry, setRetry] = useState(0);

  const showBasicMap = () => {
    layerRef.current = "basic";
    setLayer("basic");
    setAerialReady(false);
    onImageryAvailabilityChange?.(false);
  };

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    layerRef.current = "loading";
    setLayer("loading");
    setAerialReady(false);
    setBasicFailed(false);
    onImageryAvailabilityChange?.(false);
    fetch("/api/basemap-meta", { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: Partial<BasemapMetadata> | null) => {
        if (cancelled) return;
        if (data?.attribution && typeof data.maxZoom === "number" && Number.isInteger(data.maxZoom) && data.maxZoom >= 0 && data.maxZoom <= 22) {
          const minZoom = typeof data.minZoom === "number" && Number.isInteger(data.minZoom) &&
            data.minZoom >= 0 && data.minZoom <= data.maxZoom ? data.minZoom : 0;
          setBasemapMeta({
            attribution: data.attribution,
            minZoom,
            maxZoom: data.maxZoom,
            name: typeof data.name === "string" && data.name.trim() ? data.name.trim() : undefined,
            provider: typeof data.provider === "string" && data.provider.trim() ? data.provider.trim() : undefined,
          });
          layerRef.current = "aerial";
          setLayer("aerial");
        } else {
          layerRef.current = "basic";
          setLayer("basic");
        }
      })
      .catch(() => {
        if (!cancelled) { layerRef.current = "basic"; setLayer("basic"); }
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, [retry, onImageryAvailabilityChange]);

  useEffect(() => {
    if (layer !== "aerial" || aerialReady) return;
    const timeout = window.setTimeout(() => {
      layerRef.current = "basic";
      setLayer("basic");
      onImageryAvailabilityChange?.(false);
    }, 10000);
    return () => window.clearTimeout(timeout);
  }, [layer, aerialReady, onImageryAvailabilityChange]);

  // A live GPS watch re-renders this component several times a second, so the
  // per-ray geodesy (and especially the wedge polygons, which are dozens of
  // destinationPoint calls each) is memoised on the values it actually depends
  // on rather than recomputed on every fix.
  const shapes = useMemo<RayShape[]>(() => {
    if (!origin) return [];
    return rays.map((ray, i) => {
      const color = RAY_COLORS[i % RAY_COLORS.length];
      // A picked target defines the bearing; a typed azimuth is used as-is.
      const bearing = ray.target
        ? bearingBetween(
            origin,
            calibration
              ? correctApparentPosition(ray.target.apparent, ray.target.heightM, calibration)
              : ray.target.apparent
          )
        : ray.azimuthDeg;
      if (ray.beamwidthDeg) {
        return {
          id: ray.id,
          color,
          kind: "wedge",
          points: wedgePoints(origin, bearing, ray.beamwidthDeg, ray.distanceM),
        };
      }
      const dest = destinationPoint(origin, bearing, ray.distanceM);
      return {
        id: ray.id,
        color,
        kind: "line",
        points: [
          [origin.lat, origin.lon],
          [dest.lat, dest.lon],
        ],
      };
    });
  }, [origin, rays, calibration]);

  const originEventHandlers = useMemo<LeafletEventHandlerFnMap>(
    () => ({
      dragend: (e) => {
        const { lat, lng } = (e.target as L.Marker).getLatLng();
        onOriginMove?.({ lat, lon: lng });
      },
    }),
    [onOriginMove]
  );

  return (
    <div className="map-shell flex h-full w-full flex-col overflow-hidden rounded-xl border border-border">
      <div className="relative min-h-0 flex-1">
      <MapContainer
        center={origin ? [origin.lat, origin.lon] : FALLBACK_CENTER}
        zoom={origin ? 18 : 13}
        className="h-full w-full"
        scrollWheelZoom
      >
        {layer !== "loading" && (
          <TileLayer
            key={layer}
            url={layer === "aerial" ? BASEMAP_TILE_URL : BASIC_TILE_URL}
            attribution={layer === "aerial" ? basemapMeta.attribution : BASIC_ATTRIBUTION}
            maxZoom={layer === "aerial" ? basemapMeta.maxZoom : 19}
            maxNativeZoom={layer === "aerial" ? basemapMeta.maxZoom : 19}
            minZoom={layer === "aerial" ? basemapMeta.minZoom : 0}
            eventHandlers={{
              tileerror: () => {
                if (layerRef.current !== layer) return;
                if (layer === "aerial") showBasicMap(); else setBasicFailed(true);
              },
              tileload: () => {
                if (layerRef.current !== layer) return;
                if (layer === "aerial") { setAerialReady(true); onImageryAvailabilityChange?.(true); }
                else setBasicFailed(false);
              },
            }}
          />
        )}
        <ScaleControl />
        <ResizeMap />
        <RecenterOnFirstFix origin={origin} />
        <ClickCapture markMode={markMode} onPick={onPick} />

        {shapes.map((shape) =>
          shape.kind === "wedge" ? (
            <Polygon
              key={shape.id}
              positions={shape.points}
              pathOptions={{ color: shape.color, weight: 2, fillOpacity: 0.2 }}
            />
          ) : (
            <Polyline
              key={shape.id}
              positions={shape.points}
              pathOptions={{ color: shape.color, weight: 3 }}
            />
          )
        )}

        {/* Calibration reference: base -> apparent top, i.e. the measured lean. */}
        {calibrationBase && calibrationTop && (
          <Polyline
            positions={[
              [calibrationBase.lat, calibrationBase.lon],
              [calibrationTop.lat, calibrationTop.lon],
            ]}
            pathOptions={{ color: "#ffd23f", weight: 2, dashArray: "4,4" }}
          />
        )}
        {calibrationBase && <Marker position={[calibrationBase.lat, calibrationBase.lon]} icon={baseIcon} />}
        {calibrationTop && <Marker position={[calibrationTop.lat, calibrationTop.lon]} icon={topIcon} />}

        {/* Picked targets: where they look, and where they really are. */}
        {rays.map((ray) => {
          if (!ray.target) return null;
          const { apparent, heightM } = ray.target;
          const corrected = calibration
            ? correctApparentPosition(apparent, heightM, calibration)
            : null;
          return (
            <Fragment key={`t-${ray.id}`}>
              <Marker position={[apparent.lat, apparent.lon]} icon={targetIcon} />
              {corrected && (
                <>
                  <Polyline
                    positions={[
                      [apparent.lat, apparent.lon],
                      [corrected.lat, corrected.lon],
                    ]}
                    pathOptions={{ color: "#ff6a3d", weight: 2, dashArray: "3,3" }}
                  />
                  <Marker position={[corrected.lat, corrected.lon]} icon={correctedIcon} />
                </>
              )}
            </Fragment>
          );
        })}

        {origin && (
          <Marker
            position={[origin.lat, origin.lon]}
            icon={originIcon}
            draggable={Boolean(onOriginMove)}
            eventHandlers={originEventHandlers}
          />
        )}

        {shadowProbe?.found && shadowProbe.shadowLocation && (
          <Marker
            position={[shadowProbe.shadowLocation.lat, shadowProbe.shadowLocation.lon]}
            icon={shadowIcon}
          />
        )}
      </MapContainer>

      <div className="pointer-events-none absolute right-3 top-3 z-[1000] flex h-9 w-9 items-center justify-center rounded-full bg-black/55 font-sans text-sm font-bold text-white backdrop-blur-sm" lang="cs" aria-label="Sever">
        N
      </div>

      {markMode !== "none" && (
        <div className="pointer-events-none absolute inset-x-14 top-3 z-[1000] mx-auto w-fit rounded-lg bg-black/80 px-3 py-1.5 font-sans text-sm text-white" lang="cs">
          Klepněte do mapy: {markMode === "base" ? "pata objektu" : markMode === "top" ? "vrchol objektu na snímku" : "cíl antény"}.
        </div>
      )}
      </div>

      <div className="flex flex-none flex-wrap items-center gap-2 border-t border-border bg-background px-3 py-2 text-sm text-foreground" lang="cs">
        <p className="min-w-0 flex-1" role="status" aria-atomic="true">
          {layer === "aerial" && aerialReady ? `Podklad: ${basemapMeta.name ?? basemapMeta.provider ?? "Letecký snímek"}.` :
            layer === "loading" || layer === "aerial" ? "Načítám letecký snímek…" : basicFailed ?
              "Mapa se nenačetla. Zkontrolujte připojení. Zadané azimuty zůstávají dostupné." :
              "Letecký snímek není dostupný. Zobrazuji základní mapu OpenStreetMap; korekce podle snímku je vypnutá."}
        </p>
        {layer === "basic" && (
          <button
            type="button"
            className="min-h-12 min-w-12 flex-none rounded-md border border-input px-3 py-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setRetry((value) => value + 1)}
          >
            Znovu načíst snímek
          </button>
        )}
      </div>
    </div>
  );
}

export default memo(AzimuthMap);
