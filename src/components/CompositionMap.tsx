import { useQuery } from "@tanstack/react-query";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getJobOrdination, type OrdinationPoint } from "@/lib/api";

const CLUSTER_COLORS = ["#00f0ff", "#39FF14", "#ff00e5", "#ffb300", "#a855f7", "#ff5555", "#00ffa3", "#ff8c00"];

function colorFor(cluster: number): string {
  if (cluster < 0) return "#4b5563"; // noise = dim gray
  return CLUSTER_COLORS[cluster % CLUSTER_COLORS.length];
}

export function CompositionMap({ jobId, enabled }: { jobId: string; enabled: boolean }) {
  const { data } = useQuery({
    queryKey: ["job-ordination", jobId],
    queryFn: () => getJobOrdination(jobId),
    enabled,
    retry: false,
  });

  if (!enabled || !data || data.skipped || data.points.length === 0) return null;

  const byCluster = new Map<number, OrdinationPoint[]>();
  for (const p of data.points) {
    const arr = byCluster.get(p.cluster) ?? [];
    arr.push(p);
    byCluster.set(p.cluster, arr);
  }
  const clusters = [...byCluster.entries()].sort((a, b) => a[0] - b[0]);

  return (
    <div className="border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket mt-4 font-mono">
      <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1 border-b border-white/10 pb-2 uppercase tracking-widest">
        <span>ASV Composition Map</span>
        <span className="text-gray-600">UMAP · {data.n_clusters} clusters</span>
      </div>
      <p className="text-[11px] text-gray-500 my-3">
        Each point is an ASV, positioned by its 5-mer sequence composition (UMAP) and coloured by HDBSCAN cluster.
        A within-sample composition map — not a multi-sample community ordination.
      </p>
      <div className="h-72 sm:h-96 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.06)" />
            <XAxis type="number" dataKey="x" name="UMAP-1" tick={{ fill: "#9ca3af", fontSize: 10 }} stroke="rgba(255,255,255,0.15)" />
            <YAxis type="number" dataKey="y" name="UMAP-2" tick={{ fill: "#9ca3af", fontSize: 10 }} stroke="rgba(255,255,255,0.15)" width={40} />
            <Tooltip
              cursor={{ stroke: "#00f0ff", strokeOpacity: 0.3 }}
              contentStyle={{ background: "#000", border: "1px solid rgba(255,255,255,0.2)", fontFamily: "monospace", fontSize: 11 }}
              formatter={(val: number | string) => (typeof val === "number" ? val.toFixed(3) : String(val))}
            />
            {clusters.map(([cluster, pts]) => (
              <Scatter key={cluster} data={pts} fill={colorFor(cluster)} name={cluster < 0 ? "noise" : `cluster ${cluster}`} />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3 text-[10px] text-gray-500">
        {clusters.map(([cluster]) => (
          <span key={cluster} className="flex items-center gap-1.5">
            <span className="w-2 h-2 inline-block" style={{ backgroundColor: colorFor(cluster) }} />
            {cluster < 0 ? "noise" : `cluster ${cluster}`}
          </span>
        ))}
      </div>
    </div>
  );
}
