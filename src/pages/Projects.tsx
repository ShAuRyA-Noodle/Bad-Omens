import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { useAuth } from "@/hooks/use-auth";
import { listProjects, createProject } from "@/lib/api";
import { FolderPlus, FolderGit2, ChevronRight, Loader2 } from "lucide-react";

export default function Projects() {
  const { isAuthenticated, loading } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate("/demo");
  }, [loading, isAuthenticated, navigate]);

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    enabled: isAuthenticated,
  });

  const create = useMutation({
    mutationFn: () => createProject(name.trim(), desc.trim() || undefined),
    onSuccess: () => {
      setName("");
      setDesc("");
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (loading) {
    return <div className="min-h-screen bg-transparent flex items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;
  }

  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-28 sm:pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">
          <div className="mb-8">
            <div className="flex items-center gap-2 text-primary text-xs uppercase tracking-widest mb-3">
              <span className="w-2 h-2 bg-primary animate-pulse" />
              <span>Multi-sample Studies</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-heading font-black text-white uppercase tracking-tighter">
              Projects<span className="text-neon-cyan">.</span>
            </h1>
            <p className="text-sm text-gray-400 mt-2 max-w-2xl">
              Group samples into a study to unlock cross-sample analysis — Bray-Curtis PCoA
              comparing communities across every sample in the project.
            </p>
          </div>

          {/* Create */}
          <div className="border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket mb-6">
            <div className="text-[11px] text-gray-500 uppercase tracking-widest mb-3 flex items-center gap-2">
              <FolderPlus className="w-3.5 h-3.5" /> New Project
            </div>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Project name"
                className="flex-1 px-3 py-2 bg-black border border-white/15 text-sm text-gray-200 focus:border-primary focus:outline-none placeholder-gray-700 min-h-[44px]"
              />
              <input
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="Description (optional)"
                className="flex-1 px-3 py-2 bg-black border border-white/15 text-sm text-gray-200 focus:border-primary focus:outline-none placeholder-gray-700 min-h-[44px]"
              />
              <button
                onClick={() => create.mutate()}
                disabled={!name.trim() || create.isPending}
                className="btn-cyber px-5 py-2 text-xs font-bold uppercase tracking-widest disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]"
              >
                {create.isPending ? "…" : "Create"}
              </button>
            </div>
            {create.isError && <p className="text-xs text-red-400 mt-2">{(create.error as Error).message}</p>}
          </div>

          {/* List */}
          {isLoading ? (
            <div className="border border-white/10 bg-black/40 h-32 animate-pulse" />
          ) : !projects || projects.length === 0 ? (
            <div className="border border-white/15 bg-black/60 p-12 text-center hud-bracket">
              <FolderGit2 className="w-10 h-10 mx-auto text-gray-700 mb-4" />
              <p className="text-gray-400 text-sm">No projects yet. Create one above, then attach analyses to it.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {projects.map((p) => (
                <Link
                  key={p.id}
                  to={`/projects/${p.id}`}
                  className="border border-white/15 bg-black/50 p-4 hover:bg-white/5 hover:border-neon-cyan/40 transition-colors group"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-white font-bold truncate">{p.name}</p>
                      {p.description && <p className="text-[11px] text-gray-500 mt-1 line-clamp-2">{p.description}</p>}
                    </div>
                    <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-neon-cyan shrink-0" />
                  </div>
                  <div className="flex gap-4 mt-3 text-[11px] text-gray-500">
                    <span>{p.job_count} sample{p.job_count === 1 ? "" : "s"}</span>
                    <span className="text-neon-green">{p.succeeded_count} completed</span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
