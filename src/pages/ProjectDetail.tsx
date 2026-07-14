import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ZAxis,
} from "recharts";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { getProject, getProjectOrdination } from "@/lib/api";
import { ArrowLeft, ChevronRight, GitCompareArrows } from "lucide-react";
import { cn } from "@/lib/utils";

const STATUS_CLS: Record<string, string> = {
  succeeded: "text-neon-green border-neon-green",
  failed: "text-red-500 border-red-500",
  running: "text-yellow-500 border-yellow-500",
  queued: "text-neon-cyan border-white/30",
  cancelled: "text-gray-500 border-gray-600",
};

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();

  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  });
  const { data: ord } = useQuery({
    queryKey: ["project-ordination", projectId],
    queryFn: () => getProjectOrdination(projectId!),
    enabled: !!projectId,
    retry: false,
  });

  if (!projectId) return null;

  const pct = (i: number) => (ord?.proportion_explained?.[i] != null ? `${(ord.proportion_explained[i] * 100).toFixed(1)}%` : "");
  const points = (ord?.points ?? []).map((p) => ({ x: p.pc1, y: p.pc2, label: p.label, job_id: p.job_id }));

  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-28 sm:pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">
          <Link to="/projects" className="inline-flex items-center text-xs text-gray-500 mb-6 hover:text-neon-cyan uppercase tracking-wider min-h-[44px]">
            <ArrowLeft className="w-4 h-4 mr-2" /> All projects
          </Link>

          <div className="mb-8">
            <div className="flex items-center gap-2 text-primary text-xs uppercase tracking-widest mb-3">
              <span className="w-2 h-2 bg-primary" />
              <span>Study</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-heading font-black text-white uppercase tracking-tighter break-words">
              {project?.name ?? "…"}
            </h1>
            {project?.description && <p className="text-sm text-gray-400 mt-2 max-w-2xl">{project.description}</p>}
            <p className="text-xs text-gray-500 mt-2">
              {project?.job_count ?? 0} samples · <span className="text-neon-green">{project?.succeeded_count ?? 0} completed</span>
            </p>
          </div>

          {/* Cross-sample PCoA */}
          <div className="border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket mb-6">
            <div className="flex items-center justify-between text-[11px] text-gray-500 mb-4 border-b border-white/10 pb-2 uppercase tracking-widest">
              <span className="flex items-center gap-2"><GitCompareArrows className="w-3.5 h-3.5" /> Cross-sample Ordination · Bray-Curtis PCoA</span>
              {ord && ord.n_samples >= 2 && <span className="text-gray-600">{ord.n_samples} samples</span>}
            </div>
            {ord?.message ? (
              <p className="text-sm text-gray-400 py-8 text-center">{ord.message}</p>
            ) : points.length > 0 ? (
              <>
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 24, left: 8 }}>
                      <CartesianGrid stroke="rgba(255,255,255,0.08)" />
                      <XAxis type="number" dataKey="x" name="PC1" tick={{ fill: "#9ca3af", fontSize: 10 }} stroke="rgba(255,255,255,0.2)"
                        label={{ value: `PC1 ${pct(0)}`, position: "bottom", fill: "#6b7280", fontSize: 11 }} />
                      <YAxis type="number" dataKey="y" name="PC2" tick={{ fill: "#9ca3af", fontSize: 10 }} stroke="rgba(255,255,255,0.2)"
                        label={{ value: `PC2 ${pct(1)}`, angle: -90, position: "left", fill: "#6b7280", fontSize: 11 }} />
                      <ZAxis range={[120, 120]} />
                      <Tooltip
                        cursor={{ stroke: "rgba(0,240,255,0.3)" }}
                        contentStyle={{ background: "#000", border: "1px solid rgba(255,255,255,0.2)", fontFamily: "monospace", fontSize: 11 }}
                        formatter={(v: number) => v.toFixed(3)}
                        labelFormatter={() => ""}
                      />
                      <Scatter data={points} fill="#00f0ff" fillOpacity={0.75} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] text-gray-500 mt-2">
                  Each point is a sample; closer points have more similar communities (Bray-Curtis). Real multi-sample
                  ordination — not a single-sample projection.
                </p>
              </>
            ) : (
              <div className="h-40 animate-pulse bg-black/40" />
            )}
          </div>

          {/* Samples */}
          <div className="border border-white/15 bg-black/60 backdrop-blur-md hud-bracket">
            <div className="p-4 border-b border-white/10 text-[11px] text-gray-500 uppercase tracking-widest">Samples in this project</div>
            {!project ? (
              <div className="p-8 animate-pulse" />
            ) : project.jobs.length === 0 ? (
              <div className="p-8 text-center text-sm text-gray-400">
                No samples attached yet. Run an analysis, then add it to this project from the results page.
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {project.jobs.map((j) => {
                  const clickable = j.status === "succeeded";
                  const row = (
                    <div className="flex items-center justify-between gap-3 p-4 hover:bg-white/5 transition-colors group">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={cn("text-[10px] font-bold uppercase px-2 py-1 border shrink-0", STATUS_CLS[j.status] || STATUS_CLS.queued)}>{j.status}</span>
                        <div className="min-w-0">
                          <p className="text-sm text-white truncate">{j.id.slice(0, 12)}…</p>
                          <p className="text-[11px] text-gray-500">{j.amplicon} · {new Date(j.created_at).toLocaleString()}</p>
                        </div>
                      </div>
                      {clickable && <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-neon-cyan shrink-0" />}
                    </div>
                  );
                  return clickable ? <Link key={j.id} to={`/jobs/${j.id}`}>{row}</Link> : <div key={j.id}>{row}</div>;
                })}
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
