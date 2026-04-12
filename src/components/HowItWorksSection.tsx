import { useRef } from "react";
import { Copy, Terminal, Server, Cpu } from "lucide-react";
import { motion, useScroll, useTransform } from "framer-motion";
import { cn } from "@/lib/utils";

const pipelineSteps = [
  {
    id: "STEP_01",
    command: "> node ingest.js --format fastq --quality=high",
    title: "SEQ_INGESTION",
    description: "Raw FASTA/Q payloads parsed. Quality filters apply Phred thresholds and trim adapter sequences in constant time.",
    icon: Terminal,
    output: "142,305 reads ingested [status: ok]",
  },
  {
    id: "STEP_02", 
    command: "> py inference.py --model dna-bert-v2 --parallel",
    title: "AI_INFERENCE",
    description: "Transformer arrays map taxonomic barcodes. High-dimensional embeddings cluster ecological features.",
    icon: Cpu,
    output: "Batch processed: 0.18s/seq",
  },
  {
    id: "STEP_03",
    command: "> curl -X POST https://api.ncbi /align",
    title: "DB_ALIGNMENT", 
    description: "Asynchronous requests to globally distributed curated bio-databases establish definitive lineage constraints.",
    icon: Server,
    output: "NCBI connected. SILVA mapped.",
  },
  {
    id: "STEP_04",
    command: "> generate_report --format json,viz",
    title: "TOPOLOGY_OUTPUT",
    description: "A functional ecosystem matrix is compiled containing relative abundance and Shannon-Wiener computations.",
    icon: Copy,
    output: "relict_manifest.json created.",
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
      className="relative bg-background border-t border-white/5 py-24 sm:py-32"
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