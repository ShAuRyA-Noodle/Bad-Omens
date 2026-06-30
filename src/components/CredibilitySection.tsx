import { motion } from "framer-motion";
import { ShieldAlert, Terminal } from "lucide-react";

// Reference data sources actually used at analysis time. No invented
// latencies, no fake status strings, no animated counters implying live
// telemetry that does not exist. Every row is a verifiable, version-pinned
// fact about the real pipeline.
const referenceSources = [
  { id: "ref_01", name: "SILVA 138.1 SSU NR99", role: "16S / 18S rRNA taxonomy", kind: "REFERENCE_DB" },
  { id: "ref_02", name: "MIDORI2 GB269", role: "COI / 12S taxonomy", kind: "REFERENCE_DB" },
  { id: "ref_03", name: "GBIF Backbone + Occurrence", role: "name resolution + occurrence counts", kind: "LIVE_API" },
  { id: "ref_04", name: "IUCN Red List (via GBIF)", role: "conservation status", kind: "LIVE_API" },
];

// Verifiable properties of the platform — each is true by construction, not
// a measured metric animated to look impressive.
const guarantees = [
  { label: "PIPELINE", value: "fastp · vsearch UNOISE3 · scikit-bio", note: "version-pinned, published tools" },
  { label: "PROVENANCE", value: "Ed25519-signed manifest", note: "publicly verifiable at /public-key" },
  { label: "DATA_POLICY", value: "no mock data", note: "every number computed from your reads" },
  { label: "LICENSE", value: "MIT · open source", note: "self-hostable, no lock-in" },
];

export const CredibilitySection = () => {
  return (
    <section className="py-24 bg-transparent border-t border-white/5 relative overflow-hidden font-mono">
      <div className="container mx-auto px-4 md:px-8 max-w-6xl">

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-12">

          {/* Left Column - Verifiable Guarantees */}
          <div className="space-y-8">
            <div>
              <div className="flex items-center space-x-2 text-primary text-xs uppercase tracking-widest mb-4">
                <span className="w-2 h-2 bg-primary animate-pulse"></span>
                <span>System Architecture</span>
              </div>
              <h2 className="text-3xl md:text-4xl font-heading font-black text-white uppercase tracking-tighter mb-4">
                Verifiable <span className="text-neon-cyan">by design.</span>
              </h2>
              <p className="text-sm text-gray-400">
                Relict pins every tool and reference database, and signs every result. Nothing on this page is a measured marketing number — these are properties you can check against the code and the provenance manifest.
              </p>
            </div>

            <div className="border border-white/20 bg-black p-6 hud-bracket shadow-[0_0_15px_rgba(0,0,0,1)]">
              <div className="flex justify-between text-xs text-gray-500 mb-6 border-b border-white/10 pb-2">
                <span>SYSTEM_GUARANTEES</span>
                <span>VERIFIABLE</span>
              </div>

              <div className="space-y-5">
                {guarantees.map((g) => (
                  <div key={g.label}>
                    <div className="text-xs text-gray-400 mb-1">{g.label}</div>
                    <div className="text-lg font-bold text-white flex items-baseline">
                      <span className="text-neon-cyan mr-2">&gt;</span>
                      <span>{g.value}</span>
                    </div>
                    <div className="text-xs text-gray-600 mt-1 pl-4">{g.note}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column - Reference Sources */}
          <div>
            <div className="border border-white/20 bg-[#0a0a0a] w-full h-full min-h-[400px] flex flex-col">
              <div className="bg-white/5 border-b border-white/20 py-2 px-4 flex items-center justify-between text-xs text-gray-400">
                <div className="flex items-center space-x-2">
                  <Terminal className="w-3 h-3" />
                  <span>reference_sources.txt</span>
                </div>
              </div>

              <div className="p-4 sm:p-6 text-xs sm:text-sm text-gray-300 font-mono flex-grow space-y-2 overflow-hidden relative">
                <div className="text-gray-500 mb-4 font-bold"># Public reference databases &amp; APIs used per analysis</div>

                {referenceSources.map((src, i) => (
                  <motion.div
                    key={src.id}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.3 + i * 0.15 }}
                    className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-white/5 pb-2"
                  >
                    <div className="flex space-x-4">
                      <span className="text-gray-600">[{src.id}]</span>
                      <span className="text-neon-cyan font-bold w-48 truncate">{src.name}</span>
                    </div>
                    <div className="flex justify-between sm:justify-end sm:space-x-8 mt-1 sm:mt-0">
                      <span className="text-gray-500 hidden sm:inline-block w-56 truncate">{src.role}</span>
                      <span className="text-gray-600 text-right w-28">{src.kind}</span>
                    </div>
                  </motion.div>
                ))}

                <motion.div
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true }}
                  transition={{ delay: 1.2 }}
                  className="mt-6 pt-4 text-gray-500"
                >
                  # Exact versions &amp; SHA256 checksums are recorded in each job&apos;s signed provenance manifest.
                </motion.div>
              </div>
            </div>
          </div>

        </div>

        {/* Scope Limitation Banner — honest, kept */}
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
              Output manifests are intended for <span className="text-white">environmental studies, baseline monitoring, and bioinformatics research</span>. Relict outputs are NOT clinically, legally, or forensically certified.
            </p>
          </div>
        </motion.div>

      </div>
    </section>
  );
};
