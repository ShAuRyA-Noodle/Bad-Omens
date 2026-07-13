import { Link } from "react-router-dom";
import { Github, Mail, ExternalLink, Activity } from "lucide-react";
import { useScroll, useTransform, motion } from "framer-motion";
import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { checkHealth } from "@/lib/api";

const ASCII_LOGO = `
██████╗ ███████╗██╗     ██╗ ██████╗████████╗
██╔══██╗██╔════╝██║     ██║██╔════╝╚══██╔══╝
██████╔╝█████╗  ██║     ██║██║        ██║
██╔══██╗██╔══╝  ██║     ██║██║        ██║
██║  ██║███████╗███████╗██║╚██████╗   ██║
╚═╝  ╚═╝╚══════╝╚══════╝╚═╝ ╚═════╝   ╚═╝
`;

type FooterLink = { name: string; href: string; external?: boolean };

const footerLinks: Record<string, FooterLink[]> = {
  SYSTEMS: [
    { name: "INIT // DEMO", href: "/demo" },
    { name: "IMPCT_MTRX", href: "/impact" },
    { name: "MAN_PAGES", href: "/about" },
  ],
  VERIFY: [
    { name: "PUBLIC_KEY", href: "/public-key", external: true },
  ],
  EXT_DB: [
    { name: "NCBI_SRA", href: "https://www.ncbi.nlm.nih.gov/sra", external: true },
    { name: "GBIF_ORG", href: "https://www.gbif.org/", external: true },
    { name: "IUCN_REDLIST", href: "https://www.iucnredlist.org/", external: true },
  ],
};

export const Footer = () => {
  const currentYear = new Date().getFullYear();
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end end"],
  });

  const y = useTransform(scrollYProgress, [0, 1], ["-20%", "0%"]);
  const opacity = useTransform(scrollYProgress, [0, 1], [0.5, 1]);

  // Real, living status — polls the actual /health endpoint. No fabricated
  // telemetry: if the API is unreachable this honestly reads OFFLINE.
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,
    retry: false,
  });
  const apiStatus = isLoading ? "…" : isError || !health ? "OFFLINE" : health.status === "ok" ? "ONLINE" : health.status.toUpperCase();
  const statusColor = apiStatus === "ONLINE" ? "text-neon-green" : apiStatus === "OFFLINE" ? "text-red-500" : "text-yellow-500";

  const statusRows: { label: string; value: string; accent?: string }[] = [
    { label: "API_STATUS", value: apiStatus, accent: statusColor },
    { label: "API_VERSION", value: health?.version ? `v${health.version}` : "—" },
    { label: "PIPELINE", value: "fastp · vsearch UNOISE3 · scikit-bio" },
    { label: "REFERENCES", value: "SILVA 138.1 · MIDORI2 GB269" },
    { label: "PROVENANCE", value: "Ed25519-signed manifests" },
  ];

  return (
    <footer
      ref={containerRef}
      className="relative bg-transparent text-white overflow-hidden py-0 border-t-2 border-white/10 font-mono"
      style={{ minHeight: "80vh" }}
    >
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-[0.03] mix-blend-overlay pointer-events-none" />

      <motion.div
        className="w-full h-full flex flex-col justify-between pt-16 sm:pt-24 pb-8 px-4 md:px-8 relative z-10"
        style={{ y, opacity }}
      >
        <div className="max-w-7xl mx-auto w-full grid grid-cols-1 lg:grid-cols-[1fr_2fr] gap-12 sm:gap-24 mb-16">

          {/* Left: Real system status (bound to /health) */}
          <div className="border border-white/20 bg-black/60 p-4 w-full min-h-48 overflow-hidden relative shadow-[0_0_20px_rgba(0,0,0,1)]">
            <div className="flex items-center text-xs text-primary mb-4 pb-2 border-b border-white/10">
              <Activity className="w-4 h-4 mr-2" />
              <span>SYSTEM STATUS</span>
              <span className="ml-auto text-[10px] text-gray-600">live · 30s</span>
            </div>
            <div className="text-[10px] sm:text-xs space-y-2">
              {statusRows.map((row) => (
                <div key={row.label} className="flex items-start justify-between gap-3 border-b border-white/5 pb-1">
                  <span className="text-gray-600 shrink-0">{row.label}</span>
                  <span className={cn("text-right break-words", row.accent ?? "text-gray-300")}>{row.value}</span>
                </div>
              ))}
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
                  {links.map((link) => {
                    const inner = (
                      <>
                        <span className="text-primary opacity-0 group-hover:opacity-100 mr-2 transition-opacity">&gt;&gt;</span>
                        <span>{link.name}</span>
                        {link.external && <ExternalLink className="w-3 h-3 ml-2 opacity-30 group-hover:opacity-100" />}
                      </>
                    );
                    const classes =
                      "text-gray-500 hover:text-white hover:bg-white/10 transition-colors flex items-center group py-2 px-2 -ml-2 min-h-[44px]";
                    return (
                      <li key={link.name}>
                        {link.external ? (
                          <a href={link.href} target="_blank" rel="noopener noreferrer" className={classes}>{inner}</a>
                        ) : (
                          <Link to={link.href} className={classes}>{inner}</Link>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* ASCII Logo Section */}
        <div className="w-full flex-grow flex flex-col items-center justify-end mx-auto relative px-4">
          <div className="flex flex-col sm:flex-row items-center w-full justify-between mb-8 border-b border-white/20 pb-4 mt-16 sm:mt-0">
            <div className="flex items-center space-x-6 text-gray-500">
              <a href="https://github.com/ShAuRyA-Noodle/Bad-Omens" target="_blank" rel="noopener noreferrer" aria-label="GitHub repository" className="hover:text-white hover:bg-white/10 p-2 border border-transparent hover:border-white/20 transition-all">
                <Github className="w-5 h-5" />
              </a>
              <a href="mailto:workwithshaurya10@gmail.com" aria-label="Email the author" className="hover:text-white hover:bg-white/10 p-2 border border-transparent hover:border-white/20 transition-all">
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

          <div className="w-full border-t border-white/20 pt-4 flex flex-col sm:flex-row justify-between gap-2 text-[10px] text-gray-600">
            <div>v0.2.0 | BUILD {currentYear}</div>
            <div className="sm:text-right">WARN: RESEARCH SCOPE ONLY. NOT CLINICALLY OR LEGALLY CERTIFIED.</div>
          </div>
        </div>
      </motion.div>
    </footer>
  );
};
