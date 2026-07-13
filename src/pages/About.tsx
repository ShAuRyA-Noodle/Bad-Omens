import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Terminal, Database, ShieldAlert, BookOpen, ExternalLink, Mail, Github, Linkedin } from "lucide-react";

const About = () => {
  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">

          <div className="mb-16">
            <div className="flex items-center space-x-2 text-primary text-xs uppercase tracking-widest mb-4">
              <span className="w-2 h-2 bg-primary"></span>
              <span>System Documentation</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-heading font-black text-white uppercase tracking-tighter mb-4 flex items-center">
              Architecture <span className="text-neon-cyan ml-3">Nodes.</span>
              <Terminal className="w-8 h-8 ml-4 text-gray-500" />
            </h1>
            <p className="text-sm text-gray-400 max-w-2xl border-l border-white/20 pl-4 py-1">
              RELIC_SYS is engineered to push environmental DNA methodologies beyond academic silos. By combining modern AI, massive concurrency, and strict scientific provenance, we synthesize actionable endpoints.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-8 mb-16">
            {/* Master Node Panel */}
            <div className="border border-secondary bg-black/60 backdrop-blur-md p-6 hud-panel relative shadow-[inset_0_0_30px_rgba(0,240,255,0.1)]">
              <div className="absolute top-0 right-0 p-2 bg-secondary text-black text-[10px] font-bold uppercase tracking-widest">
                SYS_ADMIN
              </div>
              <div className="mb-6">
                <div className="text-white font-bold text-xl uppercase tracking-widest mb-1">Shaurya Punj</div>
                <div className="text-secondary text-xs uppercase">Primary Architect // Full-Stack Eng</div>
              </div>
              <div className="text-xs text-gray-400 leading-relaxed space-y-4 font-light">
                <p>Relict is a fully independent, end-to-end research platform designed, engineered, and deployed by a single developer.</p>
                <p>Every layer of the system - research design, machine learning integration, database engineering, visualization, and deployment - has been independently built to meet real-world scientific needs.</p>
              </div>
              <div className="mt-8 pt-4 border-t border-secondary/30 flex items-center space-x-4">
                <a href="https://github.com/ShAuRyA-Noodle" target="_blank" rel="noopener noreferrer" className="w-8 h-8 rounded border border-secondary/50 flex items-center justify-center text-secondary hover:bg-secondary/20 transition-colors">
                  <Github className="w-4 h-4" />
                </a>
                <a href="https://www.linkedin.com/in/shaurya-punj-2287513b3/" target="_blank" rel="noopener noreferrer" className="w-8 h-8 rounded border border-secondary/50 flex items-center justify-center text-secondary hover:bg-secondary/20 transition-colors">
                  <Linkedin className="w-4 h-4" />
                </a>
                <a href="https://www.shauryapunj.com/contact" target="_blank" rel="noopener noreferrer" className="w-8 h-8 rounded border border-secondary/50 flex items-center justify-center text-secondary hover:bg-secondary/20 transition-colors">
                  <Mail className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* Scientific Foundations */}
            <div className="space-y-6">
              <div className="border border-white/20 bg-black/60 p-6 hud-bracket relative">
                <div className="flex items-center space-x-2 border-b border-white/10 pb-2 mb-4 text-xs text-gray-500">
                  <Database className="w-4 h-4" />
                  <span>UPSTREAM_DEPENDENCIES</span>
                </div>
                <ul className="space-y-3">
                  {[
                    { node: "NCBI Sequence Read Archive", tag: "RAW_DATA" },
                    { node: "SILVA rRNA 138.1", tag: "TAXONOMY" },
                    { node: "GBIF & IUCN Red List", tag: "CONSERVATION" },
                    { node: "MGnify (EMBL-EBI)", tag: "METAGENOMICS" }
                  ].map(dep => (
                    <li key={dep.node} className="flex justify-between items-center text-sm">
                      <span className="text-white uppercase font-bold">{dep.node}</span>
                      <span className="text-[10px] text-primary border border-primary/30 px-2 py-0.5">{dep.tag}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border border-white/20 bg-black/60 p-6 hud-bracket relative">
                <div className="flex items-center space-x-2 border-b border-white/10 pb-2 mb-4 text-xs text-gray-500">
                  <BookOpen className="w-4 h-4" />
                  <span>THEORETICAL_FOUNDATIONS</span>
                </div>
                <ul className="space-y-4">
                  {[
                    { pub: "VSEARCH: a versatile open-source tool for metagenomics", org: "Rognes et al., PeerJ (2016)" },
                    { pub: "The SILVA ribosomal RNA gene database project", org: "Quast et al., Nucleic Acids Res (2013)" }
                  ].map(ref => (
                    <li key={ref.pub} className="border-l-2 border-gray-600 pl-3">
                      <div className="text-sm text-gray-300 font-bold uppercase">{ref.pub}</div>
                      <div className="text-xs text-gray-500 flex items-center mt-1">
                        <ExternalLink className="w-3 h-3 mr-1" /> {ref.org}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <div className="border border-yellow-500/50 bg-black/80 p-8 hud-panel text-center relative overflow-hidden">
            <ShieldAlert className="w-12 h-12 text-yellow-500 mx-auto mb-4 opacity-50" />
            <div className="text-yellow-500 font-bold tracking-widest uppercase mb-2">Notice: Open Connectivity Protocol</div>
            <p className="text-gray-400 text-sm max-w-2xl mx-auto mb-6">
              RELICT_SYS is fully open-source (MIT Licensed) and available for academic collaboration. External researchers seeking pipeline access or applied benchmarking protocols may initiate contact sequence.
            </p>
            <a href="https://www.shauryapunj.com/contact" target="_blank" rel="noopener noreferrer" className="inline-flex items-center px-6 py-3 border border-yellow-500 text-yellow-500 hover:bg-yellow-500 hover:text-black font-bold text-sm tracking-widest transition-all">
              <Mail className="w-4 h-4 mr-2" />
              INITIATE_HANDSHAKE
            </a>
          </div>

        </div>
      </main>
      <Footer />
    </div>
  );
};

export default About;