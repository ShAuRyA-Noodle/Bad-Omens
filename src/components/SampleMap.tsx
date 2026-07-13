import { useQuery } from "@tanstack/react-query";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { getJobSummary, getJobConservation } from "@/lib/api";

const THREATENED = new Set(["CR", "EN", "VU", "EW", "EX"]);

export function SampleMap({ jobId, enabled }: { jobId: string; enabled: boolean }) {
  const { data: summary } = useQuery({ queryKey: ["job-summary", jobId], queryFn: () => getJobSummary(jobId), enabled });
  const { data: cons } = useQuery({ queryKey: ["job-conservation", jobId], queryFn: () => getJobConservation(jobId), enabled, retry: false });

  const md = summary?.dwc_metadata;
  const lat = md ? Number(md.decimalLatitude) : NaN;
  const lon = md ? Number(md.decimalLongitude) : NaN;
  if (!enabled || !md || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;

  const threatened = (cons?.records ?? []).filter((r) => r.iucn_category && THREATENED.has(r.iucn_category));
  const hasThreat = threatened.length > 0;
  const color = hasThreat ? "#ef4444" : "#00f0ff";

  return (
    <div className="border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket mb-6">
      <div className="flex items-center justify-between text-[11px] text-gray-500 mb-3 border-b border-white/10 pb-2 uppercase tracking-widest">
        <span>Sampling Location</span>
        <span className="text-gray-600">
          {lat.toFixed(4)}, {lon.toFixed(4)}
        </span>
      </div>
      <div className="h-72 sm:h-80 w-full overflow-hidden border border-white/10">
        <MapContainer center={[lat, lon]} zoom={6} scrollWheelZoom={false} style={{ height: "100%", width: "100%", background: "#000" }}>
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          />
          <CircleMarker center={[lat, lon]} radius={11} pathOptions={{ color, fillColor: color, fillOpacity: 0.35, weight: 2 }}>
            <Popup>
              <div style={{ fontFamily: "monospace", fontSize: 12 }}>
                <strong>{md.locality ? String(md.locality) : "eDNA sample"}</strong>
                <br />
                {summary?.n_asvs ?? 0} ASVs · {threatened.length} threatened
                {md.eventDate ? <><br />{String(md.eventDate)}</> : null}
              </div>
            </Popup>
          </CircleMarker>
        </MapContainer>
      </div>
      {hasThreat && (
        <p className="text-[11px] text-red-400/90 mt-3">
          ⚠ {threatened.length} threatened species detected at this location.
        </p>
      )}
    </div>
  );
}
