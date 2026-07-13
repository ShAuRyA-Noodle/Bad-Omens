import type { ReactNode } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { IntegrityMatrix } from "@/components/IntegrityMatrix";
import { CompositionMap } from "@/components/CompositionMap";
import { cn } from "@/lib/utils";
import {
  getJobSummary,
  getJobASVs,
  getJobConservation,
  getJobProvenance,
  downloadExport,
  getDwcaUrl,
  getCsvUrl,
  getBiomUrl,
  getReportUrl,
  getJob,
  type ASVWithTaxon,
  type ConservationSummary,
  type ProvenanceManifest,
  type JobResultsSummary,
} from "@/lib/api";
import { Download, Shield, Dna, BarChart3, FileCheck, ArrowLeft } from "lucide-react";

const IUCN_COLORS: Record<string, string> = {
  EX: "bg-black text-white border border-white/40",
  EW: "bg-purple-900 text-white",
  CR: "bg-red-600 text-white",
  EN: "bg-orange-500 text-black",
  VU: "bg-yellow-500 text-black",
  NT: "bg-lime-400 text-black",
  LC: "bg-green-500 text-black",
  DD: "bg-gray-500 text-white",
  NE: "bg-gray-700 text-gray-200",
};

// ─── Reusable cyber-terminal primitives ─────────────────────────────────

function Panel({ label, live, children, className }: { label?: string; live?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn("border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket relative", className)}>
      {label && (
        <div className="flex items-center justify-between text-[11px] text-gray-500 mb-4 border-b border-white/10 pb-2 uppercase tracking-widest">
          <span>{label}</span>
          {live && <span className="text-gray-600">{live}</span>}
        </div>
      )}
      {children}
    </div>
  );
}

function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="border border-white/10 bg-black/40 h-40 flex items-center justify-center font-mono text-xs text-gray-500 animate-pulse">
      {label}
      <span className="ml-1 animate-pulse text-neon-cyan">_</span>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-white/15 bg-black/50 p-4 font-mono">
      <p className="text-[10px] sm:text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl sm:text-2xl font-bold mt-1 text-neon-cyan break-words">{value}</p>
    </div>
  );
}

