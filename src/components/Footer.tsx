import { Link } from "react-router-dom";
import { Github, Mail, ExternalLink, Activity } from "lucide-react";
import { useScroll, useTransform, motion } from "framer-motion";
import { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";

const ASCII_LOGO = `
██████╗ ███████╗██╗     ██╗ ██████╗████████╗
██╔══██╗██╔════╝██║     ██║██╔════╝╚══██╔══╝
██████╔╝█████╗  ██║     ██║██║        ██║   
██╔══██╗██╔══╝  ██║     ██║██║        ██║   
██║  ██║███████╗███████╗██║╚██████╗   ██║   
╚═╝  ╚═╝╚══════╝╚══════╝╚═╝ ╚═════╝   ╚═╝   
`;

export const Footer = () => {
  const currentYear = new Date().getFullYear();
  const containerRef = useRef<HTMLDivElement>(null);
  const [logMessages, setLogMessages] = useState<string[]>([]);
  
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end end"]
  });

  const y = useTransform(scrollYProgress, [0, 1], ["-20%", "0%"]);
  const opacity = useTransform(scrollYProgress, [0, 1], [0.5, 1]);

  useEffect(() => {
    const logs = [
      "SYNCHRONIZING REPOSITORY INDEX...",
      "FETCHING LATEST NCBI_GENBANK RELEASES",
      "UPDATING SILVA_138.1 TAXONOMY TREE",
      "RECALIBRATING INFERENCE MODULES",
      "SYS DAEMON RUNNING OK",
      "MEM: 24.5 GB / 128 GB [ OK ]",
    ];
    let idx = 0;
    
    const interval = setInterval(() => {
      setLogMessages(prev => {
        const newLogs = [...prev, `[${new Date().toISOString().split('T')[1].substring(0,8)}] ` + logs[idx % logs.length]];
        if (newLogs.length > 5) newLogs.shift();
        return newLogs;
      });
      idx++;
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  const footerLinks = {
    SYSTEMS: [
      { name: "INIT // DEMO", href: "/demo" },
      { name: "VIEW_LOGS", href: "/visualize" },
      { name: "IMPCT_MTRX", href: "/impact" },
    ],
    NODE_CMD: [
      { name: "MAN_PAGES", href: "/about" },
    ],
    EXT_DB: [
      { name: "NCBI_SRA", href: "https://www.ncbi.nlm.nih.gov/sra", external: true },
      { name: "MGNIFY_API", href: "https://www.ebi.ac.uk/metagenomics/", external: true },
      { name: "QIIME2_CORE", href: "https://qiime2.org/", external: true },
    ],
  };

  return (
    <footer 
      ref={containerRef}
      className="relative bg-black text-white overflow-hidden py-0 border-t-2 border-white/10 font-mono"
      style={{ minHeight: "80vh" }}
    >
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.03] mix-blend-overlay pointer-events-none" />
      
      <motion.div 
        className="w-full h-full flex flex-col justify-between pt-16 sm:pt-24 pb-8 px-4 md:px-8 relative z-10"
        style={{ y, opacity }}
      >
        <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 sm:gap-24 mb-16">
          
          {/* Left: Terminal Logging View */}
          <div className="border border-white/20 bg-black/60 p-4 w-full h-48 overflow-hidden relative shadow-[0_0_20px_rgba(0,0,0,1)]">
            <div className="flex items-center text-xs text-primary mb-4 pb-2 border-b border-white/10">
              <Activity className="w-4 h-4 mr-2" />
              <span>SYSTEM EVENT BUS</span>
            </div>
            <div className="text-[10px] sm:text-xs text-gray-500 space-y-1">
              {logMessages.map((log, i) => (
                <div key={i} className={cn("truncate", i === logMessages.length - 1 && "text-neon-cyan")}>{log}</div>
              ))}
              <div className="text-neon-cyan animate-pulse">_</div>
            </div>
          </div>

          {/* Right: Structural Links */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-8 text-xs sm:text-sm">
            {Object.entries(footerLinks).map(([category, links]) => (
              <div key={category}>
                <h3 className="font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2">
                  <span className="text-primary mr-2">+</span>{category}
                </h3>
                <ul className="space-y-4">
                  {links.map((link) => (
                    <li key={link.name}>
                      <a 
                        href={link.href}
                        target={link.external ? "_blank" : "_self"}
                        className="text-gray-500 hover:text-white hover:bg-white/10 transition-colors flex items-center group py-1 px-2 -ml-2"
                      >
                        <span className="text-primary opacity-0 group-hover:opacity-100 mr-2 transition-opacity">&gt;&gt;</span>
                        <span>{link.name}</span>
                        {link.external && <ExternalLink className="w-3 h-3 ml-2 opacity-30 group-hover:opacity-100 border-b border-transparent" />}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* ASCII Logo Section */}
        <div className="w-full flex-grow flex flex-col items-center justify-end mx-auto relative px-4">
          <div className="flex flex-col sm:flex-row items-center w-full justify-between mb-8 border-b border-white/20 pb-4 mt-16 sm:mt-0">
            <div className="flex items-center space-x-6 text-gray-500">
              <a href="https://github.com/ShAuRyA-Noodle/Bad-Omens" target="_blank" rel="noreferrer" className="hover:text-white hover:bg-white/10 p-2 border border-transparent hover:border-white/20 transition-all">
                <Github className="w-5 h-5" />
              </a>
              <a href="mailto:spunj_be23@thapar.edu" className="hover:text-white hover:bg-white/10 p-2 border border-transparent hover:border-white/20 transition-all">
                <Mail className="w-5 h-5" />
              </a>
            </div>
            <div className="text-xs text-gray-500 mt-4 sm:mt-0 text-right">
              <div>AUTHOR: SHAURYA PUNJ</div>
              <div>LICENSE: MIT OPEN-SOURCE</div>
            </div>
          </div>
          
          <div className="w-full relative py-8 flex justify-center text-neon-cyan/80">
            <pre className="font-mono text-[6px] sm:text-[10px] md:text-sm lg:text-md leading-tight text-center drop-shadow-[0_0_15px_rgba(0,240,255,0.4)] block">
              {ASCII_LOGO}
            </pre>
          </div>

          <div className="w-full border-t border-white/20 pt-4 flex justify-between text-[10px] text-gray-600">
            <div>v0.1.0-dev | BUILD {currentYear}</div>
            <div className="text-right">WARN: RESEARCH SCOPE ONLY. EXTRAPOLATION FORBIDDEN.</div>
          </div>
        </div>
      </motion.div>
    </footer>
  );
};
