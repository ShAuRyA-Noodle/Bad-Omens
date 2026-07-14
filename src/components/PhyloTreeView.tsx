import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Trees } from "lucide-react";
import { getJobTree } from "@/lib/api";

// ─── Minimal Newick parser ────────────────────────────────────────────
// Handles the FastTree output grammar: (A:len,B:len)support:len; — names,
// branch lengths, and internal support labels. No external dependency.
interface TreeNode {
  name: string;
  length: number;
  children: TreeNode[];
}

function parseNewick(s: string): TreeNode {
  let i = 0;
  const text = s.trim();

  function node(): TreeNode {
    const n: TreeNode = { name: "", length: 0, children: [] };
    if (text[i] === "(") {
      i++; // consume '('
      do {
        n.children.push(node());
      } while (text[i] === "," && i++ < text.length);
      i++; // consume ')'
    }
    // label (name or internal support), up to :,),, or ;
    let label = "";
    while (i < text.length && !":,()".includes(text[i]) && text[i] !== ";") {
      label += text[i++];
    }
    n.name = label;
    if (text[i] === ":") {
      i++; // consume ':'
      let num = "";
      while (i < text.length && !",()".includes(text[i]) && text[i] !== ";") {
        num += text[i++];
      }
      n.length = parseFloat(num) || 0;
    }
    return n;
  }

  return node();
}

// ─── Layout: rectangular phylogram ────────────────────────────────────
interface Laid extends TreeNode {
  x: number;   // cumulative branch length from root (depth)
  y: number;   // vertical position
  children: Laid[];
}

function layout(root: TreeNode): { nodes: Laid[]; leaves: Laid[]; maxX: number; count: number } {
  const leaves: Laid[] = [];
  const nodes: Laid[] = [];
  let leafIndex = 0;
  let maxX = 0;

  function walk(n: TreeNode, depth: number): Laid {
    const x = depth + n.length;
    maxX = Math.max(maxX, x);
    const laid: Laid = { ...n, x, y: 0, children: [] };
    if (n.children.length === 0) {
      laid.y = leafIndex++;
      leaves.push(laid);
    } else {
      laid.children = n.children.map((c) => walk(c, x));
      laid.y = laid.children.reduce((a, c) => a + c.y, 0) / laid.children.length;
    }
    nodes.push(laid);
    return laid;
  }

  walk(root, 0);
  return { nodes, leaves, maxX, count: leafIndex };
}

export function PhyloTreeView({ jobId }: { jobId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["job-tree", jobId],
    queryFn: () => getJobTree(jobId),
    retry: false,
  });

  const model = useMemo(() => {
    if (!data?.newick) return null;
    try {
      return layout(parseNewick(data.newick));
    } catch {
      return null;
    }
  }, [data?.newick]);

  if (isLoading) return <div className="h-64 animate-pulse bg-black/40 border border-white/10" />;

  if (!data || !model || model.count === 0) {
    return (
      <div className="border border-white/15 bg-black/60 backdrop-blur-md hud-bracket p-6">
        <div className="flex items-center gap-2 text-[11px] text-gray-500 uppercase tracking-widest mb-3">
          <Trees className="w-3.5 h-3.5" /> Phylogenetic tree
        </div>
        <p className="text-sm text-gray-400 py-6 text-center">
          No tree for this sample — a phylogenetic tree needs at least 3 ASVs.
        </p>
      </div>
    );
  }

  // ─── SVG geometry ───────────────────────────────────────────────────
  const rowH = 22;
  const padTop = 16;
  const padBottom = 16;
  const labelW = 180;
  const plotW = 640;
  const height = padTop + padBottom + model.count * rowH;
  const scaleX = (x: number) => (model.maxX > 0 ? (x / model.maxX) * plotW : 0);
  const scaleY = (y: number) => padTop + y * rowH + rowH / 2;

  const edges: { x1: number; y1: number; x2: number; y2: number }[] = [];
  const verticals: { x: number; y1: number; y2: number }[] = [];
  for (const n of model.nodes) {
    const parentX = n.x - n.length;
    edges.push({ x1: scaleX(parentX), y1: scaleY(n.y), x2: scaleX(n.x), y2: scaleY(n.y) });
    if (n.children.length > 0) {
      const ys = n.children.map((c) => scaleY(c.y));
      verticals.push({ x: scaleX(n.x), y1: Math.min(...ys), y2: Math.max(...ys) });
    }
  }

  return (
    <div className="border border-white/15 bg-black/60 backdrop-blur-md hud-bracket p-4 sm:p-6">
      <div className="flex items-center justify-between text-[11px] text-gray-500 uppercase tracking-widest mb-4 border-b border-white/10 pb-2">
        <span className="flex items-center gap-2"><Trees className="w-3.5 h-3.5" /> Phylogenetic tree · {data.method}</span>
        <span className="text-gray-600">
          {data.n_tips} ASVs{data.faith_pd != null && <> · Faith's PD <span className="text-neon-green">{data.faith_pd.toFixed(3)}</span></>}
        </span>
      </div>

      <div className="w-full overflow-x-auto">
        <svg
          viewBox={`0 0 ${plotW + labelW + 16} ${height}`}
          width="100%"
          style={{ minWidth: 520, maxHeight: 520 }}
          fontFamily="monospace"
        >
          {verticals.map((v, i) => (
            <line key={`v${i}`} x1={v.x} y1={v.y1} x2={v.x} y2={v.y2}
              stroke="rgba(0,240,255,0.5)" strokeWidth={1.2} />
          ))}
          {edges.map((e, i) => (
            <line key={`e${i}`} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2}
              stroke="rgba(0,240,255,0.7)" strokeWidth={1.2} />
          ))}
          {model.leaves.map((leaf, i) => (
            <g key={`l${i}`}>
              <circle cx={scaleX(leaf.x)} cy={scaleY(leaf.y)} r={2.5} fill="#39ff14" />
              <text
                x={scaleX(leaf.x) + 8}
                y={scaleY(leaf.y) + 3.5}
                fontSize={11}
                fill="#cbd5e1"
              >
                {leaf.name.length > 22 ? `${leaf.name.slice(0, 22)}…` : leaf.name}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <p className="text-[11px] text-gray-500 mt-2">
        De-novo maximum-likelihood tree (MAFFT alignment → FastTree GTR+CAT). Horizontal distance is
        evolutionary divergence; Faith's PD is the total branch length spanning all tips.
      </p>
    </div>
  );
}
