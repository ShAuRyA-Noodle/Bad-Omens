import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Shield, Target, Users, Leaf, Globe, TrendingUp } from "lucide-react";

const impactAreas = [
  { id: "IMP_01", title: "NON_INVASIVE_SAMPLING", desc: "Isolates DNA traces from abiotic matrices (water/soil). No direct organism disruption or capture required.", icon: Target },
  { id: "IMP_02", title: "DB_CROSS_REFERENCING", desc: "Automated real-time pinging of GBIF occurrences and IUCN Red List. Immediate conservation flags.", icon: Shield },
  { id: "IMP_03", title: "SIGNED_PROVENANCE", desc: "Every parameter, tool version, reference-DB hash, and sequence hash recorded in an Ed25519-signed manifest anyone can verify offline.", icon: TrendingUp },
];

const sdg = [
  { id: "SDG_14", text: "LIFE_BELOW_WATER (14) - Marine resource tracking." },
  { id: "SDG_15", text: "LIFE_ON_LAND (15) - Terrestrial ecosystem preservation." },
  { id: "SDG_13", text: "CLIMATE_ACTION (13) - Baseline monitoring of shifts." },
];

const Impact = () => {
  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">
          
          <div className="mb-16">
            <div className="flex items-center space-x-2 text-primary text-xs uppercase tracking-widest mb-4">
              <span className="w-2 h-2 bg-primary"></span>
              <span>System Output Goals</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-heading font-black text-white uppercase tracking-tighter mb-4 flex items-center">
              Environmental <span className="text-neon-cyan ml-3">Impact.</span>
              <Globe className="w-8 h-8 ml-4 text-gray-500" />
            </h1>
            <p className="text-sm text-gray-400 max-w-2xl border-l border-white/20 pl-4 py-1">
              Alignment with global sustainability frameworks. Precision monitoring translates directly into verifiable ecological protection.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-16">
            {impactAreas.map(item => (
              <div key={item.id} className="border border-white/20 bg-black/60 backdrop-blur-md p-6 hud-panel space-y-4">
                <div className="flex justify-between items-center text-xs text-secondary border-b border-white/10 pb-2">
                  <span>[{item.id}]</span>
                  <item.icon className="w-4 h-4" />
                </div>
                <div className="font-bold text-white uppercase tracking-wider">{item.title}</div>
                <div className="text-sm text-gray-400 leading-relaxed font-light">{item.desc}</div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-[1.5fr_1fr] gap-8 mb-16">
            <div className="border border-white/20 bg-black/60 backdrop-blur-sm p-8 hud-bracket">
              <div className="flex items-center space-x-2 mb-6 border-b border-white/10 pb-2 text-xs text-primary uppercase">
                <Users className="w-4 h-4" />
                <span>USER_BIFURCATION_TREE</span>
              </div>
              <div className="space-y-6">
                <div>
                  <h3 className="text-white font-bold mb-2 uppercase tracking-widest">GROUP A: RESEARCH_LABS</h3>
                  <ul className="text-xs text-gray-400 space-y-2">
                    <li>&gt; ONE-CMD REPRODUCIBLE PIPELINES</li>
                    <li>&gt; SIGNED PROVENANCE MANIFESTOS</li>
                    <li>&gt; QIIME2 / PHYLOSEQ EXPORTS</li>
                  </ul>
                </div>
                <div>
                  <h3 className="text-white font-bold mb-2 uppercase tracking-widest">GROUP B: FIELD_SCIENTISTS</h3>
                  <ul className="text-xs text-gray-400 space-y-2">
                    <li>&gt; NO BIOINFORMATICS CLI REQ</li>
                    <li>&gt; PLAIN_LANGUAGE RECONSTRUCTION</li>
                    <li>&gt; GBIF OCCURRENCE FORWARDING</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="border border-white/20 bg-black/60 backdrop-blur-sm p-8 text-xs text-gray-500 font-mono flex flex-col justify-between">
              <div>
                <div className="text-primary mb-4">[ SUSTAINABILITY_INDEX ]</div>
                <div className="space-y-2">
                  {sdg.map(s => (
                    <div key={s.id} className="border-l border-white/20 pl-2">
                      <span className="text-secondary">{s.id}</span>
                      <div className="mt-1">{s.text}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="mt-8 pt-4 border-t border-white/10 flex items-center space-x-2 text-green-500">
                <Leaf className="w-4 h-4" />
                <span>SYSTEM_GREEN_COMPLIANT</span>
              </div>
            </div>
          </div>
          
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Impact;