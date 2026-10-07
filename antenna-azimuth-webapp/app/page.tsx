"use client";

import { Check, Link as LinkIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AzimuthControls, type GpsStatus } from "@/components/AzimuthControls";
import { CalibrationPanel, type MarkMode } from "@/components/CalibrationPanel";
import { MobileCompass } from "@/components/MobileCompass";
import { Button } from "@/components/ui/button";
import { haversineDistanceM, type LatLon } from "@/lib/geometry";
import { decodeSession, loadSession, saveSession, shareUrl, type SessionState } from "@/lib/persist";
import { calibrateFromReference, type ImageryCalibration } from "@/lib/relief";
import type { AzimuthRay } from "@/lib/types";
import { listProjects, saveProject } from "@/lib/project-store";
import { projectRays, projectIsComplete, type MountingProject } from "@/lib/projects";

const ProjectWorkspace = dynamic(() => import("@/components/ProjectWorkspace").then(module => module.ProjectWorkspace), { ssr: false });
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
      id: "ray-1",
      azimuthDeg: 45,
      distanceM: 1000,
      beamwidthDeg: null,
      label: "Ray 1",
    },
  ];
}

export default function Home() {
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [projectsFilter, setProjectsFilter] = useState<"active" | "completed">("active");
  const [activeDetails, setActiveDetails] = useState<MountingProject | null>(null);
  const [completionBusy, setCompletionBusy] = useState(false);
  const [completionMessage, setCompletionMessage] = useState("");
  const [activeProject, setActiveProject] = useState<{ id: string; name: string; revision: number } | null>(null);
  const [projectNeedsPosition, setProjectNeedsPosition] = useState(false);
  const [liveOrigin, setLiveOrigin] = useState<LatLon | null>(null);
  const [manualOrigin, setManualOrigin] = useState<LatLon | null>(null);
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>("idle");
  const [gpsAccuracyM, setGpsAccuracyM] = useState<number | null>(null);
  const [headingDeg, setHeadingDeg] = useState<number | null>(null);
  const [rays, setRays] = useState<AzimuthRay[]>(defaultRays);
  const [copied, setCopied] = useState(false);
  const [imageryAvailable, setImageryAvailable] = useState(false);

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
    if (state.activeProject) setActiveProject(state.activeProject);
    if (state.projectNeedsPosition) setProjectNeedsPosition(true);
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
        setHeadingDeg(pos.coords.heading != null && Number.isFinite(pos.coords.heading)
          ? Math.round(pos.coords.heading) % 360 : null);
        setGpsStatus("watching");
      },
      (err) => {
        setGpsStatus(err.code === err.PERMISSION_DENIED ? "denied" : "error");
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  const origin = projectNeedsPosition ? null : manualOrigin ?? liveOrigin;

  const calibration: ImageryCalibration | null = useMemo(() => {
    if (!imageryAvailable || !calibrationBase || !calibrationTop || !referenceHeightM) return null;
    return calibrateFromReference({
      base: calibrationBase,
      top: calibrationTop,
      heightM: referenceHeightM,
    });
  }, [imageryAvailable, calibrationBase, calibrationTop, referenceHeightM]);

  const sessionState: SessionState = useMemo(
    () => ({
      activeProject,
      projectNeedsPosition,
      origin,
      rays,
      calibration,
      calibrationBase,
      calibrationTop,
      referenceHeightM,
    }),
    [origin, rays, calibration, calibrationBase, calibrationTop, referenceHeightM, activeProject, projectNeedsPosition]
  );

  useEffect(() => {
    saveSession(sessionState);
  }, [sessionState]);

  const handleUseLiveGps = useCallback(() => { setManualOrigin(null); setProjectNeedsPosition(false); }, []);
  const handleImageryAvailability = useCallback((available: boolean) => {
    setImageryAvailable(available);
    if (!available) { setMarkMode("none"); setPickingRayId(null); }
  }, []);

  const handlePick = useCallback(
    (mode: Exclude<MarkMode, "none">, at: LatLon) => {
      if (!imageryAvailable) return;
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
    [pickingRayId, imageryAvailable]
  );

  const handlePickTarget = useCallback(
    (rayId: string) => {
      if (!imageryAvailable) return;
      if (markMode === "target" && pickingRayId === rayId) {
        setMarkMode("none");
        setPickingRayId(null);
      } else {
        setMarkMode("target");
        setPickingRayId(rayId);
      }
    },
    [imageryAvailable, markMode, pickingRayId]
  );

  const handleCopyLink = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareUrl(sessionState));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked — nothing useful to say */
    }
  }, [sessionState]);

  const handleOpenProject = (project: MountingProject) => {
    setActiveDetails(project); setCompletionMessage("");
    setRays(projectRays(project));
    const hasPosition = project.latitude !== null && project.longitude !== null;
    setManualOrigin(hasPosition ? { lat: project.latitude!, lon: project.longitude! } : null);
    setProjectNeedsPosition(!hasPosition);
    setCalibrationBase(null); setCalibrationTop(null); setReferenceHeightM(null);
     setMarkMode("none"); setPickingRayId(null);
    setActiveProject({ id: project.id, name: project.name, revision: project.revision });
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
    setProjectsOpen(false);
  };

  useEffect(() => {
    if (!activeProject || activeDetails || projectsOpen) return;
    let cancelled = false;
    listProjects().then(projects => {
      if (cancelled) return;
      const project = projects.find(item => item.id === activeProject.id);
      if (project) {
        if (project.revision === activeProject.revision) setActiveDetails(project);
        else setCompletionMessage("Projekt se od posledního otevření změnil. Otevřete aktuální zadání v Projektech.");
      }
    }).catch(() => { if (!cancelled) setCompletionMessage("Pro potvrzení montáže se přihlaste v Projektech."); });
    return () => { cancelled = true; };
  }, [activeProject, activeDetails, projectsOpen]);

  const confirmSector = async (sectorId: string) => {
    if (!activeDetails || completionBusy) return;
    const source = activeDetails.sectors.find(sector => sector.id === sectorId);
    const ray = rays.find(item => item.id === sectorId);
    if (!source || !ray || ray.target || ray.azimuthDeg !== source.azimuthDeg) {
      setCompletionMessage("Směr na mapě se liší od zadání. Nejprve zkontrolujte projekt."); return;
    }
    setCompletionBusy(true); setCompletionMessage("Ukládám stav montáže…");
    try {
      const project = await saveProject({ ...activeDetails, sectors: activeDetails.sectors.map(sector => sector.id === sectorId ? { ...sector, completedAt: sector.completedAt ? null : new Date().toISOString() } : sector) });
      setActiveDetails(project); setActiveProject({ id: project.id, name: project.name, revision: project.revision });
      setCompletionMessage(source.completedAt ? "Sektor vrácen mezi rozpracované." : "Nasměrování sektoru potvrzeno.");
      if (projectIsComplete(project)) { setProjectsFilter("completed"); setProjectsOpen(true); }
    } catch (error) { setCompletionMessage(error instanceof Error ? error.message : "Stav se nepodařilo uložit. Potvrzení zopakujte."); }
    finally { setCompletionBusy(false); }
  };

  if (projectsOpen) return <ProjectWorkspace initialFilter={projectsFilter} onOpen={handleOpenProject} onClose={() => setProjectsOpen(false)} />;

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      <div className="relative h-[45vh] p-3 md:h-full md:flex-1 md:p-4">
        <AzimuthMap
          origin={origin}
          rays={rays}
          shadowProbe={null}
          calibration={calibration}
          calibrationBase={imageryAvailable ? calibrationBase : null}
          calibrationTop={imageryAvailable ? calibrationTop : null}
          markMode={imageryAvailable ? markMode : "none"}
          onPick={handlePick}
          onOriginMove={at => { setManualOrigin(at); setProjectNeedsPosition(false); }}
          onImageryAvailabilityChange={handleImageryAvailability}
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

        <div className="space-y-3 px-4 pt-4" lang="cs">
          <Button className="min-h-12 w-full text-base" onClick={() => { setProjectsFilter("active"); setProjectsOpen(true); }}>Projekty a nahrání PDF</Button>
          {activeProject && <p className="text-base font-medium">{activeProject.name} · revize {activeProject.revision}</p>}
          {completionMessage && <p role="status" className="text-sm">{completionMessage}</p>}
          {projectNeedsPosition && <p role="status" className="text-sm">Projekt nemá souřadnice. Nastavte místo montáže ručně nebo použijte polohu telefonu.</p>}
          {!manualOrigin && gpsAccuracyM !== null && gpsAccuracyM > 100 && <p role="status" className="text-sm">GPS je zatím nepřesná (±{gpsAccuracyM} m). Ověřte místo montáže v mapě.</p>}
        </div>
        <AzimuthControls
          projectSectors={activeDetails?.sectors}
          onConfirmSector={activeDetails ? confirmSector : undefined}
          completionBusy={completionBusy}
          rays={rays}
          onRaysChange={setRays}
          origin={origin}
          gpsStatus={gpsStatus}
          gpsAccuracyM={manualOrigin ? null : gpsAccuracyM}
          headingDeg={headingDeg}
          manualOverride={manualOrigin !== null || projectNeedsPosition}
          onManualOriginChange={at => { setManualOrigin(at); setProjectNeedsPosition(false); }}
          onUseLiveGps={handleUseLiveGps}
          calibration={calibration}
          markMode={markMode}
          onPickTarget={handlePickTarget}
          pickingRayId={pickingRayId}
          imageryAvailable={imageryAvailable}
        />

        <div className="flex flex-col gap-4 p-4 pb-0">
          <MobileCompass />
          {imageryAvailable && <details><summary className="min-h-12 cursor-pointer py-3 text-base font-medium">Pokročilé: korekce leteckého snímku</summary><CalibrationPanel
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
              
            }}
          /></details>}
        </div>



        
      </aside>
    </main>
  );
}
