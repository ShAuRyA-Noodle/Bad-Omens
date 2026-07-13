import type { ReactNode } from "react";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { useAuth } from "@/hooks/use-auth";
import { listJobs, type JobPublic } from "@/lib/api";
import { cn } from "@/lib/utils";
import { User, FileText, CheckCircle, XCircle, Loader2, LogOut, ChevronRight } from "lucide-react";

export default function Profile() {
  const { user, isAuthenticated, loading, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate("/demo");
  }, [loading, isAuthenticated, navigate]);

  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs-list"],
    queryFn: () => listJobs(50, 0),
    enabled: isAuthenticated,
    refetchInterval: 10000,
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-transparent flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }
  if (!user) return null;

  const jobs = jobsData?.items || [];
  const total = jobsData?.total || 0;
  const done = jobs.filter((j) => j.status === "succeeded").length;
  const failed = jobs.filter((j) => j.status === "failed").length;
  const active = jobs.filter((j) => j.status === "running" || j.status === "queued").length;

  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-28 sm:pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">
          {/* Account header */}
          <div className="border border-white/15 bg-black/60 backdrop-blur-md p-5 sm:p-6 hud-bracket mb-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-14 h-14 border border-primary/40 bg-primary/10 flex items-center justify-center shrink-0">
                  <User className="w-7 h-7 text-neon-green" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-xl sm:text-2xl font-heading font-black text-white uppercase tracking-tight truncate">{user.email}</h1>
                  <p className="text-[11px] text-gray-500 mt-1">
                    {user.role.toUpperCase()} · joined {new Date(user.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
              <button
                onClick={() => { logout(); navigate("/"); }}
                className="text-xs text-red-500 hover:text-red-400 border border-red-500/30 px-4 py-2 hover:bg-red-500/10 transition-colors uppercase flex items-center gap-2 shrink-0 self-start min-h-[44px]"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign Out
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-6">
            <Stat label="Total" value={total} icon={<FileText className="w-4 h-4 text-gray-500" />} />
            <Stat label="Completed" value={done} icon={<CheckCircle className="w-4 h-4 text-neon-green" />} />
            <Stat label="Failed" value={failed} icon={<XCircle className="w-4 h-4 text-red-500" />} />
            <Stat label="Active" value={active} icon={<Loader2 className="w-4 h-4 text-yellow-500" />} />
          </div>

          {/* Job history */}
          <div className="border border-white/15 bg-black/60 backdrop-blur-md hud-bracket">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <span className="text-[11px] text-gray-500 uppercase tracking-widest">Analysis History</span>
              <Link to="/demo" className="text-xs text-neon-cyan hover:text-white border border-white/15 px-3 py-1.5 hover:bg-white/5 transition-colors uppercase min-h-[36px] flex items-center">
                + New
              </Link>
            </div>

            {jobsLoading ? (
              <div className="p-12 text-center text-gray-500 text-xs animate-pulse">Loading history…</div>
            ) : jobs.length === 0 ? (
              <div className="p-12 text-center">
                <FileText className="w-10 h-10 mx-auto text-gray-700 mb-4" />
                <p className="text-gray-400 mb-3 text-sm">No analyses yet.</p>
                <Link to="/demo" className="text-neon-cyan hover:underline text-sm">Upload your first FASTQ →</Link>
              </div>
            ) : (
              <div className="divide-y divide-white/5">
                {jobs.map((job) => <JobRow key={job.id} job={job} />)}
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function Stat({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="border border-white/15 bg-black/50 p-4">
      <div className="flex items-center justify-between mb-2">
        {icon}
        <span className="text-2xl font-bold text-neon-cyan">{value}</span>
      </div>
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
    </div>
  );
}

const STATUS: Record<string, { cls: string; label: string }> = {
  succeeded: { cls: "text-neon-green border-neon-green", label: "DONE" },
  failed: { cls: "text-red-500 border-red-500", label: "FAIL" },
  running: { cls: "text-yellow-500 border-yellow-500", label: "RUNNING" },
  queued: { cls: "text-neon-cyan border-white/30", label: "QUEUED" },
  cancelled: { cls: "text-gray-500 border-gray-600", label: "CANCELLED" },
};

function JobRow({ job }: { job: JobPublic }) {
  const s = STATUS[job.status] || STATUS.queued;
  const created = new Date(job.created_at);
  const runtime = job.started_at && job.finished_at
    ? `${((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000).toFixed(1)}s`
    : "—";
  const clickable = job.status === "succeeded";

  const inner = (
    <div className="flex items-center justify-between gap-3 p-4 hover:bg-white/5 transition-colors group">
      <div className="flex items-center gap-3 min-w-0">
        <span className={cn("text-[10px] font-bold uppercase px-2 py-1 border shrink-0", s.cls)}>{s.label}</span>
        <div className="min-w-0">
          <p className="text-sm text-white truncate">{job.id.slice(0, 12)}…</p>
          <p className="text-[11px] text-gray-500 truncate">
            {created.toLocaleDateString()} {created.toLocaleTimeString()} · {job.amplicon} · {runtime}
            {job.pipeline_version ? ` · v${job.pipeline_version}` : ""}
          </p>
        </div>
      </div>
      {clickable && <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-neon-cyan transition-colors shrink-0" />}
    </div>
  );

  return clickable ? <Link to={`/jobs/${job.id}`}>{inner}</Link> : <div>{inner}</div>;
}
