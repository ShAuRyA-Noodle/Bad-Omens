import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ReactLenis } from "@studio-freight/react-lenis";
import CustomCursor from "@/components/CustomCursor";
import { BioNetworkBackground } from "@/components/BioNetworkBackground";
import { useHeavyFxEnabled } from "@/hooks/use-heavy-fx";

import Index from "./pages/Index";
import Demo from "./pages/Demo";
import Impact from "./pages/Impact";
import About from "./pages/About";
import JobResults from "./pages/JobResults";
import Profile from "./pages/Profile";
import NotFound from "./pages/NotFound";

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
        {heavyFx && <BioNetworkBackground />}
        {heavyFx && <CustomCursor />}
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/demo" element={<Demo />} />
              <Route path="/jobs/:jobId" element={<JobResults />} />
              <Route path="/profile" element={<Profile />} />
              <Route path="/impact" element={<Impact />} />
              <Route path="/about" element={<About />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ReactLenis>
    </ThemeProvider>
  </QueryClientProvider>
  );
};

export default App;
