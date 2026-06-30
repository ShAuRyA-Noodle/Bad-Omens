import { Header } from "@/components/Header";
import { DemoUpload } from "@/components/DemoUpload";
import { Footer } from "@/components/Footer";
import { TerminalSquare } from "lucide-react";

const Demo = () => {
  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-5xl">
          <div className="mb-12">
            <div className="flex items-center space-x-2 text-secondary text-xs uppercase tracking-widest mb-4">
              <span className="w-2 h-2 bg-secondary animate-pulse"></span>
              <span>Sequence Ingestion</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-heading font-black text-white uppercase tracking-tighter mb-4 flex items-center">
              Execute <span className="text-neon-cyan ml-3">Pipeline.</span>
              <TerminalSquare className="w-8 h-8 ml-4 text-gray-600" />
            </h1>
            <p className="text-sm text-gray-400 max-w-2xl border-l border-white/20 pl-4 py-1">
              Upload raw environmental FASTQ reads. The worker runs fastp QC, vsearch UNOISE3 ASV inference and dechimerization, taxonomy against SILVA/MIDORI2, GBIF + IUCN conservation cross-referencing, and emits a signed provenance manifest.
            </p>
          </div>
          
          <div className="w-full">
            <DemoUpload />
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Demo;