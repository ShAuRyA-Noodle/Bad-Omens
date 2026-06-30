import { Header } from "@/components/Header";
import { BiodiversityCharts } from "@/components/BiodiversityCharts";
import { Footer } from "@/components/Footer";
import { BiodiversityMetrics } from "@/components/BiodiversityMetrics";
import { Activity } from "lucide-react";

const Visualize = () => {
  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 py-8 md:px-8 max-w-6xl">
          
          <div className="mb-16">
            <div className="flex items-center space-x-2 text-primary text-xs uppercase tracking-widest mb-4">
              <span className="w-2 h-2 bg-primary animate-pulse"></span>
              <span>Data Telemetry / Log Output</span>
            </div>
            <h1 className="text-4xl md:text-5xl font-heading font-black text-white uppercase tracking-tighter mb-4 flex items-center">
              Topology <span className="text-neon-cyan ml-3">Matrix.</span>
              <Activity className="w-8 h-8 ml-4 text-primary" />
            </h1>
            <p className="text-sm text-gray-400 max-w-2xl border-l border-white/20 pl-4 py-1">
              Per-job taxonomy and diversity visualizations render here after you run an analysis. Every chart is computed from your uploaded reads — nothing is shown until a job produces real results.
            </p>
          </div>

          <div className="border border-white/20 bg-black/60 backdrop-blur-md p-6 sm:p-12 mb-16 shadow-[0_0_20px_rgba(0,0,0,1)] hud-bracket relative">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-50" />
            <div className="text-xs text-gray-500 mb-8 border-b border-white/10 pb-2 uppercase tracking-widest flex items-center justify-between">
              <span>VISUALIZATION_ENGINE</span>
              <span>[ AWAITING DATA ]</span>
            </div>
            
            {/* Wrapper div to force dark mode styles inside charts if needed */}
            <div className="chart-container-hud">
              <BiodiversityCharts />
            </div>
          </div>

          <div className="border border-white/20 bg-black/60 backdrop-blur-md p-6 sm:p-12 shadow-[0_0_20px_rgba(0,0,0,1)] hud-bracket relative">
             <div className="text-xs text-gray-500 mb-8 border-b border-white/10 pb-2 uppercase tracking-widest flex items-center justify-between">
              <span>ECOLOGICAL_METRICS_READOUT</span>
              <span>[ PER-JOB ]</span>
            </div>
            <BiodiversityMetrics />
          </div>

        </div>
      </main>
      <Footer />
    </div>
  );
};

export default Visualize;