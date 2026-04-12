import { useRef, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, TerminalSquare, ChevronRight } from "lucide-react";
import { motion, useScroll, useTransform } from "framer-motion";

const DNA_BASES = ["A", "C", "G", "T"];

export const HeroSection = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start start", "end start"],
  });

  const backgroundY = useTransform(scrollYProgress, [0, 1], ["0%", "50%"]);
  const mainOpacity = useTransform(scrollYProgress, [0, 0.5], [1, 0]);

  const [sequenceOffset, setSequenceOffset] = useState(0);

  useEffect(() => {
    let animationFrameId: number;
    let lastTime = performance.now();

    const animateSequence = (currentTime: number) => {
      if (currentTime - lastTime > 150) { // Update every 150ms for that choppy terminal feel
        setSequenceOffset(prev => (prev + 1) % 100);
        lastTime = currentTime;
      }
      animationFrameId = requestAnimationFrame(animateSequence);
    };

    animationFrameId = requestAnimationFrame(animateSequence);
    return () => cancelAnimationFrame(animationFrameId);
  }, []);

  return (
    <section ref={containerRef} className="relative min-h-screen flex items-center justify-center overflow-hidden bg-background pt-20 scanline">
      
      {/* HUD Crosshairs */}
      <div className="absolute top-24 left-8 w-4 h-4 border-t-2 border-l-2 border-secondary z-0 opacity-50"></div>
      <div className="absolute top-24 right-8 w-4 h-4 border-t-2 border-r-2 border-secondary z-0 opacity-50"></div>
      <div className="absolute bottom-8 left-8 w-4 h-4 border-b-2 border-l-2 border-secondary z-0 opacity-50"></div>
      <div className="absolute bottom-8 right-8 w-4 h-4 border-b-2 border-r-2 border-secondary z-0 opacity-50"></div>

      {/* Streaming DNA Background */}
      <motion.div 
        className="absolute inset-0 z-0 pointer-events-none opacity-10 font-mono text-[10px] sm:text-xs leading-none overflow-hidden text-primary select-none whitespace-pre-wrap break-all px-8 pb-8 pt-32 text-justify"
        style={{ y: backgroundY }}
      >
        {Array.from({ length: 1500 }).map((_, i) => DNA_BASES[(i + sequenceOffset) % 4]).join('')}
      </motion.div>

      <motion.div 
        className="container mx-auto px-4 sm:px-8 relative z-10 w-full"
        style={{ opacity: mainOpacity }}
      >
        <div className="max-w-4xl border border-white/10 bg-black/60 backdrop-blur-sm p-1">
          {/* Terminal Window Header */}
          <div className="border-b border-white/10 bg-white/5 p-2 flex items-center justify-between">
            <div className="flex space-x-2 px-2">
              <div className="w-3 h-3 bg-red-500/50"></div>
              <div className="w-3 h-3 bg-yellow-500/50"></div>
              <div className="w-3 h-3 bg-green-500/50"></div>
            </div>
            <div className="text-[10px] font-mono text-gray-500">bin/sh - execution_pipeline.sh</div>
            <div className="w-4 h-4 text-gray-500"><TerminalSquare className="w-4 h-4" /></div>
          </div>

          <div className="p-8 sm:p-12 border-b border-white/5 relative">
            {/* Blinking Cursor Box Logo */}
            <div className="mb-8 flex items-center space-x-2">
              <span className="text-secondary font-mono text-sm">&gt; SYSTEM_INITIALIZED</span>
              <motion.div 
                className="w-2 h-4 bg-secondary"
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              />
            </div>

            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, ease: "easeOut" }}
              className="text-5xl sm:text-6xl md:text-7xl font-heading font-black text-white uppercase tracking-tighter leading-[0.9] mb-6"
            >
              Parse the <br />
              <span className="text-neon-cyan">Biosphere.</span>
            </motion.h1>
            
            <p className="font-mono text-gray-400 max-w-xl text-sm sm:text-base leading-relaxed mb-10">
              <span className="text-primary">RUNNING:</span> High-throughput BERT classification over environmental DNA sequences. Transforming raw FASTA dumps into structured ecological topologies.
            </p>

            <div className="flex flex-col sm:flex-row gap-4">
              <Link to="/demo" className="btn-cyber px-8 py-4 flex items-center justify-center font-bold">
                <ChevronRight className="w-4 h-4 mr-2" />
                EXECUTE // PIPELINE
              </Link>
              <Link to="#documentation" className="border border-white/20 text-gray-400 hover:text-white hover:bg-white/10 px-8 py-4 flex items-center justify-center font-mono text-sm transition-colors uppercase">
                READ_DOCS.md
              </Link>
            </div>
          </div>

          {/* Readout Footer */}
          <div className="bg-black/80 p-4 font-mono text-xs flex flex-col sm:flex-row justify-between text-gray-500 border-t border-white/10">
            <div className="flex space-x-8">
              <span><span className="text-primary">LATENCY:</span> 120ms</span>
              <span><span className="text-primary">THROUGHPUT:</span> 4.2k seq/s</span>
            </div>
            <div className="mt-2 sm:mt-0">
              [ TARGET: AQUIRED ]
            </div>
          </div>
        </div>
      </motion.div>
    </section>
  );
};
