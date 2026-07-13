/**
 * Relict API client - typed fetch wrappers for every backend endpoint.
 *
 * Every function here talks to the real FastAPI backend at API_BASE.
 * No mock data, no fake numbers, no placeholder responses.
 */

// In dev, VITE_API_BASE_URL is empty so the Vite proxy forwards /api and
// /ws to localhost:8000. In production (Vercel) set VITE_API_BASE_URL to
// the Render backend origin, e.g. https://relict-api.onrender.com.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");
const API_V1 = `${API_BASE}/api/v1`;

// ─── Token management ─────────────────────────────────────────────

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    localStorage.setItem("relict_access_token", token);
  } else {
    localStorage.removeItem("relict_access_token");
  }
}

export function getAccessToken(): string | null {
  if (!accessToken) {
    accessToken = localStorage.getItem("relict_access_token");
  }
  return accessToken;
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_V1}${path}`, {
    ...init,
    headers: {
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: { message: res.statusText } }));
    throw new Error(body?.error?.message || body?.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ─── Types ────────────────────────────────────────────────────────

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  access_expires_at: string;
  refresh_expires_at: string;
}

export interface UserPublic {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface JobPublic {
  id: string;
  user_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  amplicon: string;
  parameter_hash: string | null;
  pipeline_version: string | null;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SamplePublic {
  id: string;
  job_id: string;
  filename: string;
  sha256: string;
  size_bytes: number;
  content_type: string;
  num_reads: number | null;
  read_length_mean: number | null;
  primer_set: string | null;
  dwc_metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface TaxonPublic {
  id: string;
  asv_id: string;
  kingdom: string | null;
  phylum: string | null;
  tax_class: string | null;
  tax_order: string | null;
  family: string | null;
  genus: string | null;
  species: string | null;
  confidence: number | null;
  reference_db: string | null;
}

export interface ASVWithTaxon {
  id: string;
  sequence_sha256: string;
  sequence: string;
  length: number;
  abundance: number;
  taxon: TaxonPublic | null;
}

export interface DiversityPublic {
  id: string;
  sample_id: string;
  richness: number | null;
  shannon: number | null;
  simpson: number | null;
  chao1: number | null;
  faith_pd: number | null;
  evenness: number | null;
}

export interface ConservationRecord {
  id: string;
  species: string;
  gbif_key: number | null;
  gbif_occurrence_count: number | null;
  iucn_category: string | null;
  iucn_assessment_year: number | null;
  is_invasive: boolean;
  legal_flags: Record<string, string> | null;
  fetched_at: string;
}

export interface ConservationSummary {
  job_id: string;
  species_queried: number;
  species_with_gbif: number;
  species_with_iucn: number;
  threatened_count: number;
  lookup_failed_count: number;
  api_degraded: boolean;
  records: ConservationRecord[];
}

export interface ProvenanceManifest {
  id: string;
  job_id: string;
  schema_version: string;
  manifest: Record<string, unknown>;
  manifest_sha256: string;
  signature: string;
  signed_at: string;
  created_at: string;
}

export interface JobResultsSummary {
  job_id: string;
  status: string;
  pipeline_version: string | null;
  parameter_hash: string | null;
  n_asvs: number;
  n_assigned: number;
  diversity: DiversityPublic | null;
  amplicon: string;
}

export interface EIIComponent {
  key: string;
  name: string;
  weight: number;
  available: boolean;
  value: number | null;
  detail: string;
}

export interface IntegrityIndex {
  job_id: string;
  version: string;
  score: number | null;
  grade: string | null;
  assessed_weight: number;
  components: EIIComponent[];
}

// ─── Auth ─────────────────────────────────────────────────────────

export async function signup(email: string, password: string): Promise<TokenPair> {
  const tokens = await apiFetch<TokenPair>("/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(tokens.access_token);
  localStorage.setItem("relict_refresh_token", tokens.refresh_token);
  return tokens;
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const tokens = await apiFetch<TokenPair>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  setAccessToken(tokens.access_token);
  localStorage.setItem("relict_refresh_token", tokens.refresh_token);
  return tokens;
}

export async function getMe(): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me");
}

export function logout() {
  setAccessToken(null);
  localStorage.removeItem("relict_refresh_token");
}

// ─── Samples ──────────────────────────────────────────────────────

export const AMPLICON_MARKERS = [
  { value: "16S_V4", label: "16S V4", note: "bacteria / archaea · SILVA" },
  { value: "18S_V9", label: "18S V9", note: "eukaryotes · SILVA" },
  { value: "12S_MiFish", label: "12S MiFish", note: "fish · MIDORI2" },
  { value: "COI_Leray", label: "COI Leray", note: "invertebrates · MIDORI2" },
  { value: "ITS2", label: "ITS2", note: "fungi / plants" },
  { value: "rbcL", label: "rbcL", note: "plants" },
] as const;

export async function uploadSample(file: File, amplicon: string): Promise<{ sample: SamplePublic; download_url: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("amplicon", amplicon);
  const res = await fetch(`${API_V1}/samples/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail || body?.error?.message || `Upload failed: ${res.status}`);
  }
  return res.json();
}

