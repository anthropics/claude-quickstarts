"use client";
import { useEffect, useState, type FormEvent } from "react";
import type { LatLon } from "@/lib/geometry";
import { parseDecimal } from "@/lib/projects";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function CoordinateForm({ origin, onApply }: { origin: LatLon | null; onApply: (at: LatLon) => void }) {
  const [lat, setLat] = useState(origin?.lat.toFixed(6) ?? "");
  const [lon, setLon] = useState(origin?.lon.toFixed(6) ?? "");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!editing) { setLat(origin?.lat.toFixed(6) ?? ""); setLon(origin?.lon.toFixed(6) ?? ""); }
  }, [origin, editing]);
  const apply = (event: FormEvent) => {
    event.preventDefault();
    const latitude = parseDecimal(lat), longitude = parseDecimal(lon);
    if (latitude === null || longitude === null || Math.abs(latitude) > 85 || Math.abs(longitude) > 180) {
      setError("Zadejte obě souřadnice: šířku −85 až 85° a délku −180 až 180°."); return;
    }
    onApply({ lat: latitude, lon: longitude }); setEditing(false); setError("");
  };
  return <form onSubmit={apply} className="space-y-3" lang="cs">
    <div className="grid gap-3 sm:grid-cols-2">
      <div><Label htmlFor="lat">Zeměpisná šířka</Label><Input id="lat" className="min-h-12 text-base" inputMode="decimal" value={lat} aria-invalid={Boolean(error)} aria-describedby={error ? "coordinate-error" : undefined} onChange={event => { setEditing(true); setLat(event.target.value); }} /></div>
      <div><Label htmlFor="lon">Zeměpisná délka</Label><Input id="lon" className="min-h-12 text-base" inputMode="decimal" value={lon} aria-invalid={Boolean(error)} aria-describedby={error ? "coordinate-error" : undefined} onChange={event => { setEditing(true); setLon(event.target.value); }} /></div>
    </div>
    {error && <p id="coordinate-error" role="alert" className="text-sm">{error}</p>}
    <Button type="submit" variant="outline" className="min-h-12 w-full text-base">Použít souřadnice</Button>
  </form>;
}
