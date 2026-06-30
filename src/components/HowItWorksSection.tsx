import { useRef } from "react";
import { Copy, Terminal, Server, Cpu } from "lucide-react";
import { motion, useScroll, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

// Each step describes exactly what the real pipeline does. No fabricated
// counts, no machine-learning theatre — these are the actual published,
// deterministic tools invoked by the worker (see backend/worker/pipeline/).
const pipelineSteps = [
  {
    id: "STEP_01",
    command: "> fastp --in1 reads.fastq.gz --cut_front --cut_tail",
    title: "QC_TRIMMING",
    description: "Raw FASTQ reads are quality-trimmed and adapter-clipped with fastp. A JSON report records read counts before and after filtering.",
    icon: Terminal,
    output: "quality-trimmed reads + fastp.json report",
  },
  {
    id: "STEP_02",
    command: "> vsearch --cluster_unoise --uchime3_denovo",
    title: "ASV_INFERENCE",
    description: "Reads are dereplicated, denoised into amplicon sequence variants with vsearch UNOISE3, then de novo dechimerized. Published, deterministic algorithms — no neural network, no black box.",
    icon: Cpu,
    output: "dechimerized ASVs (asvs.fasta)",
  },
  {
    id: "STEP_03",
    command: "> vsearch --usearch_global asvs.fasta --db SILVA",
    title: "TAXONOMY_+_CONSERVATION",
    description: "ASVs are assigned taxonomy against SILVA 138.1 / MIDORI2, then each species is cross-referenced live against GBIF occurrence data and IUCN Red List status.",
    icon: Server,
    output: "lineage + IUCN status per ASV",
  },
  {
    id: "STEP_04",
    command: "> relict provenance --sign ed25519",
    title: "SIGNED_MANIFEST",
    description: "scikit-bio computes diversity metrics, then every input hash, tool version, reference-DB version and output hash is recorded and Ed25519-signed into a publicly verifiable provenance manifest.",
    icon: Copy,
    output: "provenance.json (Ed25519-signed)",
  }
];

export const HowItWorksSection = () => {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start center", "end end"]
  });

  return (
    <section
      ref={containerRef}
      id="pipeline"
      className="relative bg-transparent border-t border-white/5 py-24 sm:py-32"
    >
      <div className="container mx-auto px-4 md:px-8 relative z-10 w-full max-w-5xl">
        <div className="mb-20">
          <div className="flex items-center space-x-2 text-primary font-mono text-xs uppercase tracking-widest mb-4">
            <span className="w-2 h-2 bg-primary"></span>
            <span>Architecture // Pipeline Execution</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-heading font-black text-white uppercase tracking-tighter">
            Data <span className="text-neon-cyan">Topology.</span>
          </h2>
        </div>

        {/* Vertical Pipeline Graph */}
        <div className="relative pl-8 sm:pl-16">
          {/* Main descending pipeline trace line */}
          <div className="absolute top-0 left-[15px] sm:left-[31px] w-[2px] h-full bg-white/10 z-0">
            <motion.div
              className="absolute top-0 left-0 w-full bg-primary"
              style={{ scaleY: scrollYProgress, transformOrigin: "top" }}
            />
          </div>

          <div className="space-y-24 sm:space-y-32">
            {pipelineSteps.map((step, index) => {
              // We reveal the nodes based on scroll depth
              const isActive = useTransform(
                scrollYProgress,
                [0, Math.min(1, index * 0.25), Math.min(1, (index + 0.5) * 0.25)],
                [0, 0, 1]
              );

              const yOffset = useTransform(
                scrollYProgress,
                [0, Math.min(1, index * 0.25), Math.min(1, (index + 0.5) * 0.25)],
                [50, 50, 0]
              );

              return (
                <div key={step.id} className="relative z-10 grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-8">
                  {/* The Node Connection Point */}
                  <motion.div
                    className="absolute -left-[30px] sm:-left-[46px] top-6 w-[30px] h-[30px] rounded-sm border-2 bg-background flex items-center justify-center z-20"
                    style={{
                      borderColor: useTransform(isActive, (v) => v > 0.5 ? "hsl(var(--primary))" : "rgba(255,255,255,0.2)"),
                    }}
                  >
                    <motion.div
                      className="w-[10px] h-[10px]"
                      style={{
                        backgroundColor: useTransform(isActive, (v) => v > 0.5 ? "hsl(var(--primary))" : "transparent"),
                      }}
                    />
                  </motion.div>

                  {/* Step ID / Execution Context */}
                  <motion.div
                    style={{ opacity: isActive, y: yOffset }}
                    className="font-mono text-sm"
                  >
                    <div className="text-gray-500 mb-1">[{step.id}]</div>
                    <div className="text-white font-bold mb-4">{step.title}</div>
                    <div className="hidden md:flex p-3 border border-white/10 bg-white/5 items-start space-x-3 text-gray-400 hud-bracket">
                      <step.icon className="w-5 h-5 text-secondary shrink-0" />
                      <div className="text-xs leading-relaxed">{step.description}</div>
                    </div>
                  </motion.div>

                  {/* Terminal Execution Window */}
                  <motion.div
                    style={{ opacity: isActive, y: yOffset }}
                    className="w-full"
                  >
                    <div className="border border-white/20 bg-black text-xs font-mono w-full shadow-[0_0_15px_rgba(0,0,0,1)]">
                      <div className="border-b border-white/20 bg-white/5 py-1 px-3 flex justify-between text-gray-600">
                        <span>bash 80x24</span>
                        <span>[x]</span>
                      </div>
                      <div className="p-4 sm:p-6 space-y-4">
                        <div className="text-gray-400">
                          <span className="text-secondary">{step.command.split(" ")[0]} </span>
                          <span>{step.command.substring(step.command.indexOf(" ") + 1)}</span>
                        </div>
                        <motion.div
                          className="pt-4 text-neon-green"
                          initial={{ opacity: 0 }}
                          whileInView={{ opacity: 1 }}
                          viewport={{ once: false, margin: "-100px" }}
                          transition={{ delay: 0.3 }}
                        >
                          {step.output}
                        </motion.div>
                        <motion.div
                          className="w-2 h-4 bg-gray-500"
                          animate={{ opacity: [1, 0, 1] }}
                          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                        />
                      </div>
                    </div>

                    {/* Mobile description fallback */}
                    <div className="md:hidden mt-4 text-xs font-mono text-gray-400 border-l border-primary/50 pl-3">
                      {step.description}
                    </div>
                  </motion.div>

                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};