import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { ShieldCheck, ShieldAlert, Upload, KeyRound } from "lucide-react";
import { cn } from "@/lib/utils";
import { getPublicKey, verifyManifest, type VerifyResult } from "@/lib/api";

export default function Verify() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: publicKey } = useQuery({ queryKey: ["public-key"], queryFn: getPublicKey, retry: false });

  const runVerify = useCallback(async (raw: string) => {
    setError(null);
    setResult(null);
    let manifest: unknown;
    try {
      manifest = JSON.parse(raw);
    } catch {
      setError("That is not valid JSON. Paste a full provenance manifest.");
      return;
    }
    setBusy(true);
    try {
      setResult(await verifyManifest(manifest));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }, []);

  const onFile = useCallback((file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const content = String(reader.result ?? "");
      setText(content);
      void runVerify(content);
    };
    reader.readAsText(file);
  }, [runVerify]);

  return (
    <div className="min-h-screen bg-transparent font-mono relative">
      <Header />
      <main className="pt-28 sm:pt-32 pb-24 relative z-10">
        <div className="container mx-auto px-4 md:px-8 max-w-4xl">
          <div className="mb-8">
            <div className="flex items-center gap-2 text-primary text-xs uppercase tracking-widest mb-3">
              <span className="w-2 h-2 bg-primary animate-pulse" />
              <span>Public Verification · no login</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-heading font-black text-white uppercase tracking-tighter">
              Verify a <span className="text-neon-cyan">Manifest.</span>
            </h1>
            <p className="text-sm text-gray-400 mt-3 max-w-2xl">
              Paste a Relict provenance manifest to check its integrity: the content hash is
              recomputed and the Ed25519 signature is verified against this server&apos;s public key.
              Anyone can do this — no account required.
            </p>
          </div>

          <div className="border border-white/15 bg-black/60 backdrop-blur-md p-4 sm:p-6 hud-bracket">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-gray-500 mb-3 uppercase tracking-widest border-b border-white/10 pb-2">
              <span>Provenance Manifest (JSON)</span>
              <label className="flex items-center gap-2 text-neon-cyan cursor-pointer hover:text-white transition-colors">
                <Upload className="w-3.5 h-3.5" />
                <span>Upload file</span>
                <input
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }}
                />
              </label>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder='{ "schema_version": "1.0", "manifest_sha256": "...", "signature": "ed25519:...", ... }'
              spellCheck={false}
              className="w-full h-56 bg-black border border-white/15 p-3 text-xs text-gray-300 font-mono focus:border-primary focus:outline-none placeholder-gray-700 resize-y break-all"
            />
            <button
              onClick={() => runVerify(text)}
              disabled={busy || !text.trim()}
              className="w-full btn-cyber py-3 mt-4 font-bold tracking-widest flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed min-h-[48px]"
            >
              {busy ? "VERIFYING…" : "VERIFY SIGNATURE"}
            </button>

            {error && (
              <div className="mt-4 p-3 border border-red-500/40 bg-red-900/20 text-red-400 text-xs">{error}</div>
            )}

            {result && (
              <div className={cn("mt-4 border p-4", result.verified ? "border-neon-green/50 bg-primary/5" : "border-red-500/50 bg-red-900/10")}>
                <div className="flex items-center gap-3 mb-3">
                  {result.verified
                    ? <ShieldCheck className="w-7 h-7 text-neon-green shrink-0" />
                    : <ShieldAlert className="w-7 h-7 text-red-500 shrink-0" />}
                  <span className={cn("text-xl font-heading font-black uppercase tracking-tight", result.verified ? "text-neon-green" : "text-red-500")}>
                    {result.verified ? "Verified" : "Not Verified"}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  <VerifyRow label="Content hash" ok={result.content_hash_ok} />
                  <VerifyRow label={`Signature (${result.algorithm})`} ok={result.signature_ok} />
                </div>
                <p className="text-[11px] text-gray-400 mt-3">{result.detail}</p>
                <p className="text-[10px] text-gray-600 mt-2 break-all">computed: {result.computed_sha256}</p>
              </div>
            )}
          </div>

          <div className="border border-white/10 bg-black/40 p-4 mt-6 text-xs">
            <div className="flex items-center gap-2 text-gray-500 uppercase tracking-widest mb-2">
              <KeyRound className="w-3.5 h-3.5" /> Server Public Key
            </div>
            {publicKey ? (
              <>
                <p className="text-gray-400 mb-1">{publicKey.algorithm} · base64</p>
                <p className="font-mono text-[11px] text-neon-cyan break-all">{publicKey.public_key_b64}</p>
              </>
            ) : (
              <p className="text-gray-600">No signing key exists yet — run a job to mint one.</p>
            )}
            <p className="text-[10px] text-gray-600 mt-3">
              For a fully independent check, verify offline with
              <span className="text-gray-400"> backend/scripts/verify_manifest.py</span>.
            </p>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

function VerifyRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between border border-white/10 px-3 py-2">
      <span className="text-gray-400">{label}</span>
      <span className={cn("font-bold uppercase", ok ? "text-neon-green" : "text-red-500")}>{ok ? "OK" : "FAIL"}</span>
    </div>
  );
}
