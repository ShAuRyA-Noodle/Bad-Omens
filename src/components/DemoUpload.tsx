import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, AlertCircle, LogIn, UserPlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/hooks/use-auth";
import {
  uploadSample,
  getJob,
  createJobWebSocket,
  AMPLICON_MARKERS,
} from "@/lib/api";

export const DemoUpload = () => {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>("");
  const [stageMessage, setStageMessage] = useState<string>("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [amplicon, setAmplicon] = useState<string>("16S_V4");
  const [meta, setMeta] = useState<Record<string, string>>({});
  const setMetaField = (k: string, v: string) => setMeta((m) => ({ ...m, [k]: v }));

  const [authMode, setAuthMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  const { toast } = useToast();
  const navigate = useNavigate();
  const { user, isAuthenticated, login, signup: signupFn, logout } = useAuth();

  const handleAuth = async () => {
    if (!email || !password) return;
    setAuthLoading(true);
    try {
      if (authMode === "signup") {
        await signupFn(email, password);
      } else {
        await login(email, password);
      }
      toast({ title: authMode === "signup" ? "Account created" : "Logged in" });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Auth failed";
      toast({ title: "Error", description: msg, variant: "destructive" });
    } finally {
      setAuthLoading(false);
    }
  };

  useEffect(() => {
    if (!jobId) return;
    const ws = createJobWebSocket(jobId);
    if (!ws) return;

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.progress !== undefined) {
          setUploadProgress(Math.round(data.progress * 100));
        }
        if (data.message) {
          setStageMessage(data.message);
        }
        if (data.kind === "job.succeeded") {
          setJobStatus("succeeded");
          setIsProcessing(false);
          toast({ title: "Analysis complete", description: "View your results" });
        }
        if (data.kind === "job.failed") {
          setJobStatus("failed");
          setIsProcessing(false);
          setError(data.message || "Pipeline failed");
        }
      } catch { /* best-effort: failures surface via job status / polling */ }
    };

    ws.onerror = () => {
      const pollInterval = setInterval(async () => {
        try {
          const job = await getJob(jobId);
          if (job.status === "succeeded" || job.status === "failed") {
            setJobStatus(job.status);
            setIsProcessing(false);
            if (job.status === "succeeded") {
              toast({ title: "Analysis complete" });
            } else {
              setError(job.error_message || "Pipeline failed");
            }
            clearInterval(pollInterval);
          }
        } catch { /* best-effort: failures surface via job status / polling */ }
      }, 3000);
      return () => clearInterval(pollInterval);
    };

    return () => { ws.close(); };
  }, [jobId, toast]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setUploadedFile(file);
      setIsProcessing(true);
      setUploadProgress(5);
      setError(null);
      setJobId(null);
      setJobStatus("");
      setStageMessage("Uploading sequence array...");

      try {
        const cleanMeta = Object.fromEntries(
          Object.entries(meta).filter(([, v]) => v.trim() !== "")
        );
        const result = await uploadSample(file, amplicon, cleanMeta);
        const jid = result.sample.job_id;
        setJobId(jid);
        setUploadProgress(10);
        setStageMessage("Byte-stream complete. Initializing analysis daemon...");

        toast({
          title: "Ingestion OK",
          description: `${file.name} (${(file.size / 1024).toFixed(1)} KB) mapped to memory.`,
        });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setError(msg);
        setIsProcessing(false);
        toast({ title: "Upload failed", description: msg, variant: "destructive" });
      }
    },
    [toast, amplicon, meta]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/octet-stream": [".fastq", ".fq", ".fasta", ".fa", ".fna", ".fastq.gz", ".fq.gz", ".fasta.gz", ".fa.gz", ".fna.gz"],
    },
    maxFiles: 1,
    disabled: isProcessing || !isAuthenticated,
  });

  if (!isAuthenticated) {
    return (
      <div className="p-8 border border-white/20 bg-black/80 max-w-lg shadow-[0_0_20px_rgba(0,240,255,0.1)] hud-bracket backdrop-blur-md">
        <div className="text-secondary text-xs mb-6 pb-2 border-b border-white/10 uppercase tracking-widest flex items-center">
          <LogIn className="w-3 h-3 mr-2" />
          AUTHORIZATION REQUIRED
        </div>
        <p className="text-gray-400 text-xs mb-6">
          Access to computing clusters requires clearance. Establish proxy connection by supplying credentials below.
        </p>
        <div className="space-y-4 font-mono text-sm">
          <input
            type="email"
            placeholder="[ ENTER EMAIL ID ]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-3 bg-black border border-white/20 focus:border-primary text-primary focus:outline-none placeholder-gray-600 transition-colors"
          />
          <input
            type="password"
            placeholder="[ ENTER SECURITY HASH ]"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-3 bg-black border border-white/20 focus:border-primary text-primary focus:outline-none placeholder-gray-600 transition-colors"
          />
          <button 
            onClick={handleAuth} 
            disabled={authLoading} 
            className="w-full btn-cyber py-3 flex items-center justify-center font-bold tracking-widest mt-2"
          >
            {authLoading ? "INITIALIZING..." : authMode === "signup" ? (
              <><UserPlus className="w-4 h-4 mr-2" /> GENERATE ID</>
            ) : (
              <><LogIn className="w-4 h-4 mr-2" /> AUTHENTICATE</>
            )}
          </button>
          <div className="mt-4 pt-4 border-t border-white/10 text-center text-xs text-gray-500 flex justify-center items-center space-x-2">
            <span>{authMode === "signup" ? "HAVE KEYS?" : "NO AUTH ID?"}</span>
            <button
              onClick={() => setAuthMode(authMode === "signup" ? "login" : "signup")}
              className="text-secondary hover:text-white transition-colors uppercase border-b border-secondary pb-0.5"
            >
              {authMode === "signup" ? "LOGIN" : "REQUEST ONE"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between border border-white/10 p-3 bg-white/5 backdrop-blur-md">
        <div className="flex items-center space-x-3 text-xs">
          <div className="w-2 h-2 bg-primary rounded-full animate-pulse shadow-[0_0_5px_hsl(var(--primary))]" />
          <p className="text-gray-400">
            CONNECTION OK // <strong>{user?.email}</strong>
          </p>
        </div>
        <button className="text-xs text-red-500 hover:text-red-400 border border-red-500/30 px-3 py-1 hover:bg-red-500/10 transition-colors uppercase" onClick={logout}>
          DISCONNECT
        </button>
      </div>

      {/* Amplicon marker — drives reference DB, GBIF kingdom hint, and DwC-A
          target gene. Choosing the right one is what makes non-16S results
          correct. */}
      <div className="border border-white/10 bg-black/60 backdrop-blur-md p-4 hud-bracket">
        <div className="flex items-center justify-between text-[11px] text-gray-500 mb-3 uppercase tracking-widest">
          <span>Amplicon Marker</span>
          <span className="text-gray-600">reference DB</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {AMPLICON_MARKERS.map((m) => {
            const active = amplicon === m.value;
            return (
              <button
                key={m.value}
                type="button"
                disabled={isProcessing}
                onClick={() => setAmplicon(m.value)}
                className={cn(
                  "text-left p-3 border transition-colors min-h-[56px] disabled:opacity-50 disabled:cursor-not-allowed",
                  active ? "border-primary bg-primary/10 text-primary" : "border-white/15 text-gray-400 hover:border-secondary hover:text-white"
                )}
              >
                <div className="font-bold text-sm uppercase tracking-wide">{m.label}</div>
                <div className="text-[10px] text-gray-500 mt-0.5">{m.note}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Optional Darwin Core sample metadata — powers the map and a complete
          DwC-A archive. Where + when the sample was collected. */}
      <details className="border border-white/10 bg-black/60 backdrop-blur-md p-4 hud-bracket group">
        <summary className="text-[11px] text-gray-500 uppercase tracking-widest cursor-pointer flex items-center justify-between list-none select-none min-h-[24px]">
          <span>Sample Metadata <span className="text-gray-600">· optional</span></span>
          <span className="text-neon-cyan group-open:rotate-90 transition-transform">›</span>
        </summary>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          <MetaInput label="Latitude" placeholder="e.g. 30.7333" value={meta.decimalLatitude ?? ""} onChange={(v) => setMetaField("decimalLatitude", v)} type="number" />
          <MetaInput label="Longitude" placeholder="e.g. 76.7794" value={meta.decimalLongitude ?? ""} onChange={(v) => setMetaField("decimalLongitude", v)} type="number" />
          <MetaInput label="Event date" value={meta.eventDate ?? ""} onChange={(v) => setMetaField("eventDate", v)} type="date" />
          <MetaInput label="Locality" placeholder="e.g. Sukhna Lake" value={meta.locality ?? ""} onChange={(v) => setMetaField("locality", v)} />
          <MetaInput label="Collected by" placeholder="name" value={meta.recordedBy ?? ""} onChange={(v) => setMetaField("recordedBy", v)} />
          <MetaInput label="Habitat" placeholder="e.g. freshwater lake" value={meta.habitat ?? ""} onChange={(v) => setMetaField("habitat", v)} />
        </div>
      </details>

      <div
        {...getRootProps()}
        className={cn(
          "p-12 sm:p-20 border border-dashed cursor-pointer transition-all duration-300 text-center bg-black/60 backdrop-blur-sm hud-bracket relative overflow-hidden",
          isDragActive ? "border-primary bg-primary/10 shadow-[inset_0_0_50px_rgba(57,255,20,0.2)]" : "border-white/20 hover:border-secondary hover:shadow-[inset_0_0_30px_rgba(0,240,255,0.1)]",
          isProcessing && "pointer-events-none opacity-50"
        )}
      >
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10 mix-blend-overlay pointer-events-none" />
        <input {...getInputProps()} />
        
        <div className="relative z-10 flex flex-col items-center">
          <div className={cn(
              "p-4 rounded-xl border mb-6 transition-all duration-300", 
              isDragActive ? "border-primary text-primary bg-primary/20" : "border-white/10 text-gray-400 bg-white/5"
            )}>
            <Upload className="w-8 h-8" />
          </div>
          
          {isDragActive ? (
            <p className="text-xl font-bold text-primary tracking-widest uppercase">&gt;&gt;&gt; INJECT PAYLOAD &lt;&lt;&lt;</p>
          ) : (
            <>
              <p className="text-lg font-bold text-white mb-2 uppercase tracking-wide">
                MOUNT FASTA / FASTQ DIRECTORY
              </p>
              <p className="text-xs text-gray-500 tracking-widest uppercase">
                Drag-and-drop or click to parse local file
              </p>
            </>
          )}
        </div>
      </div>

      {(isProcessing || jobStatus) && (
        <div className="border border-white/20 bg-black/80 p-6 space-y-6 hud-panel shadow-[0_0_20px_rgba(0,0,0,1)]">
          {uploadedFile && (
            <div className="flex flex-wrap items-center gap-3 border-b border-white/10 pb-4">
              <FileText className="w-4 h-4 text-neon-cyan" />
              <span className="font-mono text-sm text-white">{uploadedFile.name}</span>
              <span className="text-xs text-gray-500 border border-white/10 px-2 py-0.5">
                {(uploadedFile.size / 1024).toFixed(1)} KB
              </span>
              
              <div className="ml-auto">
                {jobStatus === "succeeded" && <span className="text-xs text-black font-bold bg-primary px-3 py-1 uppercase tracking-widest">COMPLETE</span>}
                {jobStatus === "failed" && <span className="text-xs text-white bg-red-600 px-3 py-1 uppercase tracking-widest border border-red-500">FAILED</span>}
                {isProcessing && <span className="text-xs text-secondary border border-secondary px-3 py-1 uppercase tracking-widest animate-pulse">PROCESSING</span>}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <div className="flex justify-between text-[10px] text-gray-400 font-mono">
              <span>{isProcessing ? "PIPELINE_EXECUTION" : "TASK_STATUS"}</span>
              <span className="text-secondary">{uploadProgress}%</span>
            </div>
            {/* Terminal style progress bar */}
            <div className="w-full h-2 bg-white/10 border border-white/20 p-0.5 box-content overflow-hidden">
              <div 
                className="h-full bg-secondary transition-all duration-300" 
                style={{ width: `${uploadProgress}%` }} 
              />
            </div>
          </div>

          {stageMessage && (
            <div className="p-3 bg-white/5 border-l-2 border-secondary font-mono text-xs text-gray-300">
              <span className="text-secondary opacity-50 mr-2">&gt;</span> {stageMessage}
              {isProcessing && <span className="ml-1 animate-pulse">_</span>}
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-900/20 border border-red-500/50 flex items-start space-x-3 text-red-400 font-mono text-xs">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-bold mb-1">SYSTEM_ERR</div>
                <div>{error}</div>
              </div>
            </div>
          )}

          {jobStatus === "succeeded" && jobId && (
            <div className="pt-4 border-t border-white/10">
              <button 
                onClick={() => navigate(`/jobs/${jobId}`)} 
                className="w-full btn-cyber py-4 font-bold tracking-widest flex items-center justify-center text-sm"
              >
                OPEN_TOPOLOGY_MATRIX
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

function MetaInput({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        step={type === "number" ? "any" : undefined}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 px-3 py-2 bg-black border border-white/15 text-sm text-gray-200 focus:border-primary focus:outline-none placeholder-gray-700 min-h-[44px]"
      />
    </label>
  );
}
