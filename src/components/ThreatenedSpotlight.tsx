import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";
import { getJobConservation, type ConservationRecord } from "@/lib/api";

// IUCN categories in descending conservation concern. Only these are
// "threatened" enough to spotlight (NT/LC are not).
const THREATENED_ORDER: Record<string, number> = { EX: 6, EW: 5, CR: 4, EN: 3, VU: 2, NT: 1 };
const IUCN_FULL: Record<string, string> = {
  EX: "Extinct", EW: "Extinct in the Wild", CR: "Critically Endangered",
  EN: "Endangered", VU: "Vulnerable", NT: "Near Threatened",
};
const IUCN_BADGE: Record<string, string> = {
  EX: "bg-black text-white border border-white/40", EW: "bg-purple-900 text-white",
  CR: "bg-red-600 text-white", EN: "bg-orange-500 text-black",
  VU: "bg-yellow-500 text-black", NT: "bg-lime-400 text-black",
};

export function ThreatenedSpotlight({ jobId, enabled }: { jobId: string; enabled: boolean }) {
  const { data } = useQuery({
    queryKey: ["job-conservation", jobId],
    queryFn: () => getJobConservation(jobId),
    enabled,
    retry: false,
  });

  if (!enabled || !data) return null;

  const threatened = data.records
    .filter((r: ConservationRecord) => r.iucn_category && (THREATENED_ORDER[r.iucn_category] ?? 0) >= 2)
    .sort((a, b) => (THREATENED_ORDER[b.iucn_category ?? ""] ?? 0) - (THREATENED_ORDER[a.iucn_category ?? ""] ?? 0));

  if (threatened.length === 0) return null;

  const top = threatened[0];
  const topCat = top.iucn_category ?? "VU";

  return (
    <div className="border border-red-500/40 bg-red-950/20 backdrop-blur-md p-4 sm:p-6 hud-bracket mb-6 relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-red-500/60 to-transparent" />
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="p-3 border border-red-500/40 bg-red-500/10 shrink-0 self-start">
          <ShieldAlert className="w-7 h-7 text-red-500" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[11px] uppercase tracking-widest text-red-400/80 mb-1">Conservation Alert</div>
          <h3 className="text-lg sm:text-xl font-heading font-black text-white uppercase tracking-tight">
            {threatened.length} threatened {threatened.length === 1 ? "species" : "species"} detected
          </h3>
          <p className="text-sm text-gray-300 mt-1">
            Most at risk: <span className="italic text-white">{top.species}</span> —{" "}
            <span className="font-bold">{IUCN_FULL[topCat] ?? topCat}</span>
            {top.gbif_occurrence_count != null && (
              <span className="text-gray-500"> · {top.gbif_occurrence_count.toLocaleString()} GBIF records</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-4">
        {threatened.slice(0, 8).map((r) => (
          <span
            key={r.id}
            className="flex items-center gap-2 border border-white/10 bg-black/40 px-2 py-1 text-xs"
            title={IUCN_FULL[r.iucn_category ?? ""] ?? r.iucn_category ?? ""}
          >
            <span className={`px-1.5 py-0.5 text-[10px] font-bold uppercase ${IUCN_BADGE[r.iucn_category ?? "VU"]}`}>{r.iucn_category}</span>
            <span className="italic text-gray-300 truncate max-w-[12rem]">{r.species}</span>
          </span>
        ))}
        {threatened.length > 8 && <span className="text-xs text-gray-500 self-center">+{threatened.length - 8} more</span>}
      </div>
    </div>
  );
}
