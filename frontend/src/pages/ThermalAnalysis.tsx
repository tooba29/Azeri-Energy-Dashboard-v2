import React, { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { toast } from "../components/Toast";
import {
  ArrowLeft,
  Thermometer,
  Upload,
  Download,
  Camera,
  Wind,
  Activity,
  Eye,
  CheckCircle2,
  XCircle,
  Loader2,
  Info,
  Crosshair,
  BarChart3,
  FileText,
  Gauge,
  Ruler,
  RefreshCw,
  Clock,
  Trash2,
  Layers,
  FileImage,
  X,
  ZoomIn,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { io, type Socket } from "socket.io-client";
import { API_BASE } from "../api/api";

const POLL_MS = 2000;

const PALETTES = [
  { id: 0, label: "White Hot" },
  { id: 1, label: "Fulgurite" },
  { id: 2, label: "Iron Red" },
  { id: 3, label: "Hot Iron" },
  { id: 4, label: "Medical" },
  { id: 5, label: "Arctic" },
  { id: 6, label: "Rainbow 1" },
  { id: 7, label: "Rainbow 2" },
  { id: 8, label: "Tint" },
  { id: 9, label: "Black Hot" },
];

const UNITS = ["Celsius", "Fahrenheit", "Kelvin"] as const;
type TempUnit = (typeof UNITS)[number];

const OBJECT_TYPES = [
  "", "electrical", "insulator", "transformer", "wire", "metal",
  "concrete", "vegetation", "solar_panel", "roof", "pipe", "motor",
  "human_skin", "water",
];

type LocalFile = {
  id: string;
  file: File;
  preview: string;
};

type ThermalStats = {
  min_c: number;
  max_c: number;
  mean_c: number;
  median_c: number;
  std_c: number;
  height: number;
  width: number;
  pixels: number;
};

type ThermalAnalysisData = {
  metadata_extracted: {
    camera_model: string | null;
    serial_number: string | null;
    focal_length_mm: number | null;
    f_number: number | null;
    image_width: number | null;
    image_height: number | null;
    timestamp: string | null;
    gps_coordinates: { latitude: number | null; longitude: number | null };
    altitude_m: number | null;
    altitude_source: string | null;
    camera_tilt_deg: number | null;
    emissivity_in_meta: number | null;
    reflected_temp_in_meta: number | null;
    atmospheric_temp_in_meta: number | null;
    humidity_in_meta: number | null;
  };
  distance_meters: { value: number; method: string; confidence: number; range?: string };
  environment: {
    ambient_temperature_c: { value: number; source: string; confidence: number };
    humidity_percent: { value: number; source: string; confidence: number };
  };
  thermal_parameters: {
    emissivity: { value: number; source: string; confidence: number; plausible_range?: string };
    reflected_temperature_c: { value: number; source: string; confidence: number };
  };
  thermal_correction_insights: string;
  analysis_notes: string;
};

type CardData = {
  localId?: string;
  fileId?: string;
  filename: string;
  localPreview?: string;
  status: "pending" | "uploading" | "queued" | "processing" | "complete" | "error";
  progress: number;
  progressLabel: string;
  thermalImageB64?: string;
  thermalImageUrl?: string;
  stats?: ThermalStats;
  analysis?: ThermalAnalysisData;
  unit?: string;
  error?: string;
};

type SdkHealth = {
  ok: boolean;
  sdk_initialized: boolean;
  sdk_message: string;
};

let _idCounter = 0;
const uid = () => `t_${++_idCounter}_${Date.now()}`;

function unitLabel(u: TempUnit) {
  return u === "Celsius" ? "°C" : u === "Fahrenheit" ? "°F" : "K";
}

function confidenceBadge(confidence: number) {
  const pct = Math.round(confidence * 100);
  const color =
    confidence >= 0.8 ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30" :
    confidence >= 0.5 ? "text-yellow-400 bg-yellow-500/10 border-yellow-500/30" :
    "text-red-400 bg-red-500/10 border-red-500/30";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${color}`}>
      <Gauge size={10} /> {pct}%
    </span>
  );
}

export default function ThermalAnalysis() {
  const reduceMotion = useReducedMotion();
  const transition = { duration: reduceMotion ? 0 : 0.3 };

  const [files, setFiles] = useState<LocalFile[]>([]);
  const [cards, setCards] = useState<Map<string, CardData>>(new Map());
  const [jobId, setJobId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ completed: 0, total: 0 });
  const [dragActive, setDragActive] = useState(false);
  const [previewId, setPreviewId] = useState<string | null>(null);

  const [palette, setPalette] = useState(2);
  const [unit, setUnit] = useState<TempUnit>("Celsius");
  const [objectType, setObjectType] = useState("");

  const [sdkHealth, setSdkHealth] = useState<SdkHealth | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [roiActive, setRoiActive] = useState(false);
  const [roiStart, setRoiStart] = useState<{ x: number; y: number } | null>(null);
  const [roiEnd, setRoiEnd] = useState<{ x: number; y: number } | null>(null);
  const [roiStats, setRoiStats] = useState<ThermalStats | null>(null);
  const [roiLoading, setRoiLoading] = useState(false);

  const socketRef = useRef<Socket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const cardsRef = useRef<Map<string, CardData>>(new Map());
  const nameToKeyRef = useRef<Map<string, string>>(new Map());

  const totalFiles = files.length;
  const canStart = totalFiles > 0 && !processing;

  useEffect(() => { jobIdRef.current = jobId; }, [jobId]);
  useEffect(() => { cardsRef.current = cards; }, [cards]);

  useEffect(() => {
    fetchHealth();
    return () => {
      socketRef.current?.disconnect();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/thermal/health`);
      if (res.ok) setSdkHealth(await res.json());
    } catch { /* ignore */ }
  };

  const updateCard = useCallback((key: string, patch: Partial<CardData>) => {
    setCards(prev => {
      const existing = prev.get(key);
      if (!existing) return prev;
      const next = new Map(prev);
      next.set(key, { ...existing, ...patch });
      return next;
    });
  }, []);

  const addFiles = useCallback((fileList: File[]) => {
    const imageFiles = fileList.filter(f => f.type.startsWith("image/"));
    if (imageFiles.length === 0) {
      toast.warning("No image files found", 3000);
      return;
    }
    const newFiles: LocalFile[] = imageFiles.map(file => ({
      id: uid(),
      file,
      preview: URL.createObjectURL(file),
    }));
    setFiles(prev => [...prev, ...newFiles]);
    toast.success(`Added ${imageFiles.length} thermal image(s)`, 2000);
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles(prev => {
      const f = prev.find(x => x.id === id);
      if (f) URL.revokeObjectURL(f.preview);
      return prev.filter(x => x.id !== id);
    });
  }, []);

  const clearAll = useCallback(() => {
    files.forEach(f => URL.revokeObjectURL(f.preview));
    setFiles([]);
    setCards(new Map());
    setJobId(null);
    setBatchProgress({ completed: 0, total: 0 });
    setProcessing(false);
    setPreviewId(null);
    socketRef.current?.disconnect();
    socketRef.current = null;
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    nameToKeyRef.current.clear();
  }, [files]);

  const syncFromApi = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/thermal/batch/results/${id}`);
      if (!res.ok) return;
      const body = await res.json();

      setCards(prev => {
        const next = new Map(prev);
        let changed = false;
        (body.results || []).forEach((r: any) => {
          const cardKey = nameToKeyRef.current.get(r.file_id) || nameToKeyRef.current.get(r.filename);
          if (!cardKey) return;
          const existing = next.get(cardKey);
          if (existing?.status === "complete") return;
          changed = true;
          next.set(cardKey, {
            ...(existing || {} as CardData),
            fileId: r.file_id,
            status: "complete",
            progress: 100,
            progressLabel: "Complete",
            thermalImageB64: r.thermal_image_base64_png,
            thermalImageUrl: r.thermal_image_url,
            stats: r.stats,
            analysis: r.analysis,
            unit: r.unit,
          });
          nameToKeyRef.current.set(r.file_id, cardKey);
        });
        return changed ? next : prev;
      });

      const total = body.total || (body.results?.length ?? 0);
      const completed = body.completed || (body.results?.length ?? 0);
      setBatchProgress({ completed, total });

      if (body.status === "complete" || completed >= total) {
        setProcessing(false);
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      }
    } catch { /* retry next poll */ }
  }, []);

  const connectSocket = useCallback((id: string) => {
    if (socketRef.current) { socketRef.current.disconnect(); socketRef.current = null; }

    const sock = io({ path: "/socket.io/", transports: ["websocket", "polling"] });
    socketRef.current = sock;

    sock.on("connect", () => {
      sock.emit("subscribe_thermal_job", { job_id: id });
      syncFromApi(id);
    });

    sock.on("thermal_queued", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const cardKey = nameToKeyRef.current.get(d.filename);
      if (cardKey) {
        nameToKeyRef.current.set(d.file_id, cardKey);
        updateCard(cardKey, { fileId: d.file_id, status: "queued", progressLabel: "Queued" });
      }
    });

    sock.on("thermal_start", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const cardKey = nameToKeyRef.current.get(d.file_id) || nameToKeyRef.current.get(d.filename);
      if (cardKey) updateCard(cardKey, { status: "processing", progressLabel: "Analyzing..." });
    });

    sock.on("thermal_result", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const cardKey = nameToKeyRef.current.get(d.file_id) || nameToKeyRef.current.get(d.filename);
      if (cardKey) {
        if (d.error) {
          updateCard(cardKey, { status: "error", error: d.error });
        } else {
          updateCard(cardKey, {
            fileId: d.file_id,
            status: "complete",
            progress: 100,
            progressLabel: "Complete",
            thermalImageB64: d.thermal_image_base64_png,
            thermalImageUrl: d.thermal_image_url,
            stats: d.stats,
            analysis: d.analysis,
            unit: d.unit,
          });
        }
      }
      setBatchProgress({ completed: d.completed || 0, total: d.total || 0 });
    });

    sock.on("thermal_batch_complete", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      setBatchProgress({ completed: d.total_files, total: d.total_files });
      setProcessing(false);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      toast.success(`Thermal analysis complete! ${d.total_files} files processed.`, 5000);
    });
  }, [syncFromApi, updateCard]);

  const startAnalysis = useCallback(async () => {
    if (files.length === 0) return;
    setProcessing(true);
    nameToKeyRef.current.clear();

    const newCards = new Map<string, CardData>();
    files.forEach(lf => {
      newCards.set(lf.id, {
        localId: lf.id,
        filename: lf.file.name,
        localPreview: lf.preview,
        status: "pending",
        progress: 0,
        progressLabel: "Pending",
      });
      nameToKeyRef.current.set(lf.file.name, lf.id);
    });
    setCards(newCards);
    setBatchProgress({ completed: 0, total: files.length });

    try {
      const batchRes = await fetch(`${API_BASE}/api/thermal/batch/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          total: files.length,
          palette,
          unit,
          object_type: objectType || null,
        }),
      });
      if (!batchRes.ok) {
        const errText = await batchRes.text().catch(() => "");
        throw new Error(errText || `Server returned ${batchRes.status}`);
      }
      const { job_id } = await batchRes.json();
      setJobId(job_id);
      jobIdRef.current = job_id;

      connectSocket(job_id);

      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(() => syncFromApi(job_id), POLL_MS);

      const CONCURRENT = 3;
      const queue = [...files];

      const uploadOne = async (lf: LocalFile) => {
        updateCard(lf.id, { status: "uploading", progressLabel: "Uploading..." });
        const formData = new FormData();
        formData.append("job_id", job_id);
        formData.append("file", lf.file);
        try {
          const uploadRes = await fetch(`${API_BASE}/api/thermal/batch/file`, { method: "POST", body: formData });
          if (!uploadRes.ok) throw new Error(`Upload failed: ${uploadRes.status}`);
          setCards(prev => {
            const existing = prev.get(lf.id);
            if (existing && existing.status === "uploading") {
              const next = new Map(prev);
              next.set(lf.id, { ...existing, status: "queued", progressLabel: "Queued" });
              return next;
            }
            return prev;
          });
        } catch (err: any) {
          updateCard(lf.id, { status: "error", error: err.message || "Upload failed" });
        }
      };

      const workers = Array.from({ length: Math.min(CONCURRENT, queue.length) }, async () => {
        while (queue.length > 0) {
          const lf = queue.shift()!;
          await uploadOne(lf);
        }
      });
      await Promise.all(workers);

      toast.info(`Uploaded ${files.length} files. Thermal analysis in progress...`, 3000);
    } catch (err: any) {
      toast.error(`Failed to start analysis: ${err.message}`, 5000);
      setProcessing(false);
    }
  }, [files, palette, unit, objectType, connectSocket, syncFromApi, updateCard]);

  const completedCards = useMemo(() =>
    Array.from(cards.entries()).filter(([, c]) => c.status === "complete").map(([key]) => key),
    [cards]
  );

  const previewCard = previewId ? cards.get(previewId) : null;

  const navigatePreview = useCallback((dir: number) => {
    if (completedCards.length === 0) return;
    const idx = previewId ? completedCards.indexOf(previewId) : -1;
    const next = dir > 0
      ? (idx + 1) % completedCards.length
      : (idx - 1 + completedCards.length) % completedCards.length;
    setPreviewId(completedCards[next]);
  }, [completedCards, previewId]);

  useEffect(() => {
    if (!previewId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPreviewId(null);
      if (e.key === "ArrowLeft") navigatePreview(-1);
      if (e.key === "ArrowRight") navigatePreview(1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [previewId, navigatePreview]);

  const exportCsv = useCallback(async (cardKey: string) => {
    const card = cards.get(cardKey);
    const lf = files.find(f => f.id === cardKey);
    if (!lf || !card) return;
    setExporting(cardKey);
    const form = new FormData();
    form.append("image", lf.file);
    form.append("unit", unit);
    try {
      const res = await fetch(`${API_BASE}/api/thermal/export/csv`, { method: "POST", body: form });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${lf.file.name.replace(/\.[^.]+$/, "")}_temperatures.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV exported", 2000);
    } catch (err: any) {
      toast.error(err.message, 4000);
    } finally {
      setExporting(null);
    }
  }, [cards, files, unit]);

  const handleRoiMouseDown = useCallback((e: React.MouseEvent<HTMLImageElement>) => {
    if (!roiActive) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * (previewCard?.stats?.width || 640));
    const y = Math.round(((e.clientY - rect.top) / rect.height) * (previewCard?.stats?.height || 512));
    setRoiStart({ x, y });
    setRoiEnd(null);
    setRoiStats(null);
  }, [roiActive, previewCard]);

  const handleRoiMouseUp = useCallback(async (e: React.MouseEvent<HTMLImageElement>) => {
    if (!roiActive || !roiStart) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.round(((e.clientX - rect.left) / rect.width) * (previewCard?.stats?.width || 640));
    const y = Math.round(((e.clientY - rect.top) / rect.height) * (previewCard?.stats?.height || 512));
    setRoiEnd({ x, y });

    const lf = files.find(f => f.id === previewId);
    if (!lf) return;

    setRoiLoading(true);
    try {
      const form = new FormData();
      form.append("image", lf.file);
      form.append("x1", String(Math.min(roiStart.x, x)));
      form.append("y1", String(Math.min(roiStart.y, y)));
      form.append("x2", String(Math.max(roiStart.x, x)));
      form.append("y2", String(Math.max(roiStart.y, y)));
      form.append("unit", unit);
      const res = await fetch(`${API_BASE}/api/thermal/roi`, { method: "POST", body: form });
      if (res.ok) {
        const data = await res.json();
        setRoiStats(data.stats ?? data);
      }
    } catch { /* ignore */ } finally {
      setRoiLoading(false);
    }
  }, [roiActive, roiStart, previewCard, previewId, files, unit]);

  const u = unitLabel(unit);
  const analysis = previewCard?.analysis;
  const meta = analysis?.metadata_extracted;
  const stats = previewCard?.stats;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={transition}
        className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <Link to="/dashboard" className="text-neutral-400 hover:text-white transition-colors">
                <ArrowLeft size={20} />
              </Link>
              <Thermometer className="text-emerald-400" size={22} />
              <div className="text-sm text-emerald-400 uppercase tracking-wider font-medium">Thermal Analysis</div>
              {sdkHealth && (
                <span className={`ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                  sdkHealth.sdk_initialized
                    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
                    : "text-red-400 bg-red-500/10 border-red-500/30"
                }`}>
                  {sdkHealth.sdk_initialized ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
                  DJI SDK {sdkHealth.sdk_initialized ? "Ready" : "Offline"}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-white mb-2">DJI R-JPEG Thermal Processing</h1>
            <p className="text-sm text-neutral-300 leading-relaxed">
              Upload DJI R-JPEG thermal images for batch analysis. Temperature mapping, metadata extraction,
              environmental data, and correction insights — processed in queue.
            </p>
          </div>
          <div className="flex gap-2">
            {totalFiles > 0 && !processing && (
              <button onClick={clearAll} className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors flex items-center gap-2">
                <Trash2 size={16} /> Clear All
              </button>
            )}
            <button
              onClick={startAnalysis}
              disabled={!canStart}
              className="rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white px-5 py-2.5 text-sm font-semibold hover:shadow-lg disabled:opacity-60 transition-all flex items-center gap-2"
            >
              {processing ? (
                <><Clock className="animate-spin" size={16} /> Processing...</>
              ) : (
                <><Activity size={16} /> Start Analysis{totalFiles > 0 ? ` (${totalFiles})` : ""}</>
              )}
            </button>
          </div>
        </div>
      </motion.div>

      {/* Upload + Config */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upload Zone */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ ...transition, delay: reduceMotion ? 0 : 0.05 }}
          className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium"
        >
          <div className="flex items-center gap-2 mb-4">
            <Upload className="text-emerald-400" size={20} />
            <h2 className="font-semibold text-white text-lg">Image Upload</h2>
          </div>

          <div
            onDragEnter={e => { e.preventDefault(); e.stopPropagation(); setDragActive(true); }}
            onDragLeave={e => { e.preventDefault(); e.stopPropagation(); setDragActive(false); }}
            onDragOver={e => { e.preventDefault(); e.stopPropagation(); }}
            onDrop={e => { e.preventDefault(); e.stopPropagation(); setDragActive(false); if (e.dataTransfer.files?.length) addFiles(Array.from(e.dataTransfer.files)); }}
            className={`rounded-xl border-2 border-dashed transition-all p-4 ${
              dragActive
                ? "border-emerald-400 bg-emerald-400/10"
                : files.length > 0
                ? "border-emerald-500/40 bg-emerald-500/5"
                : "border-neutral-700 bg-premium-card/30 hover:border-emerald-400/40"
            }`}
          >
            {files.length > 0 ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <CheckCircle2 size={16} />
                  <span>{files.length} thermal image(s) selected</span>
                </div>
                <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
                  {files.map(f => (
                    <div key={f.id} className="relative group">
                      <img src={f.preview} alt={f.file.name} className="w-16 h-16 object-cover rounded-lg border border-neutral-700" />
                      {!processing && (
                        <button
                          onClick={() => removeFile(f.id)}
                          className="absolute -top-1 -right-1 bg-red-500 rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X size={10} className="text-white" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <input type="file" accept="image/*" multiple onChange={e => { if (e.target.files?.length) addFiles(Array.from(e.target.files)); e.target.value = ""; }} className="hidden" id="thermal-add-more" />
                <label htmlFor="thermal-add-more" className="inline-block rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-1.5 text-xs font-semibold hover:bg-premium-card-hover cursor-pointer transition-colors">
                  + Add More
                </label>
              </div>
            ) : (
              <div className="text-center py-6">
                <Thermometer className="text-3xl text-neutral-500 mx-auto mb-2" size={36} />
                <div className="text-sm text-neutral-300 mb-2">Drop thermal images here or click to browse</div>
                <input type="file" accept="image/*" multiple onChange={e => { if (e.target.files?.length) addFiles(Array.from(e.target.files)); e.target.value = ""; }} className="hidden" id="thermal-upload" />
                <label htmlFor="thermal-upload" className="inline-block rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white px-5 py-2.5 text-sm font-semibold cursor-pointer hover:shadow-lg transition-all">
                  Select Thermal Images
                </label>
              </div>
            )}
          </div>
          <div className="mt-2 text-xs text-neutral-400">DJI R-JPEG radiometric thermal images for temperature analysis</div>

          {totalFiles > 0 && !processing && (
            <div className="mt-3 rounded-xl bg-premium-card/50 border border-neutral-700 p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm text-white font-medium">{totalFiles} file{totalFiles !== 1 ? "s" : ""} ready</div>
                <span className="text-xs text-emerald-400">{totalFiles} Thermal</span>
              </div>
            </div>
          )}
        </motion.div>

        {/* Config */}
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ ...transition, delay: reduceMotion ? 0 : 0.1 }}
          className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium"
        >
          <div className="flex items-center gap-2 mb-6">
            <Activity className="text-emerald-400" size={20} />
            <h2 className="font-semibold text-white text-lg">Analysis Configuration</h2>
          </div>
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-white">Object Type (Emissivity)</div>
              </div>
              <select
                value={objectType} onChange={e => setObjectType(e.target.value)} disabled={processing}
                className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
              >
                <option value="">Auto / Default</option>
                {OBJECT_TYPES.filter(Boolean).map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}</option>
                ))}
              </select>
            </div>

            <div>
              <div className="text-sm font-medium text-white mb-2">Color Palette</div>
              <select
                value={palette} onChange={e => setPalette(Number(e.target.value))} disabled={processing}
                className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-emerald-500 outline-none disabled:opacity-50"
              >
                {PALETTES.map(p => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
            </div>

            <div>
              <div className="text-sm font-medium text-white mb-2">Temperature Unit</div>
              <div className="flex gap-1">
                {UNITS.map(u => (
                  <button
                    key={u} onClick={() => setUnit(u)} disabled={processing}
                    className={`flex-1 rounded-lg px-3 py-2 text-xs font-semibold transition-all disabled:opacity-50 ${
                      unit === u
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                        : "bg-premium-card border border-neutral-700 text-neutral-400 hover:text-white"
                    }`}
                  >{u}</button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-neutral-700 bg-premium-card/30 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="text-emerald-400" size={16} />
                <div className="text-sm font-semibold text-white">Processing Pipeline</div>
              </div>
              <div className="space-y-2">
                {["DJI SDK initialization", "EXIF/XMP metadata extraction", "Temperature map generation", "Pseudo-color visualization", "Environmental analysis"].map((step, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-neutral-700 flex items-center justify-center text-xs font-bold text-neutral-400">{i + 1}</div>
                    <span className="text-xs text-neutral-300">{step}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Progress */}
      {processing && (
        <div className="glass rounded-2xl border border-emerald-500/50 bg-emerald-500/10 p-4 shadow-premium">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Clock className="text-emerald-400 animate-spin" size={18} />
              <span className="font-semibold text-white">Processing Thermal Images</span>
            </div>
            <span className="text-sm text-neutral-300">
              {batchProgress.total > 0 ? `${Math.round((batchProgress.completed / batchProgress.total) * 100)}%` : "—"}
            </span>
          </div>
          <div className="w-full bg-neutral-800 rounded-full h-2.5 overflow-hidden">
            {batchProgress.total > 0 ? (
              <div className="bg-gradient-to-r from-emerald-500 to-teal-500 h-full transition-all duration-300 rounded-full" style={{ width: `${(batchProgress.completed / batchProgress.total) * 100}%` }} />
            ) : (
              <div className="h-full w-1/3 animate-progress-indeterminate rounded-full bg-gradient-to-r from-transparent via-emerald-500/70 to-transparent" />
            )}
          </div>
          <div className="mt-2 text-xs text-neutral-400">
            {batchProgress.total > 0 ? `${batchProgress.completed} of ${batchProgress.total} files completed` : "Uploading files..."}
          </div>
        </div>
      )}

      {/* Results Grid */}
      {cards.size > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Layers className="text-emerald-400" size={20} />
              Analysis Results ({cards.size})
            </h2>
            <div className="flex gap-3 text-xs text-neutral-400">
              {(() => {
                const completed = Array.from(cards.values()).filter(c => c.status === "complete").length;
                const errors = Array.from(cards.values()).filter(c => c.status === "error").length;
                const active = Array.from(cards.values()).filter(c => ["processing", "queued", "uploading"].includes(c.status)).length;
                return (
                  <>
                    {completed > 0 && <span className="text-emerald-400">&#x2713; {completed} complete</span>}
                    {active > 0 && <span className="text-cyan-400">&#x21BB; {active} processing</span>}
                    {errors > 0 && <span className="text-red-400">&#x2717; {errors} failed</span>}
                  </>
                );
              })()}
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {Array.from(cards.entries()).map(([key, card]) => (
              <div
                key={key}
                onClick={() => card.status === "complete" && setPreviewId(key)}
                className={`rounded-xl border overflow-hidden transition-all group ${
                  card.status === "complete"
                    ? "border-emerald-500/30 bg-emerald-500/5 cursor-pointer hover:shadow-glow hover:border-emerald-400/50"
                    : card.status === "error"
                    ? "border-red-500/30 bg-red-500/5"
                    : card.status === "processing"
                    ? "border-emerald-500/50 bg-emerald-500/5"
                    : "border-neutral-800 bg-premium-card/30"
                }`}
              >
                <div className="relative aspect-square bg-neutral-800 overflow-hidden">
                  {card.status === "complete" && card.thermalImageB64 ? (
                    <img src={`data:image/png;base64,${card.thermalImageB64}`} alt={card.filename} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" loading="lazy" />
                  ) : card.status === "complete" && card.thermalImageUrl ? (
                    <img src={card.thermalImageUrl} alt={card.filename} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" loading="lazy" />
                  ) : card.localPreview ? (
                    <img src={card.localPreview} alt={card.filename} className="w-full h-full object-cover opacity-50" loading="lazy" />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center"><FileImage className="text-neutral-600" size={32} /></div>
                  )}

                  {card.status !== "complete" && card.status !== "error" && (
                    <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center gap-2">
                      {card.status === "processing" ? <Clock className="text-emerald-400 animate-spin" size={24} /> : <Clock className="text-neutral-400" size={24} />}
                      <span className="text-[10px] text-white font-medium px-2 text-center">{card.progressLabel}</span>
                    </div>
                  )}

                  {card.status === "error" && (
                    <div className="absolute inset-0 bg-black/50 flex flex-col items-center justify-center gap-1 px-2">
                      <XCircle className="text-red-400" size={24} />
                      <span className="text-[10px] text-red-300 text-center">{card.error || "Error"}</span>
                    </div>
                  )}

                  <div className="absolute top-1 left-1">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-500/80 text-white">THERMAL</span>
                  </div>

                  {card.status === "complete" && (
                    <div className="absolute bottom-1 right-1"><CheckCircle2 className="text-emerald-400 drop-shadow-lg" size={16} /></div>
                  )}
                </div>
                <div className="p-2">
                  <p className="text-[11px] truncate font-medium text-white" title={card.filename}>{card.filename}</p>
                  {card.status === "complete" && card.stats && (
                    <div className="mt-1 text-[10px] text-neutral-400">
                      {card.stats.min_c != null ? card.stats.min_c.toFixed(1) : "—"}–{card.stats.max_c != null ? card.stats.max_c.toFixed(1) : "—"} {u}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {previewCard && previewId && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-start justify-center overflow-y-auto py-8 px-4" onClick={() => setPreviewId(null)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.2 }}
            className="glass rounded-2xl border border-neutral-700 w-full max-w-5xl shadow-premium-lg relative"
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between p-5 border-b border-neutral-700">
              <div className="flex items-center gap-3">
                <Eye className="text-emerald-400" size={20} />
                <div>
                  <h3 className="text-lg font-bold text-white">{previewCard.filename}</h3>
                  <p className="text-xs text-neutral-400">Thermal Analysis Detail</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => navigatePreview(-1)} className="rounded-lg glass border border-neutral-700 p-2 text-neutral-400 hover:text-white transition-colors">
                  <ChevronLeft size={16} />
                </button>
                <span className="text-xs text-neutral-500">{completedCards.indexOf(previewId) + 1}/{completedCards.length}</span>
                <button onClick={() => navigatePreview(1)} className="rounded-lg glass border border-neutral-700 p-2 text-neutral-400 hover:text-white transition-colors">
                  <ChevronRight size={16} />
                </button>
                <button
                  onClick={() => exportCsv(previewId)}
                  disabled={exporting === previewId}
                  className="rounded-lg bg-emerald-600/20 border border-emerald-500/40 text-emerald-400 px-3 py-2 text-xs font-semibold hover:bg-emerald-600/30 transition-colors flex items-center gap-1.5 disabled:opacity-50"
                >
                  {exporting === previewId ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                  CSV
                </button>
                <button onClick={() => { setPreviewId(null); setRoiActive(false); setRoiStart(null); setRoiEnd(null); setRoiStats(null); }} className="rounded-lg glass border border-neutral-700 p-2 text-neutral-400 hover:text-white transition-colors">
                  <X size={16} />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-5">
              {/* Thermal Image + Stats Row */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                {previewCard.thermalImageB64 && (
                  <div className="lg:col-span-2 rounded-xl overflow-hidden border border-neutral-700 bg-black relative">
                    <img
                      src={`data:image/png;base64,${previewCard.thermalImageB64}`}
                      alt="Thermal"
                      className={`w-full h-auto ${roiActive ? "cursor-crosshair" : ""}`}
                      onMouseDown={handleRoiMouseDown}
                      onMouseUp={handleRoiMouseUp}
                      draggable={false}
                    />
                    {roiActive && roiStart && roiEnd && stats && (
                      <div
                        className="absolute border-2 border-emerald-400 bg-emerald-400/10 pointer-events-none"
                        style={{
                          left: `${(Math.min(roiStart.x, roiEnd.x) / stats.width) * 100}%`,
                          top: `${(Math.min(roiStart.y, roiEnd.y) / stats.height) * 100}%`,
                          width: `${(Math.abs(roiEnd.x - roiStart.x) / stats.width) * 100}%`,
                          height: `${(Math.abs(roiEnd.y - roiStart.y) / stats.height) * 100}%`,
                        }}
                      />
                    )}
                    <button
                      onClick={() => { setRoiActive(a => !a); setRoiStart(null); setRoiEnd(null); setRoiStats(null); }}
                      className={`absolute top-2 right-2 z-10 rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition-colors flex items-center gap-1.5 ${
                        roiActive
                          ? "bg-emerald-500/80 text-white border border-emerald-400"
                          : "bg-black/60 backdrop-blur-sm border border-neutral-500/50 text-neutral-200 hover:bg-black/80"
                      }`}
                    >
                      <Crosshair size={11} />
                      ROI
                    </button>
                    {roiActive && (
                      <div className="absolute top-2 left-2 rounded-lg bg-black/70 border border-emerald-500/50 px-2 py-1 text-[10px] text-emerald-400 flex items-center gap-1">
                        <Crosshair size={10} /> Drag to select
                      </div>
                    )}
                  </div>
                )}
                {stats && (
                  <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
                    <div className="flex items-center gap-2 mb-4">
                      <BarChart3 className="text-emerald-400" size={16} />
                      <h4 className="font-semibold text-white text-sm">Temperature Stats</h4>
                    </div>
                    <div className="space-y-2.5">
                      <StatRow label="Minimum" value={`${stats.min_c != null ? stats.min_c.toFixed(2) : "—"} ${u}`} color="text-blue-400" />
                      <StatRow label="Maximum" value={`${stats.max_c != null ? stats.max_c.toFixed(2) : "—"} ${u}`} color="text-red-400" />
                      <StatRow label="Mean" value={`${stats.mean_c != null ? stats.mean_c.toFixed(2) : "—"} ${u}`} color="text-emerald-400" />
                      <StatRow label="Median" value={`${stats.median_c != null ? stats.median_c.toFixed(2) : "—"} ${u}`} color="text-yellow-400" />
                      <StatRow label="Std Dev" value={`${stats.std_c != null ? stats.std_c.toFixed(2) : "—"} ${u}`} color="text-purple-400" />
                      <div className="border-t border-neutral-700 my-2" />
                      <StatRow label="Resolution" value={`${stats.width ?? "—"} × ${stats.height ?? "—"}`} color="text-neutral-300" />
                      <StatRow label="Temp Range" value={`${stats.max_c != null && stats.min_c != null ? (stats.max_c - stats.min_c).toFixed(2) : "—"} ${u}`} color="text-emerald-300" />
                    </div>
                    {roiLoading && (
                      <div className="mt-3 pt-3 border-t border-neutral-700 flex items-center gap-2 text-xs text-emerald-400">
                        <Loader2 size={12} className="animate-spin" /> Computing ROI stats...
                      </div>
                    )}
                    {roiStats && !roiLoading && (
                      <div className="mt-3 pt-3 border-t border-neutral-700">
                        <div className="flex items-center gap-2 mb-2">
                          <Crosshair className="text-emerald-400" size={12} />
                          <span className="text-xs font-semibold text-emerald-400">ROI Statistics</span>
                        </div>
                        <div className="space-y-1.5">
                          <StatRow label="ROI Min" value={`${roiStats.min_c != null ? roiStats.min_c.toFixed(2) : "—"} ${u}`} color="text-blue-400" />
                          <StatRow label="ROI Max" value={`${roiStats.max_c != null ? roiStats.max_c.toFixed(2) : "—"} ${u}`} color="text-red-400" />
                          <StatRow label="ROI Mean" value={`${roiStats.mean_c != null ? roiStats.mean_c.toFixed(2) : "—"} ${u}`} color="text-emerald-400" />
                          <StatRow label="ROI Std" value={`${roiStats.std_c != null ? roiStats.std_c.toFixed(2) : "—"} ${u}`} color="text-purple-400" />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Analysis Cards */}
              {analysis && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {/* Camera, GPS & Metadata (merged) */}
                  <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Camera className="text-emerald-400" size={16} />
                      <h4 className="font-semibold text-white text-sm">Camera & Location</h4>
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                      <DetailRow label="Camera" value={meta?.camera_model} />
                      <DetailRow label="Serial" value={meta?.serial_number} />
                      <DetailRow label="Focal Length" value={meta?.focal_length_mm ? `${meta.focal_length_mm} mm` : null} />
                      <DetailRow label="F-Number" value={meta?.f_number ? `f/${meta.f_number}` : null} />
                      <DetailRow label="Timestamp" value={meta?.timestamp} />
                      <DetailRow label="Tilt" value={meta?.camera_tilt_deg != null ? `${meta.camera_tilt_deg.toFixed(1)}°` : null} />
                      <DetailRow label="Latitude" value={meta?.gps_coordinates?.latitude != null ? meta.gps_coordinates.latitude.toFixed(6) : null} />
                      <DetailRow label="Longitude" value={meta?.gps_coordinates?.longitude != null ? meta.gps_coordinates.longitude.toFixed(6) : null} />
                      <DetailRow label="Altitude" value={meta?.altitude_m != null ? `${meta.altitude_m.toFixed(1)} m` : null} />
                      <DetailRow label="Resolution" value={meta?.image_width && meta?.image_height ? `${meta.image_width}×${meta.image_height}` : null} />
                    </div>
                  </div>

                  {/* Distance & Environment (merged) */}
                  <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Wind className="text-emerald-400" size={16} />
                      <h4 className="font-semibold text-white text-sm">Distance & Environment</h4>
                    </div>
                    <div className="space-y-3">
                      {analysis.distance_meters?.value != null && (
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-xs text-neutral-400">Distance</span>
                            <div className="text-lg font-bold text-white">{analysis.distance_meters.value.toFixed(1)} m</div>
                            <p className="text-[10px] text-neutral-500">{analysis.distance_meters.method?.replace(/_/g, " ") ?? ""}</p>
                          </div>
                          {confidenceBadge(analysis.distance_meters.confidence)}
                        </div>
                      )}
                      <div className="border-t border-neutral-700" />
                      <div className="grid grid-cols-2 gap-3">
                        {analysis.environment?.ambient_temperature_c?.value != null && (
                          <div>
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="text-xs text-neutral-400">Ambient Temp</span>
                              {confidenceBadge(analysis.environment.ambient_temperature_c.confidence)}
                            </div>
                            <span className="text-base font-bold text-white">{analysis.environment.ambient_temperature_c.value}°C</span>
                          </div>
                        )}
                        {analysis.environment?.humidity_percent?.value != null && (
                          <div>
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="text-xs text-neutral-400">Humidity</span>
                              {confidenceBadge(analysis.environment.humidity_percent.confidence)}
                            </div>
                            <span className="text-base font-bold text-white">{analysis.environment.humidity_percent.value}%</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Thermal Parameters */}
                  {analysis.thermal_parameters && (
                  <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Gauge className="text-emerald-400" size={16} />
                      <h4 className="font-semibold text-white text-sm">Thermal Parameters</h4>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      {analysis.thermal_parameters.emissivity && (
                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-xs text-neutral-400">Emissivity</span>
                            {confidenceBadge(analysis.thermal_parameters.emissivity.confidence)}
                          </div>
                          <span className="text-lg font-bold text-white">{analysis.thermal_parameters.emissivity.value != null ? analysis.thermal_parameters.emissivity.value.toFixed(3) : "—"}</span>
                          <p className="text-[10px] text-neutral-500">{analysis.thermal_parameters.emissivity.source ?? ""}</p>
                        </div>
                      )}
                      {analysis.thermal_parameters.reflected_temperature_c && (
                        <div>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-xs text-neutral-400">Reflected Temp</span>
                            {confidenceBadge(analysis.thermal_parameters.reflected_temperature_c.confidence)}
                          </div>
                          <span className="text-lg font-bold text-white">{analysis.thermal_parameters.reflected_temperature_c.value != null ? `${analysis.thermal_parameters.reflected_temperature_c.value.toFixed(1)}°C` : "—"}</span>
                          <p className="text-[10px] text-neutral-500">{analysis.thermal_parameters.reflected_temperature_c.source ?? ""}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  )}

                  {/* Correction Insights — professional card */}
                  {analysis.thermal_correction_insights && (
                  <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <FileText className="text-emerald-400" size={16} />
                      <h4 className="font-semibold text-white text-sm">Correction Insights</h4>
                    </div>
                    <div className="space-y-2">
                      {analysis.thermal_correction_insights.split("\n").map((line, i) => {
                        const isWarning = line.toLowerCase().includes("critical") || line.toLowerCase().includes("high");
                        const isGood = line.toLowerCase().includes("good") || line.toLowerCase().includes("low") || line.toLowerCase().includes("near-blackbody");
                        return (
                          <div key={i} className={`flex items-start gap-2.5 rounded-lg px-3 py-2 text-xs ${
                            isWarning ? "bg-red-500/10 border border-red-500/20" :
                            isGood ? "bg-emerald-500/10 border border-emerald-500/20" :
                            "bg-neutral-800/50 border border-neutral-700/50"
                          }`}>
                            <div className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                              isWarning ? "bg-red-400" : isGood ? "bg-emerald-400" : "bg-neutral-500"
                            }`} />
                            <span className="text-neutral-200 leading-relaxed">{line}</span>
                          </div>
                        );
                      })}
                    </div>
                    {analysis.analysis_notes && (
                      <p className="mt-3 text-[10px] text-neutral-500 leading-relaxed border-t border-neutral-700 pt-2">{analysis.analysis_notes}</p>
                    )}
                  </div>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}

function StatRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-neutral-400">{label}</span>
      <span className={`text-sm font-mono font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start justify-between py-0.5 gap-1">
      <span className="text-[11px] text-neutral-500 shrink-0">{label}</span>
      <span className="text-[11px] text-white font-medium text-right truncate">{value ?? <span className="text-neutral-600 italic">N/A</span>}</span>
    </div>
  );
}
