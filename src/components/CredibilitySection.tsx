import { useRef, useEffect, useState } from "react";
import { motion, useInView } from "framer-motion";
import { ShieldAlert, Terminal } from "lucide-react";

const dbMounts = [
  { id: "mnt_01", name: "SILVA_138.1", type: "16S_18S_rRNA", status: "OK", latency: "12ms" },
  { id: "mnt_02", name: "MIDORI2", type: "COI_12S", status: "OK", latency: "24ms" },
  { id: "mnt_03", name: "GBIF_GLOBAL", type: "GEO_DISTR", status: "OK", latency: "45ms" },
  { id: "mnt_04", name: "IUCN_REDLIST", type: "CONSRV_STAT", status: "OK", latency: "18ms" },
  { id: "mnt_05", name: "NCBI_GENBANK", type: "SEQ_ARCHIVE", status: "SYNCING", latency: "112ms" },
];

const Counter = ({ from, to, decimal = false }: { from: number; to: number; decimal?: boolean }) => {
  const [count, setCount] = useState(from);
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (inView) {
      let startTime: number;
      let animationFrame: number;
      const duration = 2000;

      const animate = (time: number) => {
        if (!startTime) startTime = time;
        const progress = Math.min((time - startTime) / duration, 1);
        const ease = 1 - Math.pow(1 - progress, 5); // super fast start, slow end
        setCount(from + (to - from) * ease);

        if (progress < 1) {
          animationFrame = requestAnimationFrame(animate);
        }
      };
      
      const timeoutId = setTimeout(() => {
        animationFrame = requestAnimationFrame(animate);
      }, 500);

      return () => {
        clearTimeout(timeoutId);
        cancelAnimationFrame(animationFrame);
      };
    }
  }, [inView, from, to]);

  return <span ref={ref}>{decimal ? count.toFixed(1) : Math.floor(count)}</span>;
};

export const CredibilitySection = () => {
  return (
    <section className="py-24 bg-background border-t border-white/5 relative overflow-hidden font-mono">
      <div className="container mx-auto px-4 md:px-8 max-w-6xl">
        
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-12">
          
          {/* Left Column - Diagnostic Readouts */}
          <div className="space-y-8">
            <div>
              <div className="flex items-center space-x-2 text-primary text-xs uppercase tracking-widest mb-4">
                <span className="w-2 h-2 bg-primary animate-pulse"></span>
                <span>System Architecture</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-heading font-black text-white uppercase tracking-tighter mb-4">
                Global <span className="text-neon-cyan">Mounts.</span>
              </h2>
              <p className="text-sm text-gray-400">
                Data pipeline inherently relies on version-pinned public reference databases. Sequence alignments are immutable and cryptographically audited.
              </p>
            </div>

            {/* Performance Metrics Terminal */}
            <div className="border border-white/20 bg-black p-6 hud-bracket shadow-[0_0_15px_rgba(0,0,0,1)]">
              <div className="flex justify-between text-xs text-gray-500 mb-6 border-b border-white/10 pb-2">
                <span>SYSTEM_CAPABILITIES</span>
                <span>PERF_MONITOR</span>
              </div>

              <div className="space-y-6">
                <div>
                  <div className="text-xs text-gray-400 mb-1">TOTAL_REFERENCE_SEQUENCES</div>
                  <div className="text-3xl font-bold text-white flex items-baseline">
                    <span className="text-neon-cyan mr-1">&gt;</span>
                    <Counter from={0} to={65} />
                    <span className="text-primary text-lg ml-2">M+</span>
                  </div>
                </div>
                
                <div>
                  <div className="text-xs text-gray-400 mb-1">TAXONOMIC_PRECISION_LIMIT</div>
                  <div className="text-3xl font-bold text-white flex items-baseline">
                    <span className="text-neon-cyan mr-1">&gt;</span>
                    <Counter from={80} to={99.8} decimal />
                    <span className="text-primary text-lg ml-2">%</span>
                  </div>
                </div>

                <div>
                  <div className="text-xs text-gray-400 mb-1">PROVENANCE_HASH_MATCH</div>
                  <div className="text-3xl font-bold text-white flex items-baseline">
                    <span className="text-neon-cyan mr-1">&gt;</span>
                    <Counter from={0} to={100} />
                    <span className="text-primary text-lg ml-2">%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Server/Database Mount Log */}
          <div>
            <div className="border border-white/20 bg-[#0a0a0a] w-full h-full min-h-[400px] flex flex-col">
              <div className="bg-white/5 border-b border-white/20 py-2 px-4 flex items-center justify-between text-xs text-gray-400">
                <div className="flex items-center space-x-2">
                  <Terminal className="w-3 h-3" />
                  <span>mount_databases.sh</span>
                </div>
              </div>
              
              <div className="p-4 sm:p-6 text-xs sm:text-sm text-gray-300 font-mono flex-grow space-y-2 overflow-hidden relative">
                <div className="text-gray-500 mb-4 font-bold"># Initializing remote volumes...</div>
                
                {dbMounts.map((db, i) => (
                  <motion.div 
                    key={db.id}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.5 + i * 0.15 }}
                    className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/5 pb-2"
                  >
                    <div className="flex space-x-4">
                      <span className="text-gray-600">[{db.id}]</span>
                      <span className="text-neon-cyan font-bold w-32">{db.name}</span>
                      <span className="text-gray-500 hidden sm:inline-block w-32 truncate">{db.type}</span>
                    </div>
                    <div className="flex justify-between sm:justify-end sm:space-x-8 mt-1 sm:mt-0">
                      <span className={db.status === "OK" ? "text-neon-green" : "text-yellow-500"}>
                        {db.status}
                      </span>
                      <span className="text-gray-600 text-right w-12">{db.latency}</span>
                    </div>
                  </motion.div>
                ))}

                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 2 }}
                  className="mt-6 pt-4 text-green-500 font-bold"
                >
                  Volumes mounted successfully. System ready for query.
                </motion.div>
                <div className="mt-2 text-gray-500">
                  root@relict-node-01:~# <motion.span animate={{opacity: [1,0,1]}} transition={{duration: 1, repeat: Infinity}}>_</motion.span>
                </div>
              </div>
            </div>
          </div>
          
        </div>

        {/* Warning Banner */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-16 border border-yellow-500/50 bg-yellow-500/5 p-6 flex flex-col md:flex-row md:items-center gap-6"
        >
          <ShieldAlert className="w-8 h-8 text-yellow-500 shrink-0" />
          <div>
            <h4 className="text-yellow-500 font-bold text-sm uppercase mb-1 drop-shadow-[0_0_10px_rgba(234,179,8,0.3)]">ATTENTION: Research Scope Limitation</h4>
            <p className="text-xs text-gray-400 leading-relaxed">
              Output manifests are intended for <span className="text-white">environmental studies, baseline monitoring, and bioinformatics research</span>. RELICT_SYS outputs are NOT clinically, legally, or forensically certified. 
            </p>
          </div>
        </motion.div>
        
      </div>
    </section>
  );
};