export default function JobResults() {
  const { jobId } = useParams<{ jobId: string }>();

  const { data: job } = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId,
  });
  const succeeded = job?.status === "succeeded";

  const { data: summary, isLoading: summaryLoading } = useQuery({ queryKey: ["job-summary", jobId], queryFn: () => getJobSummary(jobId!), enabled: !!jobId && succeeded });
  const { data: asvs, isLoading: asvsLoading } = useQuery({ queryKey: ["job-asvs", jobId], queryFn: () => getJobASVs(jobId!), enabled: !!jobId && succeeded });
  const { data: conservation, isLoading: consLoading } = useQuery({ queryKey: ["job-conservation", jobId], queryFn: () => getJobConservation(jobId!), enabled: !!jobId && succeeded });
  const { data: provenance, isLoading: provLoading } = useQuery({ queryKey: ["job-provenance", jobId], queryFn: () => getJobProvenance(jobId!), enabled: !!jobId && succeeded });

  if (!jobId) return null;

  const statusStyle =
    job?.status === "succeeded" ? "border-neon-green text-neon-green"
      : job?.status === "failed" ? "border-red-500 text-red-500"
        : "border-yellow-500 text-yellow-500";

  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-28 sm:pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-6xl">
          <Link to="/demo" className="inline-flex items-center text-xs text-gray-500 mb-6 hover:text-neon-cyan transition-colors uppercase tracking-wider min-h-[44px]">
            <ArrowLeft className="w-4 h-4 mr-2" /> Back to pipeline
          </Link>

          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-2 text-primary text-xs uppercase tracking-widest mb-3">
                <span className="w-2 h-2 bg-primary animate-pulse" />
                <span>Analysis Output</span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-heading font-black text-white uppercase tracking-tighter">
                Results<span className="text-neon-cyan">.</span>
              </h1>
              <p className="text-xs text-gray-500 mt-2 break-all">JOB_ID: {jobId}</p>
            </div>
            {job && (
              <span className={cn("border px-3 py-1.5 text-xs uppercase tracking-wider shrink-0 self-start sm:self-auto", statusStyle)}>
                {job.status}{job.pipeline_version ? ` · v${job.pipeline_version}` : ""}
              </span>
            )}
          </div>

          {/* Flagship: the Ecosystem Integrity Index grade matrix. */}
          <IntegrityMatrix jobId={jobId} enabled={succeeded} />

          {job && !succeeded && (
            <Panel label={`Job Status // ${job.status}`}>
              <p className="text-sm text-gray-300">
                {job.status === "running" && "Pipeline is executing. This page updates when the job completes."}
                {job.status === "queued" && "Job is queued and waiting for a worker."}
                {job.status === "failed" && "The pipeline failed. The error is shown below."}
                {job.status === "cancelled" && "This job was cancelled."}
              </p>
              {job.error_message && (
                <pre className="mt-4 text-xs text-red-400 bg-black/60 border border-red-500/30 p-3 overflow-x-auto whitespace-pre-wrap break-words">{job.error_message}</pre>
              )}
            </Panel>
          )}

          {succeeded && (
            <Tabs defaultValue="overview" className="space-y-6">
              <TabsList className="grid grid-cols-3 sm:grid-cols-5 w-full h-auto gap-1 bg-black/40 border border-white/10 p-1">
                {[
                  { v: "overview", icon: BarChart3, label: "Overview" },
                  { v: "asvs", icon: Dna, label: "ASVs" },
                  { v: "conservation", icon: Shield, label: "Conservation" },
                  { v: "provenance", icon: FileCheck, label: "Provenance" },
                  { v: "export", icon: Download, label: "Export" },
                ].map(({ v, icon: Icon, label }) => (
                  <TabsTrigger
                    key={v}
                    value={v}
                    className="flex flex-col sm:flex-row items-center justify-center gap-1 sm:gap-2 py-2 min-h-[48px] text-[10px] sm:text-xs uppercase tracking-wider rounded-none border border-transparent data-[state=active]:bg-primary/10 data-[state=active]:text-primary data-[state=active]:border-primary/40 data-[state=active]:shadow-none"
                  >
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="truncate">{label}</span>
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                {summaryLoading || !summary ? <Loading label="Computing metrics" /> : <OverviewTab summary={summary} />}
                <CompositionMap jobId={jobId} enabled={succeeded} />
              </TabsContent>
              <TabsContent value="asvs">{asvsLoading || !asvs ? <Loading label="Loading ASVs" /> : <ASVsTab asvs={asvs} total={summary?.n_asvs} />}</TabsContent>
              <TabsContent value="conservation">{consLoading || !conservation ? <Loading label="Cross-referencing GBIF/IUCN" /> : <ConservationTab data={conservation} />}</TabsContent>
              <TabsContent value="provenance">{provLoading || !provenance ? <Loading label="Loading manifest" /> : <ProvenanceTab data={provenance} />}</TabsContent>
              <TabsContent value="export"><ExportTab jobId={jobId} /></TabsContent>
            </Tabs>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}

function OverviewTab({ summary }: { summary: JobResultsSummary }) {
  const d = summary.diversity;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
      <MetricCard label="ASVs Detected" value={summary.n_asvs} />
      <MetricCard label="Taxa Assigned" value={`${summary.n_assigned} / ${summary.n_asvs}`} />
      <MetricCard label="Shannon" value={d?.shannon?.toFixed(4) ?? "—"} />
      <MetricCard label="Simpson" value={d?.simpson?.toFixed(4) ?? "—"} />
      <MetricCard label="Richness" value={d?.richness ?? "—"} />
      <MetricCard label="Chao1" value={d?.chao1?.toFixed(2) ?? "—"} />
      <MetricCard label="Evenness" value={d?.evenness?.toFixed(4) ?? "—"} />
      <MetricCard label="Marker" value={summary.amplicon} />
    </div>
  );
}

function ASVsTab({ asvs, total }: { asvs: ASVWithTaxon[]; total?: number }) {
  if (asvs.length === 0) {
    return <Panel label="ASVs"><p className="text-sm text-gray-400">No ASVs were inferred for this sample.</p></Panel>;
  }
  const capped = total != null && total > asvs.length;
  return (
    <Panel label={`Amplicon Sequence Variants // ${asvs.length}${capped ? ` of ${total}` : ""}`}>
      {capped && (
        <p className="text-[11px] text-gray-500 mb-3">Showing the {asvs.length} most abundant ASVs of {total}.</p>
      )}
      <div className="space-y-3">
        {asvs.map((asv, i) => {
          const t = asv.taxon;
          const name = [t?.genus, t?.species].filter(Boolean).join(" ") || "Unassigned";
          const conf = t?.confidence != null ? `${(t.confidence * 100).toFixed(1)}%` : "—";
          const lineage = [t?.kingdom, t?.phylum, t?.tax_class, t?.tax_order, t?.family, t?.genus].filter(Boolean).join(" › ");
          return (
            <div key={asv.id} className="border border-white/10 p-3 sm:p-4 hover:bg-white/5 transition-colors">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-2">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs text-gray-600 w-8 shrink-0">#{i + 1}</span>
                  <span className="font-bold text-white italic truncate">{name}</span>
                  <span className="text-[10px] px-2 py-0.5 border border-white/20 text-gray-400 shrink-0">{conf}</span>
                </div>
                <div className="flex items-center gap-4 text-[11px] text-gray-500 pl-11 sm:pl-0 shrink-0">
                  <span>{asv.abundance.toLocaleString()} reads</span>
                  <span>{asv.length} bp</span>
                </div>
              </div>
              {lineage && <div className="text-[11px] text-gray-500 mb-1 pl-11 sm:pl-0 break-words">{lineage}</div>}
              <div className="font-mono text-[10px] text-gray-600 break-all pl-11 sm:pl-0">{asv.sequence.slice(0, 72)}…</div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function ConservationTab({ data }: { data: ConservationSummary }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
        <MetricCard label="Species Queried" value={data.species_queried} />
        <MetricCard label="In GBIF" value={data.species_with_gbif} />
        <MetricCard label="IUCN Assessed" value={data.species_with_iucn} />
        <MetricCard label="Threatened" value={data.threatened_count} />
      </div>
      {data.api_degraded && (
        <div className="border border-yellow-500/40 bg-yellow-500/5 p-3 text-xs text-yellow-500/90 flex items-start gap-2">
          <span className="shrink-0">⚠</span>
          <span>{data.lookup_failed_count} lookup(s) failed (GBIF/IUCN). Conservation results may be incomplete — the &quot;Threatened&quot; count is not authoritative for this run.</span>
        </div>
      )}
      <Panel label="Per-Species Conservation Status">
        {data.records.length === 0 ? (
          <p className="text-sm text-gray-400">No species-level assignments to cross-reference.</p>
        ) : (
          <div className="space-y-2">
            {data.records.map((r) => {
              const iucn = r.iucn_category || "NE";
              return (
                <div key={r.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 p-3 border border-white/10">
                  <div className="min-w-0">
                    <p className="font-medium text-white italic break-words">{r.species}</p>
                    <p className="text-[11px] text-gray-500">
                      GBIF: {r.gbif_occurrence_count?.toLocaleString() ?? "—"} occurrences
                      {r.legal_flags?.iucn_population_trend ? ` · trend: ${r.legal_flags.iucn_population_trend}` : ""}
                    </p>
                  </div>
                  <span className={cn("text-xs px-2 py-1 font-bold uppercase shrink-0 self-start", IUCN_COLORS[iucn] || IUCN_COLORS.NE)}>{iucn}</span>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}

function ProvenanceTab({ data }: { data: ProvenanceManifest }) {
  const m = data.manifest as Record<string, unknown>;
  const pipeline = m.pipeline as Record<string, unknown> | undefined;
  const tools = (pipeline?.tool_versions || {}) as Record<string, string>;
  const stages = (m.stages || []) as Array<Record<string, unknown>>;
  const inputs = (m.inputs || []) as Array<Record<string, unknown>>;
  const isSigned = data.signature?.startsWith("ed25519:");

  return (
    <div className="space-y-4">
      <Panel label="Reproducibility Manifest" live={isSigned ? "ED25519-SIGNED" : "UNSIGNED"}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
          <Field label="Manifest SHA256" value={data.manifest_sha256} mono />
          <Field label={isSigned ? "Ed25519 Signature" : "Signature"} value={data.signature} mono />
          <Field label="Pipeline" value={`${String(pipeline?.name || "Relict")} v${String(pipeline?.version || "?")}`} />
          <Field label="Signed at" value={new Date(data.signed_at).toLocaleString()} />
        </div>
        <p className="mt-4 text-[11px] text-gray-500 border-t border-white/10 pt-3">
          Anyone can{" "}
          <Link to="/verify" className="text-neon-cyan hover:underline">verify this manifest</Link>{" "}
          against the server&apos;s Ed25519 public key — no login required.
        </p>
      </Panel>

      <Panel label={`Tool Versions // ${Object.keys(tools).length}`}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
          {Object.entries(tools).map(([tool, ver]) => (
            <div key={tool} className="p-2 border border-white/10 flex justify-between gap-2">
              <span className="text-gray-300 truncate">{tool}</span>
              <span className="text-neon-cyan shrink-0">{ver}</span>
            </div>
          ))}
        </div>
      </Panel>

      <Panel label={`Pipeline Stages // ${stages.length}`}>
        <div className="space-y-1 text-sm">
          {stages.map((s, i) => (
            <div key={i} className="flex items-center justify-between gap-2 p-2 border-b border-white/5">
              <div className="min-w-0">
                <span className="font-medium text-white">{String(s.stage)}</span>
                <span className="text-gray-500 ml-2 text-xs">{String(s.tool)} v{String(s.tool_version)}</span>
              </div>
              {s.runtime_seconds != null && <span className="text-gray-500 text-xs shrink-0">{Number(s.runtime_seconds).toFixed(2)}s</span>}
            </div>
          ))}
        </div>
      </Panel>

      {inputs.length > 0 && (
        <Panel label="Input Files">
          {inputs.map((inp, i) => (
            <div key={i} className="text-sm">
              <p className="font-bold text-white break-all">{String(inp.filename)}</p>
              <p className="text-gray-500 font-mono text-[11px] break-all">SHA256: {String(inp.sha256)}</p>
              <p className="text-gray-500 text-xs">{Number(inp.size_bytes).toLocaleString()} bytes</p>
            </div>
          ))}
        </Panel>
      )}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="text-gray-500 text-[11px] uppercase tracking-wider">{label}</p>
      <p className={cn("break-all", mono && "font-mono text-xs")}>{value}</p>
    </div>
  );
}

function ExportBtn({ onClick, children, primary }: { onClick: () => void; children: ReactNode; primary?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full min-h-[44px] px-4 py-3 text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-colors border",
        primary ? "btn-cyber font-bold" : "border-white/20 text-gray-300 hover:text-white hover:bg-white/10",
      )}
    >
      {children}
    </button>
  );
}

function ExportTab({ jobId }: { jobId: string }) {
  return (
    <div className="space-y-4">
      <Panel label="Full Analysis Report" className="border-primary/30">
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
          <div className="p-3 border border-primary/30 bg-primary/10 shrink-0 self-start">
            <FileCheck className="w-7 h-7 text-neon-green" />
          </div>
          <p className="text-sm text-gray-400">
            Self-contained HTML report: diversity metrics, ASV table, taxonomy, conservation status (IUCN/GBIF), the Ecosystem Integrity Index, and the full provenance manifest. Opens in any browser, print-ready.
          </p>
        </div>
        <ExportBtn primary onClick={() => downloadExport(getReportUrl(jobId), `relict_report_${jobId}.html`)}>
          <Download className="w-4 h-4" /> Download Report (HTML)
        </ExportBtn>
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Panel label="Darwin Core Archive">
          <p className="text-xs text-gray-400 mb-4 min-h-[3.5rem]">GBIF-compatible ZIP (occurrence.txt, dna-derived-data.txt, eml.xml) for manual submission to a GBIF IPT.</p>
          <ExportBtn onClick={() => downloadExport(getDwcaUrl(jobId), `relict_dwca_${jobId}.zip`)}><Download className="w-4 h-4" /> DwC-A</ExportBtn>
        </Panel>
        <Panel label="CSV Table">
          <p className="text-xs text-gray-400 mb-4 min-h-[3.5rem]">Flat spreadsheet: ASV sequences, abundances, 7-rank taxonomy, identity scores, reference DB.</p>
          <ExportBtn onClick={() => downloadExport(getCsvUrl(jobId), `relict_asvs_${jobId}.csv`)}><Download className="w-4 h-4" /> CSV</ExportBtn>
        </Panel>
        <Panel label="BIOM (JSON)">
          <p className="text-xs text-gray-400 mb-4 min-h-[3.5rem]">BIOM 1.0 JSON ASV table with taxonomy metadata, for phyloseq and BIOM-compatible tools.</p>
          <ExportBtn onClick={() => downloadExport(getBiomUrl(jobId), `relict_biom_${jobId}.json`)}><Download className="w-4 h-4" /> BIOM</ExportBtn>
        </Panel>
      </div>
    </div>
  );
}