// ─── Jobs ─────────────────────────────────────────────────────────

export async function getJob(jobId: string): Promise<JobPublic> {
  return apiFetch<JobPublic>(`/jobs/${jobId}`);
}

export async function listJobs(limit = 50, offset = 0): Promise<{ items: JobPublic[]; total: number }> {
  return apiFetch(`/jobs?limit=${limit}&offset=${offset}`);
}

export async function cancelJob(jobId: string): Promise<JobPublic> {
  return apiFetch<JobPublic>(`/jobs/${jobId}/cancel`, { method: "POST" });
}

// ─── Results ──────────────────────────────────────────────────────

export async function getJobSummary(jobId: string): Promise<JobResultsSummary> {
  return apiFetch<JobResultsSummary>(`/jobs/${jobId}/summary`);
}

export async function getJobASVs(jobId: string): Promise<ASVWithTaxon[]> {
  return apiFetch<ASVWithTaxon[]>(`/jobs/${jobId}/asvs`);
}

export async function getJobDiversity(jobId: string): Promise<DiversityPublic | null> {
  return apiFetch<DiversityPublic | null>(`/jobs/${jobId}/diversity`);
}

export async function getJobConservation(jobId: string): Promise<ConservationSummary> {
  return apiFetch<ConservationSummary>(`/jobs/${jobId}/conservation`);
}

export async function getJobProvenance(jobId: string): Promise<ProvenanceManifest> {
  return apiFetch<ProvenanceManifest>(`/jobs/${jobId}/provenance`);
}

export async function getJobIntegrity(jobId: string): Promise<IntegrityIndex> {
  return apiFetch<IntegrityIndex>(`/jobs/${jobId}/integrity`);
}

export interface OrdinationPoint {
  asv_id: string;
  x: number;
  y: number;
  cluster: number;
}

export interface OrdinationResponse {
  n_asvs: number;
  n_clusters: number;
  n_noise_points: number;
  skipped: boolean;
  reason: string | null;
  points: OrdinationPoint[];
  umap_params: Record<string, unknown> | null;
  hdbscan_params: Record<string, unknown> | null;
}

export async function getJobOrdination(jobId: string): Promise<OrdinationResponse> {
  return apiFetch<OrdinationResponse>(`/jobs/${jobId}/ordination`);
}

// ─── Exports ──────────────────────────────────────────────────────

// Export URLs are absolute when API_BASE is set so <a href=...> works
// across origins; otherwise relative so the Vite proxy can forward them.
export function getDwcaUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/export/dwca`;
}

export function getCsvUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/export/csv`;
}

export function getBiomUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/export/biom`;
}

export function getReportUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/export/report`;
}

export async function downloadExport(url: string, filename: string) {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

// ─── Public provenance verification (no auth, root-mounted) ─────────

export interface PublicKey {
  algorithm: string;
  public_key_b64: string;
  public_key_pem: string;
}

export interface VerifyResult {
  verified: boolean;
  content_hash_ok: boolean;
  signature_ok: boolean;
  computed_sha256: string;
  claimed_sha256: string | null;
  algorithm: string;
  detail: string;
}

export async function getPublicKey(): Promise<PublicKey> {
  const res = await fetch(`${API_BASE}/public-key`);
  if (!res.ok) throw new Error(`No public key available (${res.status})`);
  return res.json();
}

export async function verifyManifest(manifest: unknown): Promise<VerifyResult> {
  const res = await fetch(`${API_BASE}/provenance/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ manifest }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message || body?.detail || `Verification failed (${res.status})`);
  }
  return res.json();
}

// ─── Health ───────────────────────────────────────────────────────

export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

// ─── WebSocket ────────────────────────────────────────────────────

export function createJobWebSocket(jobId: string): WebSocket | null {
  const token = getAccessToken();
  if (!token) return null;
  // If VITE_API_BASE_URL is set (prod), derive the ws host from it so
  // WebSocket traffic reaches the Render backend instead of Vercel.
  // Otherwise fall back to the current origin (dev + ngrok path).
  let wsUrl: string;
  if (API_BASE) {
    wsUrl = `${API_BASE.replace(/^http/, "ws")}/ws/jobs/${jobId}?token=${token}`;
  } else {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsUrl = `${protocol}//${window.location.host}/ws/jobs/${jobId}?token=${token}`;
  }
  return new WebSocket(wsUrl);
}
