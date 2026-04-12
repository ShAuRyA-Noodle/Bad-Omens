import { useRef } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Waves, Trees, Droplets, ArrowRight } from "lucide-react";
import { motion, useInView } from "framer-motion";
import { cn } from "@/lib/utils";

const targets = [
  {
    id: "TRG_01",
    title: "MARINE_PELAGIC",
    icon: Waves,
    points: ["[X, Y, Z] DEPTH: -500M", "SALINITY_PROBE: ACTIVE"],
    desc: "Assess ocean health indicators and track elusive chondrichthyes populations via dispersed genetic markers in 10L grab samples.",
    color: "from-cyan-500/20 to-blue-500/5",
    borderH: "border-cyan-500/50",
  },
  {
    id: "TRG_02",
    title: "TERRESTRIAL_LENTIC",
    icon: Trees,
    points: ["GRID_COORD: 45N 122W", "RIPARIAN_ZONE: TRUE"],
    desc: "Identify entire mammalian presence matrices from isolated water holes. Tracks shedding from dermal layers and saliva.",
    color: "from-green-500/20 to-emerald-500/5",
    borderH: "border-green-500/50",
  },
  {
    id: "TRG_03",
    title: "LOTIC_SYSTEMS",
    icon: Droplets,
    points: ["FLOW_RATE: 12m/s", "TURBIDITY: HIGH"],
    desc: "Longitudinal watershed biodiversity tracking. Reconstruct upstream macroinvertebrate and teleost communities.",
    color: "from-teal-500/20 to-cyan-500/5",
    borderH: "border-teal-500/50",
  }
];

export const UseCasesSection = () => {
  return (
    <section className="py-32 bg-background relative font-mono overflow-hidden">
      <div className="absolute inset-0 z-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 mix-blend-overlay pointer-events-none" />
      
      {/* Background wireframe orb */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80vw] h-[80vw] border border-white/5 rounded-full z-0 pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] border border-white/10 rounded-full z-0 pointer-events-none flex items-center justify-center">
        <div className="absolute w-full h-[1px] bg-white/5" />
        <div className="absolute h-full w-[1px] bg-white/5" />
      </div>

      <div className="container mx-auto px-4 lg:px-8 relative z-10 max-w-6xl">
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mb-16"
        >
          <div className="flex items-center space-x-2 text-secondary text-xs uppercase tracking-widest mb-4">
            <span className="w-2 h-2 bg-secondary animate-pulse"></span>
            <span>Target Acquisition</span>
          </div>
          <h2 className="text-4xl md:text-5xl font-heading font-black text-white uppercase tracking-tighter w-full max-w-2xl">
            Acquire biological telemetry across <br />
            <span className="text-primary italic font-light drop-shadow-[0_0_15px_rgba(57,255,20,0.5)]">all primary biomes.</span>
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-24">
          {targets.map((trg, i) => (
            <motion.div
              key={trg.id}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              className={cn(
                "group relative bg-black/40 border border-white/20 hover:bg-black/60 transition-all duration-300 p-6 flex flex-col justify-between hud-panel cursor-crosshair min-h-[400px]",
                "hover:" + trg.borderH
              )}
            >
              <div className={cn("absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none", trg.color)} />
              
              {/* Corner brackets */}
              <div className="absolute top-0 left-0 w-4 h-4 border-t border-l border-white/50 group-hover:border-primary transition-colors" />
              <div className="absolute top-0 right-0 w-4 h-4 border-t border-r border-white/50 group-hover:border-primary transition-colors" />
              <div className="absolute bottom-0 left-0 w-4 h-4 border-b border-l border-white/50 group-hover:border-primary transition-colors" />
              <div className="absolute bottom-0 right-0 w-4 h-4 border-b border-r border-white/50 group-hover:border-primary transition-colors" />

              <div className="relative z-10">
                <div className="flex justify-between items-start mb-10">
                  <div className="text-xs text-gray-500 font-bold">[{trg.id}]</div>
                  <trg.icon className="w-6 h-6 text-gray-400 group-hover:text-primary transition-colors" />
                </div>

                <div className="mb-4">
                  <h3 className="text-2xl font-bold text-white mb-2">{trg.title}</h3>
                  <div className="space-y-1">
                    {trg.points.map(p => (
                      <div key={p} className="text-[10px] text-gray-500 flex items-center">
                        <ChevronRight className="w-3 h-3 mr-1 text-secondary" /> {p}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="relative z-10 text-sm text-gray-400 font-light leading-relaxed group-hover:text-gray-300 transition-colors border-l border-white/10 pl-4 py-2">
                {trg.desc}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Console Execution / CTA Box */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="border border-white/20 bg-black max-w-4xl mx-auto shadow-2xl relative"
        >
          <div className="bg-white/5 border-b border-white/20 py-2 px-4 flex items-center justify-between text-xs text-gray-500">
            <div>relict_sys@production:~</div>
            <div className="flex space-x-2">
              <div className="w-2 h-2 rounded-full border border-gray-500 relative"><span className="absolute inset-0 bg-gray-500"></span></div>
              <div className="w-2 h-2 rounded-full border border-gray-500 relative"><span className="absolute inset-0 bg-gray-500"></span></div>
              <div className="w-2 h-2 rounded-full border border-gray-500 relative"><span className="absolute inset-0 bg-gray-500"></span></div>
            </div>
          </div>
          <div className="p-8 sm:p-12 text-center relative overflow-hidden">
            <h3 className="text-3xl md:text-5xl font-heading font-bold text-white mb-6 uppercase tracking-tighter">
              Execute <span className="text-neon-cyan">Analytics.</span>
            </h3>
            <p className="text-gray-400 mb-10 max-w-lg mx-auto text-sm">
              Deploy the analysis algorithms on demo sequences to observe classification limits and topological output mappings.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-6 justify-center">
              <Link 
                to="/demo"
                className="btn-cyber px-8 py-4 font-bold text-lg flex items-center justify-center tracking-widest"
              >
                ./RUN_DEMO
                <ArrowRight className="w-5 h-5 ml-3" />
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};