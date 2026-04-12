import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ReactLenis } from "@studio-freight/react-lenis";
import CustomCursor from "@/components/CustomCursor";

import Index from "./pages/Index";
import Demo from "./pages/Demo";
import Visualize from "./pages/Visualize";
import Impact from "./pages/Impact";
import About from "./pages/About";
import JobResults from "./pages/JobResults";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <ReactLenis root options={{ lerp: 0.05, syncTouch: true }}>
        <CustomCursor />
        <TooltipProvider>
          <Toaster />
          <Sonner />
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/demo" element={<Demo />} />
              <Route path="/jobs/:jobId" element={<JobResults />} />
              <Route path="/visualize" element={<Visualize />} />
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

export default App;
