import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ReactLenis } from "@studio-freight/react-lenis";
import { useHeavyFxEnabled } from "@/hooks/use-heavy-fx";

// Heavy decorative FX (three.js) — lazy so three.js never lands in the initial
// bundle; only fetched on fine-pointer/motion-OK displays.
const CustomCursor = lazy(() => import("@/components/CustomCursor"));
const BioNetworkBackground = lazy(() =>
  import("@/components/BioNetworkBackground").then((m) => ({ default: m.BioNetworkBackground }))
);

// Route-level code splitting: charts (recharts), map (leaflet), and each page
// load on navigation instead of up front.
const Index = lazy(() => import("./pages/Index"));
const Demo = lazy(() => import("./pages/Demo"));
const Impact = lazy(() => import("./pages/Impact"));
const About = lazy(() => import("./pages/About"));
const JobResults = lazy(() => import("./pages/JobResults"));
const Profile = lazy(() => import("./pages/Profile"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const Verify = lazy(() => import("./pages/Verify"));
const NotFound = lazy(() => import("./pages/NotFound"));

function RouteFallback() {
  return (
    <div className="min-h-screen bg-transparent flex items-center justify-center font-mono">
      <div className="text-primary text-xs uppercase tracking-widest animate-pulse">
        <span className="opacity-50 mr-2">&gt;</span>Loading module<span className="animate-pulse">_</span>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const App = () => {
  // Heavy decorative FX (3D particle background, custom cursor) only mount on
  // fine-pointer, motion-OK displays — never on touch/mobile or when the user
  // prefers reduced motion, so phones don't run a full-screen render loop.
  const heavyFx = useHeavyFxEnabled();

  return (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <ReactLenis root options={{ lerp: 0.05, syncTouch: true }}>
        {heavyFx && (
          <Suspense fallback={null}>
            <BioNetworkBackground />
            <CustomCursor />
          </Suspense>
        )}
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/demo" element={<Demo />} />
                <Route path="/jobs/:jobId" element={<JobResults />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/projects" element={<Projects />} />
                <Route path="/projects/:projectId" element={<ProjectDetail />} />
                <Route path="/verify" element={<Verify />} />
                <Route path="/impact" element={<Impact />} />
                <Route path="/about" element={<About />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </TooltipProvider>
      </ReactLenis>
    </ThemeProvider>
  </QueryClientProvider>
  );
};

export default App;
