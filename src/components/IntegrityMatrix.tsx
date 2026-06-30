import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ShieldCheck, Lock } from "lucide-react";
import { getJobIntegrity, type EIIComponent } from "@/lib/api";

// Grade -> accent colour. Mirrors the methodology bands (A best … F worst).
function gradeAccent(grade: string | null): { text: string; ring: string; glow: string } {
  const g = (grade ?? "").charAt(0);
  switch (g) {
    case "A":
      return { text: "text-neon-green", ring: "border-neon-green", glow: "shadow-[0_0_30px_rgba(57,255,20,0.25)]" };
    case "B":
      return { text: "text-neon-cyan", ring: "border-neon-cyan", glow: "shadow-[0_0_30px_rgba(0,229,255,0.22)]" };
    case "C":
      return { text: "text-yellow-400", ring: "border-yellow-400", glow: "shadow-[0_0_30px_rgba(250,204,21,0.2)]" };
    case "D":
      return { text: "text-orange-400", ring: "border-orange-400", glow: "shadow-[0_0_30px_rgba(251,146,60,0.2)]" };
    default:
      return { text: "text-red-500", ring: "border-red-500", glow: "shadow-[0_0_30px_rgba(239,68,68,0.22)]" };
  }
}

function ComponentCell({ c, index }: { c: EIIComponent; index: number }) {
  const pct = c.value === null ? 0 : Math.round(c.value * 100);
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.06 }}
      className={`border p-4 font-mono ${
        c.available ? "border-white/20 bg-black/40" : "border-white/5 bg-black/20"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs uppercase tracking-wider ${c.available ? "text-white" : "text-gray-600"}`}>
          {c.name}
        </span>
        <span className="text-[10px] text-gray-500">w={c.weight.toFixed(2)}</span>
      </div>

      {c.available ? (
        <>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-2xl font-bold text-neon-cyan">{pct}</span>
            <span className="text-xs text-gray-500">/ 100</span>
          </div>
          <div className="h-1.5 w-full bg-white/10 mb-3">
            <motion.div
              className="h-full bg-neon-cyan"
              initial={{ width: 0 }}
              whileInView={{ width: `${pct}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: index * 0.06 + 0.1 }}
            />
          </div>
        </>
      ) : (
        <div className="mb-3 mt-1">
          <span className="text-[10px] uppercase tracking-widest text-gray-600 border border-white/10 px-2 py-0.5">
            not assessed
          </span>
        </div>
      )}

      {/* The trace: exactly how this sub-score was produced. */}
      <p className="text-[10px] leading-relaxed text-gray-500">{c.detail}</p>
    </motion.div>
  );
}

export function IntegrityMatrix({ jobId, enabled }: { jobId: string; enabled: boolean }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["job-integrity", jobId],
    queryFn: () => getJobIntegrity(jobId),
    enabled,
    retry: false,
  });

  if (!enabled) return null;

  if (isLoading) {
    return (
      <div className="border border-white/10 bg-black/40 h-48 animate-pulse mb-8" />
    );
  }

  // Older jobs may predate the EII — hide rather than error.
  if (isError || !data) return null;

  const accent = gradeAccent(data.grade);
  const assessedPct = Math.round(data.assessed_weight * 100);
  const pendingCount = data.components.filter((c) => !c.available).length;

  return (
    <div className="border border-white/15 bg-black/60 backdrop-blur-md p-6 sm:p-8 mb-10 hud-bracket relative font-mono">
      <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-50" />

      <div className="flex items-center justify-between text-xs text-gray-500 mb-6 border-b border-white/10 pb-2 uppercase tracking-widest">
        <span>Ecosystem Integrity Index</span>
        <span>v{data.version}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[auto_1fr] gap-8 items-center">
        {/* Grade badge */}
        <div className="flex flex-col items-center">
          <div
            className={`w-32 h-32 border-2 ${accent.ring} ${accent.glow} flex items-center justify-center bg-black/60`}
          >
            <span className={`text-6xl font-heading font-black ${accent.text}`}>
              {data.grade ?? "—"}
            </span>
          </div>
          <div className="mt-3 text-center">
            <div className="text-3xl font-bold text-white">
              {data.score === null ? "N/A" : data.score.toFixed(1)}
              <span className="text-sm text-gray-500"> / 100</span>
            </div>
          </div>
        </div>

        {/* Transparency + headline */}
        <div>
          <h3 className="text-2xl font-heading font-black text-white uppercase tracking-tighter mb-2">
            Biodiversity <span className="text-neon-cyan">Grade.</span>
          </h3>
          <p className="text-sm text-gray-400 leading-relaxed max-w-xl mb-4">
            A transparent composite of real, computed signals from this sample. Not a validated
            ecological metric — a glass-box summary where every sub-score below traces to its
            input and is recorded in this run&apos;s signed manifest.
          </p>
          <div className="flex flex-wrap gap-4 text-xs">
            <span className="border border-white/15 px-3 py-1 text-gray-300">
              Assessed on <span className="text-neon-cyan">{assessedPct}%</span> of the index
            </span>
            {pendingCount > 0 && (
              <span className="border border-yellow-500/30 px-3 py-1 text-yellow-500/90">
                {pendingCount} component{pendingCount > 1 ? "s" : ""} pending
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Component matrix */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-8">
        {data.components.map((c, i) => (
          <ComponentCell key={c.key} c={c} index={i} />
        ))}
      </div>

      <div className="mt-6 pt-4 border-t border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-[11px] text-gray-500">
        <span className="flex items-center gap-2">
          <ShieldCheck className="w-3.5 h-3.5 text-neon-green" />
          Every sub-score is computed from a real signal in this run.
        </span>
        <span className="flex items-center gap-2">
          <Lock className="w-3.5 h-3.5 text-primary" />
          Recorded in the Ed25519-signed provenance manifest.
        </span>
      </div>
    </div>
  );
}
