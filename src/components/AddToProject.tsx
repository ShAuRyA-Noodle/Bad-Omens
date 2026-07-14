import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { FolderPlus } from "lucide-react";
import { listProjects, attachJobToProject } from "@/lib/api";

export function AddToProject({ jobId }: { jobId: string }) {
  const { data: projects } = useQuery({ queryKey: ["projects"], queryFn: listProjects, retry: false });
  const [sel, setSel] = useState("");
  const qc = useQueryClient();

  const attach = useMutation({
    mutationFn: () => attachJobToProject(sel, jobId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project", sel] });
      qc.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  if (!projects) return null;
  if (projects.length === 0) {
    return (
      <Link to="/projects" className="text-[11px] text-neon-cyan hover:underline inline-flex items-center gap-1">
        <FolderPlus className="w-3 h-3" /> Create a project
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={sel}
        onChange={(e) => setSel(e.target.value)}
        className="bg-black border border-white/15 text-[11px] text-gray-300 px-2 py-1.5 focus:border-primary focus:outline-none max-w-[10rem]"
      >
        <option value="">Add to project…</option>
        {projects.map((p) => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>
      <button
        onClick={() => attach.mutate()}
        disabled={!sel || attach.isPending}
        className="text-[11px] border border-white/15 px-3 py-1.5 text-gray-300 hover:text-neon-cyan disabled:opacity-40 disabled:cursor-not-allowed min-h-[32px]"
      >
        {attach.isSuccess ? "Added ✓" : attach.isPending ? "…" : "Add"}
      </button>
    </div>
  );
}
