import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Dna, Terminal, Menu, X, User } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { checkHealth, getAccessToken } from "@/lib/api";

export const Header = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [time, setTime] = useState("");
  const location = useLocation();

  // Real API status — polled from /health. Reads OFFLINE honestly if down.
  const { data: health, isError, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,
    retry: false,
  });
  const apiStatus = isLoading ? "…" : isError || !health ? "OFFLINE" : health.status === "ok" ? "ONLINE" : health.status.toUpperCase();
  const statusColor = apiStatus === "ONLINE" ? "text-neon-green" : apiStatus === "OFFLINE" ? "text-red-500" : "text-yellow-500";
  const authed = !!getAccessToken();

  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date();
      setTime(`${now.getUTCHours().toString().padStart(2, '0')}:${now.getUTCMinutes().toString().padStart(2, '0')}:${now.getUTCSeconds().toString().padStart(2, '0')} UTC`);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const navigation = [
    { name: "INIT", href: "/" },
    { name: "EXECUTE_PIPELINE", href: "/demo" },
    { name: "VERIFY", href: "/verify" },
    { name: "SYSTEM_IMPACT", href: "/impact" },
    { name: "ABOUT_NODE", href: "/about" },
  ];

  return (
    <header className="fixed top-0 w-full z-50 pointer-events-auto border-b border-white/10 bg-black/80 backdrop-blur-md scanline">
      {/* Top technical strip */}
      <div className="w-full bg-primary/10 border-b border-primary/20 py-1 px-4 justify-between items-center text-[10px] font-mono text-primary uppercase tracking-widest hidden md:flex">
        <span>API: <span className={cn(statusColor, apiStatus === "ONLINE" && "animate-pulse")}>{apiStatus}</span></span>
        <span>ENV: {import.meta.env.MODE} {health?.version ? `// v${health.version}` : ""}</span>
        <span>T: {time}</span>
      </div>

      <div className="px-4 md:px-8 py-3 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-3 group">
          <div className="w-8 h-8 border border-secondary flex items-center justify-center bg-secondary/10 group-hover:bg-secondary/30 transition-colors">
            <Terminal className="w-4 h-4 text-secondary" />
          </div>
          <span className="font-heading font-black text-xl tracking-tight text-white uppercase">
            RELICT<span className="text-secondary opacity-50">_SYS</span>
          </span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center space-x-6 font-mono text-xs">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={cn(
                  "relative py-2 transition-colors uppercase tracking-wider group flex items-center",
                  isActive ? "text-primary" : "text-gray-500 hover:text-white"
                )}
              >
                <span className={cn("text-primary opacity-0 group-hover:opacity-100 transition-opacity mr-2", isActive && "opacity-100")}>[</span>
                {item.name}
                <span className={cn("text-primary opacity-0 group-hover:opacity-100 transition-opacity ml-2", isActive && "opacity-100")}>]</span>
              </Link>
            )
          })}
        </div>

        <div className="hidden md:flex items-center space-x-3">
          {authed && (
            <Link
              to="/projects"
              className="text-xs text-gray-400 hover:text-neon-cyan flex items-center border border-white/15 px-3 py-2 uppercase tracking-wider transition-colors"
            >
              PROJECTS
            </Link>
          )}
          {authed && (
            <Link
              to="/profile"
              title="Account"
              className="text-xs text-gray-400 hover:text-neon-cyan flex items-center border border-white/15 px-3 py-2 uppercase tracking-wider transition-colors"
            >
              <User className="w-3.5 h-3.5 mr-2" />
              ACCOUNT
            </Link>
          )}
          <Link
            to="/demo"
            className="btn-cyber px-4 py-2 text-xs flex items-center"
          >
            <Dna className="w-3 h-3 mr-2" />
            RUN_PIPELINE
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <div className="md:hidden flex items-center">
          <button
            className="border border-white/20 p-2 text-white hover:bg-white/10"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
          >
            <motion.div animate={{ rotate: isMobileMenuOpen ? 90 : 0 }}>
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </motion.div>
          </button>
        </div>
      </div>

      {/* Mobile Navigation Dropdown */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="md:hidden border-b border-white/10 bg-black font-mono text-xs"
          >
            <div className="flex flex-col px-4 py-4 space-y-4">
              {navigation.map((item) => (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "uppercase tracking-wider hover:text-primary transition-colors",
                    location.pathname === item.href ? "text-primary flex items-center before:content-['>'] before:mr-2" : "text-gray-500"
                  )}
                  onClick={() => setIsMobileMenuOpen(false)}
                >
                  {item.name}
                </Link>
              ))}
              <div className="pt-4 border-t border-white/10 space-y-3">
                {authed && (
                  <Link
                    to="/projects"
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-gray-400 w-full flex items-center justify-center gap-2 border border-white/15 py-3 hover:text-neon-cyan"
                  >
                    PROJECTS
                  </Link>
                )}
                {authed && (
                  <Link
                    to="/profile"
                    onClick={() => setIsMobileMenuOpen(false)}
                    className="text-gray-400 w-full flex items-center justify-center gap-2 border border-white/15 py-3 hover:text-neon-cyan"
                  >
                    <User className="w-4 h-4" /> ACCOUNT
                  </Link>
                )}
                <Link
                  to="/demo"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="text-primary w-full block text-center border border-primary py-3 hover:bg-primary/20"
                >
                  RUN_PIPELINE
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
};