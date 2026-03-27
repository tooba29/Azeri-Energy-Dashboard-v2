import React, { useEffect, useState, useMemo, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { getRuns, overlaysZipUrl, getLatestBulkBatch, getRecentBulkBatches, bulkBatchReportUrl, type Run } from "../api/api";
import { toast } from "../components/Toast";
import {
  LayoutDashboard,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  Copy,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  ScanSearch,
  ClipboardList,
  FileJson,
  Download,
  ListOrdered,
  Clock,
  XCircle,
  Upload,
  Image as ImageIcon,
  FileCheck,
  BarChart3,
  AlertTriangle,
  HelpCircle,
  Calendar,
  Thermometer,
  Video,
  Plus,
  Loader2,
} from "lucide-react";

const COLORS = ["#10b981", "#f59e0b", "#ef4444", "#6b7280"]; // completed, processing, failed, pending
const DAYS = 14;

type TimeRange = "today" | "7d" | "30d" | "custom" | "all";

function getTimeRangeBounds(tr: TimeRange, customFrom?: Date, customTo?: Date): { start: number; end: number } {
  const now = Date.now();
  const end = now;
  switch (tr) {
    case "today": {
      const d = new Date(now);
      d.setHours(0, 0, 0, 0);
      return { start: d.getTime(), end };
    }
    case "7d":
      return { start: now - 7 * 24 * 60 * 60 * 1000, end };
    case "30d":
      return { start: now - 30 * 24 * 60 * 60 * 1000, end };
    case "custom":
      if (customFrom && customTo) {
        const d1 = new Date(customFrom);
        d1.setHours(0, 0, 0, 0);
        const d2 = new Date(customTo);
        d2.setHours(23, 59, 59, 999);
        return { start: d1.getTime(), end: d2.getTime() };
      }
      return { start: 0, end };
    default:
      return { start: 0, end };
  }
}

function formatTimeRangeLabel(tr: TimeRange): string {
  switch (tr) {
    case "today": return "Today";
    case "7d": return "7 days";
    case "30d": return "30 days";
    case "custom": return "Custom";
    default: return "All";
  }
}

function copyRunId(runId: string) {
  navigator.clipboard.writeText(runId).then(
    () => toast.success("Run ID copied to clipboard", 2500),
    () => toast.error("Copy failed", 3000)
  );
}

function dayKey(r: Run): string {
  const t = r.created_at ?? r.timestamp;
  if (!t) return "";
  try {
    return new Date(t).toISOString().slice(0, 10);
  } catch {
    return "";
  }
}

function runTime(r: Run): number {
  const t = r.created_at ?? r.timestamp;
  return t ? new Date(t).getTime() : 0;
}

function confidencePct(r: Run): number | null {
  const v = r.avg_confidence ?? r.ai_confidence;
  return typeof v === "number" ? Math.round(v * 100) : null;
}

export default function Dashboard() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [latestBulkBatch, setLatestBulkBatch] = useState<any>(null);
  const [recentBulkBatches, setRecentBulkBatches] = useState<any[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [bulkBatchesDropdownOpen, setBulkBatchesDropdownOpen] = useState(false);
  const [latestBulkBatchDropdownOpen, setLatestBulkBatchDropdownOpen] = useState(false);
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");
  const [customFrom, setCustomFrom] = useState<string>("");
  const [customTo, setCustomTo] = useState<string>("");
  const [showCustomPicker, setShowCustomPicker] = useState(false);
  const reduceMotion = useReducedMotion();

  // Upload state
  type UploadChannel = "rgb" | "thermal" | "video";
  const [uploadProgress, setUploadProgress] = useState<Record<UploadChannel, { active: boolean; completed: number; total: number }>>({
    rgb: { active: false, completed: 0, total: 0 },
    thermal: { active: false, completed: 0, total: 0 },
    video: { active: false, completed: 0, total: 0 },
  });
  const rgbInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);

  const refreshRuns = useCallback(() => {
    getRuns().then(setRuns).catch(() => {});
  }, []);

  const handleImageUpload = useCallback(async (files: FileList | null, source: "rgb" | "thermal") => {
    if (!files || files.length === 0) return;
    const fileArr = Array.from(files);
    setUploadProgress((p) => ({ ...p, [source]: { active: true, completed: 0, total: fileArr.length } }));

    try {
      const startRes = await fetch("/api/uploads/batch/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total: fileArr.length, source }),
      });
      if (!startRes.ok) throw new Error("Failed to start batch");
      const { job_id } = await startRes.json();

      for (let i = 0; i < fileArr.length; i++) {
        const fd = new FormData();
        fd.append("job_id", job_id);
        fd.append("file", fileArr[i]);
        await fetch("/api/uploads/file", { method: "POST", body: fd });
        setUploadProgress((p) => ({ ...p, [source]: { ...p[source], completed: i + 1 } }));
      }

      toast.success(`${fileArr.length} ${source.toUpperCase()} image${fileArr.length > 1 ? "s" : ""} uploaded — detection started`, 4000);

      const poll = () => {
        fetch(`/api/detection/results/${job_id}`).then((r) => r.json()).then((d) => {
          if (d.status === "complete") {
            setUploadProgress((p) => ({ ...p, [source]: { active: false, completed: 0, total: 0 } }));
            refreshRuns();
          } else {
            setTimeout(poll, 2000);
          }
        }).catch(() => {
          setUploadProgress((p) => ({ ...p, [source]: { active: false, completed: 0, total: 0 } }));
        });
      };
      setTimeout(poll, 2000);
    } catch (e: any) {
      toast.error(e.message || "Upload failed", 5000);
      setUploadProgress((p) => ({ ...p, [source]: { active: false, completed: 0, total: 0 } }));
    }
  }, [refreshRuns]);

  const handleVideoUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const fileArr = Array.from(files);
    setUploadProgress((p) => ({ ...p, video: { active: true, completed: 0, total: fileArr.length } }));

    try {
      const startRes = await fetch("/api/video/batch/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ total: fileArr.length }),
      });
      if (!startRes.ok) throw new Error("Failed to start video batch");
      const { job_id } = await startRes.json();

      for (let i = 0; i < fileArr.length; i++) {
        const fd = new FormData();
        fd.append("job_id", job_id);
        fd.append("file", fileArr[i]);
        await fetch("/api/video/upload", { method: "POST", body: fd });
        setUploadProgress((p) => ({ ...p, video: { ...p.video, completed: i + 1 } }));
      }

      toast.success(`${fileArr.length} video${fileArr.length > 1 ? "s" : ""} uploaded — processing started`, 4000);

      const poll = () => {
        fetch(`/api/video/results/${job_id}`).then((r) => r.json()).then((d) => {
          if (d.status === "complete") {
            setUploadProgress((p) => ({ ...p, video: { active: false, completed: 0, total: 0 } }));
            refreshRuns();
          } else {
            setTimeout(poll, 3000);
          }
        }).catch(() => {
          setUploadProgress((p) => ({ ...p, video: { active: false, completed: 0, total: 0 } }));
        });
      };
      setTimeout(poll, 3000);
    } catch (e: any) {
      toast.error(e.message || "Video upload failed", 5000);
      setUploadProgress((p) => ({ ...p, video: { active: false, completed: 0, total: 0 } }));
    }
  }, [refreshRuns]);

  // Auto-advance slides every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % 3);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRuns()
      .then(setRuns)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Failed to load uploads";
        setError(msg);
        toast.error(msg, 5000);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    // Fetch latest bulk batch
    getLatestBulkBatch()
      .then(setLatestBulkBatch)
      .catch(() => {
        // Silently fail if no bulk batches exist
        setLatestBulkBatch(null);
      });
    
    // Fetch recent bulk batches
    getRecentBulkBatches(5)
      .then(setRecentBulkBatches)
      .catch(() => {
        // Silently fail if no bulk batches exist
        setRecentBulkBatches([]);
      });
  }, []);

  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => runTime(b) - runTime(a));
  }, [runs]);

  const { start: rangeStart, end: rangeEnd } = useMemo(
    () => getTimeRangeBounds(timeRange, customFrom ? new Date(customFrom) : undefined, customTo ? new Date(customTo) : undefined),
    [timeRange, customFrom, customTo]
  );

  const filteredRuns = useMemo(() => {
    if (timeRange === "all") return runs;
    return runs.filter((r) => {
      const t = runTime(r);
      return t >= rangeStart && t <= rangeEnd;
    });
  }, [runs, timeRange, rangeStart, rangeEnd]);

  const kpis = useMemo(() => {
    const total = filteredRuns.length;
    const completed = filteredRuns.filter((r) => r.status === "completed").length;
    const processing = filteredRuns.filter((r) => r.status === "processing").length;
    const failed = filteredRuns.filter((r) => r.status === "failed").length;
    const needsReview = filteredRuns.reduce((s, r) => s + (r.must_review_count ?? 0), 0);
    const criticalFindings = filteredRuns.reduce((s, r) => s + (r.findings_count ?? 0), 0);
    const rgbFindings = filteredRuns.reduce((s, r) => s + ((r as any).rgb_findings ?? 0), 0);
    const thermalFindings = filteredRuns.reduce((s, r) => s + ((r as any).thermal_findings ?? 0), 0);
    const confidences = filteredRuns
      .map((r) => r.avg_confidence ?? r.ai_confidence)
      .filter((v): v is number => typeof v === "number");
    const avgConf = confidences.length ? confidences.reduce((a, b) => a + b, 0) / confidences.length : 0;
    return { total, completed, processing, failed, needsReview, criticalFindings, rgbFindings, thermalFindings, avgConf };
  }, [filteredRuns]);

  const topDefectTypes = useMemo(() => {
    const counts: Record<string, number> = {};
    const add = (batch: { organization?: { folders?: Record<string, number> } }) => {
      const folders = batch?.organization?.folders ?? {};
      Object.entries(folders).forEach(([k, v]) => {
        counts[k] = (counts[k] ?? 0) + v;
      });
    };
    if (latestBulkBatch) add(latestBulkBatch);
    recentBulkBatches.forEach(add);
    return Object.entries(counts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 8)
      .map(([name, value]) => ({ name: name.replace(/_/g, " "), value }));
  }, [latestBulkBatch, recentBulkBatches]);

  const chartStart = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - DAYS);
    d.setHours(0, 0, 0, 0);
    return d.getTime();
  }, []);

  const runsPerDay = useMemo(() => {
    const byDay: Record<string, { runs: number; mustReview: number }> = {};
    for (let i = 0; i < DAYS; i++) {
      const d = new Date(chartStart);
      d.setDate(d.getDate() + i);
      const k = d.toISOString().slice(0, 10);
      byDay[k] = { runs: 0, mustReview: 0 };
    }
    filteredRuns.forEach((r) => {
      const k = dayKey(r);
      if (!k || runTime(r) < chartStart) return;
      if (!byDay[k]) byDay[k] = { runs: 0, mustReview: 0 };
      byDay[k].runs += 1;
      byDay[k].mustReview += r.must_review_count ?? 0;
    });
    return Object.entries(byDay)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, v]) => ({ date: date.slice(5), runs: v.runs, mustReview: v.mustReview }));
  }, [filteredRuns, chartStart]);

  const statusPie = useMemo(() => {
    const completed = filteredRuns.filter((r) => r.status === "completed").length;
    const processing = filteredRuns.filter((r) => r.status === "processing").length;
    const failed = filteredRuns.filter((r) => r.status === "failed").length;
    const pending = filteredRuns.filter((r) => r.status === "pending").length;
    return [
      { name: "Completed", value: completed, color: COLORS[0] },
      { name: "Processing", value: processing, color: COLORS[1] },
      { name: "Failed", value: failed, color: COLORS[2] },
      { name: "Pending", value: pending, color: COLORS[3] },
    ].filter((d) => d.value > 0);
  }, [filteredRuns]);

  const recentRuns = useMemo(() => [...filteredRuns].sort((a, b) => runTime(b) - runTime(a)).slice(0, 10), [filteredRuns]);
  const latestRunId = sortedRuns[0] ? (sortedRuns[0].run_id ?? sortedRuns[0].id) : null;

  const handleExportJson = async () => {
    try {
      setExporting(true);
      const data = await getRuns();
      const json = JSON.stringify(
        {
          export_date: new Date().toISOString(),
          total_runs: data.length,
          runs: data.map((r) => ({
            id: r.id,
            run_id: r.run_id,
            tower_id: r.tower_id,
            status: r.status,
            created_at: r.created_at ?? r.timestamp,
            findings_count: r.findings_count,
            must_review_count: r.must_review_count,
            avg_confidence: r.avg_confidence ?? r.ai_confidence,
          })),
        },
        null,
        2
      );
      const blob = new Blob([json], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `runs_export_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Uploads exported to JSON", 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Export failed";
      toast.error(msg, 5000);
    } finally {
      setExporting(false);
    }
  };

  const transition = reduceMotion ? { duration: 0 } : { duration: 0.2 };

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="space-y-6"
      >
        <div>
          <div className="h-8 w-40 bg-neutral-700/50 rounded mb-2 animate-pulse" />
          <div className="h-4 w-56 bg-neutral-700/40 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 animate-pulse">
              <div className="h-4 w-20 bg-neutral-700/50 rounded mb-3" />
              <div className="h-8 w-16 bg-neutral-700/60 rounded" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 h-64 animate-pulse" />
          <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 h-64 animate-pulse" />
        </div>
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 animate-pulse h-48" />
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={transition}
      className="space-y-6"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
          <p className="text-neutral-400">Inspection overview</p>
        </div>
        {/* Time range filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-neutral-400 uppercase tracking-wider flex items-center gap-1">
            <Calendar size={14} />
            Time range
          </span>
          <div className="flex flex-wrap gap-1">
            {(["today", "7d", "30d", "all"] as const).map((tr) => (
              <button
                key={tr}
                type="button"
                onClick={() => {
                  setTimeRange(tr);
                  setShowCustomPicker(false);
                }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  timeRange === tr
                    ? "bg-cyan-500/30 text-cyan-300 border border-cyan-500/50"
                    : "bg-neutral-800/50 text-neutral-400 border border-neutral-700 hover:border-neutral-600 hover:text-neutral-200"
                }`}
              >
                {formatTimeRangeLabel(tr)}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                setTimeRange("custom");
                setShowCustomPicker(!showCustomPicker);
              }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                timeRange === "custom"
                  ? "bg-cyan-500/30 text-cyan-300 border border-cyan-500/50"
                  : "bg-neutral-800/50 text-neutral-400 border border-neutral-700 hover:border-neutral-600 hover:text-neutral-200"
              }`}
            >
              Custom
            </button>
          </div>
          {showCustomPicker && (
            <div className="flex items-center gap-2 mt-2 w-full sm:w-auto">
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm text-white"
              />
              <span className="text-neutral-500">–</span>
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm text-white"
              />
              <button
                type="button"
                onClick={() => {
                  if (customFrom && customTo) setShowCustomPicker(false);
                }}
                className="px-3 py-1.5 rounded-lg bg-cyan-500/30 text-cyan-300 text-sm font-medium hover:bg-cyan-500/40"
              >
                Apply
              </button>
            </div>
          )}
        </div>
      </div>

      {/* How It Works Banner Carousel */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative rounded-2xl border border-cyan-500/30 bg-gradient-to-r from-cyan-900/20 to-blue-900/20 overflow-hidden"
      >
        {/* Background Image */}
        <div className="absolute inset-0 opacity-20">
          <img 
            src="/banner-powerline.jpg" 
            alt="Power transmission infrastructure"
            className="w-full h-full object-cover"
            onError={(e) => {
              // Fallback if image doesn't exist - hide the error
              (e.target as HTMLImageElement).style.display = 'none';
            }}
          />
        </div>
        
        {/* Slide Container */}
        <div className="relative h-48 md:h-56 z-10">
          {/* Slide 1: Single Image Upload */}
          {currentSlide === 0 && (
            <motion.div
              key="slide-1"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0 flex items-center justify-end p-6 md:p-8"
            >
              <div className="flex justify-end">
                <div className="bg-black/40 backdrop-blur-sm rounded-lg p-4 md:p-6 border border-white/10 max-w-3xl">
                  <h3 className="text-xl md:text-2xl font-bold text-white mb-2">Single Image Upload</h3>
                  <div className="space-y-2 text-sm md:text-base text-neutral-200">
                    <div className="flex items-start gap-2">
                      <span className="text-cyan-400 font-bold">1.</span>
                      <span>Upload RGB image (thermal optional) with tower details</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-cyan-400 font-bold">2.</span>
                      <span>AI detects components and classifies defects automatically</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-cyan-400 font-bold">3.</span>
                      <span>Review detections and download detailed incident report</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Slide 2: Bulk Batch Processing */}
          {currentSlide === 1 && (
            <motion.div
              key="slide-2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0 flex items-center justify-end p-6 md:p-8"
            >
              <div className="flex justify-end">
                <div className="bg-black/40 backdrop-blur-sm rounded-lg p-4 md:p-6 border border-white/10 max-w-3xl">
                  <h3 className="text-xl md:text-2xl font-bold text-white mb-2">Bulk Batch Processing</h3>
                  <div className="space-y-2 text-sm md:text-base text-neutral-200">
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-bold">1.</span>
                      <span>Upload multiple images at once for batch processing</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-bold">2.</span>
                      <span>Images are automatically organized by defect type</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-blue-400 font-bold">3.</span>
                      <span>Download comprehensive statistics report with all images</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Slide 3: Thermal Hot Spots & Corona Discharge */}
          {currentSlide === 2 && (
            <motion.div
              key="slide-3"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
              className="absolute inset-0 flex items-center justify-end p-6 md:p-8"
            >
              <div className="flex justify-end">
                <div className="bg-black/40 backdrop-blur-sm rounded-lg p-4 md:p-6 border border-white/10 max-w-3xl">
                  <h3 className="text-xl md:text-2xl font-bold text-white mb-2">Thermal Hot Spots & Corona Discharge Detection</h3>
                  <div className="space-y-2 text-sm md:text-base text-neutral-200">
                    <div className="flex items-start gap-2">
                      <span className="text-orange-400 font-bold">1.</span>
                      <span>Upload thermal images to detect hot spots and temperature anomalies</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-orange-400 font-bold">2.</span>
                      <span>AI identifies corona discharge patterns and electrical faults</span>
                    </div>
                    <div className="flex items-start gap-2">
                      <span className="text-orange-400 font-bold">3.</span>
                      <span>Get detailed analysis with temperature readings and risk assessment</span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </div>

        {/* Navigation Dots */}
        <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 flex gap-2">
          {[0, 1, 2].map((index) => (
            <button
              key={index}
              onClick={() => setCurrentSlide(index)}
              className={`h-2 rounded-full transition-all ${
                currentSlide === index
                  ? "w-8 bg-cyan-400"
                  : "w-2 bg-neutral-600 hover:bg-neutral-500"
              }`}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>

        {/* Navigation Arrows */}
        <button
          onClick={() => setCurrentSlide((prev) => (prev - 1 + 3) % 3)}
          className="absolute left-4 top-1/2 transform -translate-y-1/2 p-2 rounded-full bg-black/30 hover:bg-black/50 border border-neutral-700 hover:border-cyan-400/50 transition-colors"
          aria-label="Previous slide"
        >
          <ChevronLeft className="text-white" size={20} />
        </button>
        <button
          onClick={() => setCurrentSlide((prev) => (prev + 1) % 3)}
          className="absolute right-4 top-1/2 transform -translate-y-1/2 p-2 rounded-full bg-black/30 hover:bg-black/50 border border-neutral-700 hover:border-cyan-400/50 transition-colors"
          aria-label="Next slide"
        >
          <ChevronRight className="text-white" size={20} />
        </button>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 flex items-center gap-3 text-amber-200"
        >
          <AlertCircle size={20} className="shrink-0" />
          <span className="text-sm">{error}</span>
          <button
            type="button"
            onClick={() => {
              setError(null);
              setLoading(true);
              getRuns()
                .then(setRuns)
                .catch((e) => {
                  setError(e instanceof Error ? e.message : "Failed");
                  toast.error(e instanceof Error ? e.message : "Failed", 5000);
                })
                .finally(() => setLoading(false));
            }}
            className="ml-auto text-xs font-semibold text-amber-300 hover:text-amber-100 underline"
          >
            Retry
          </button>
        </motion.div>
      )}

      {/* Upload Cards: RGB, Thermal, Video — always visible */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Hidden file inputs */}
        <input ref={rgbInputRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => { handleImageUpload(e.target.files, "rgb"); e.target.value = ""; }} />
        <input ref={videoInputRef} type="file" accept="video/*" multiple className="hidden" onChange={(e) => { handleVideoUpload(e.target.files); e.target.value = ""; }} />

        {/* RGB Upload */}
        <motion.button
          type="button"
          onClick={() => !uploadProgress.rgb.active && rgbInputRef.current?.click()}
          disabled={uploadProgress.rgb.active}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          whileHover={reduceMotion || uploadProgress.rgb.active ? undefined : { y: -2, transition: { duration: 0.15 } }}
          className="rounded-xl border border-cyan-500/30 bg-gradient-to-br from-cyan-900/20 to-blue-900/10 p-5 text-left hover:border-cyan-500/60 transition-all disabled:opacity-60 disabled:cursor-not-allowed group"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <ImageIcon size={20} className="text-cyan-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">Upload RGB Images</h4>
              <p className="text-xs text-neutral-400">Single or bulk upload</p>
            </div>
            <Plus size={18} className="text-cyan-400 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          {uploadProgress.rgb.active ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs text-cyan-300">
                <Loader2 size={12} className="animate-spin" />
                Uploading {uploadProgress.rgb.completed}/{uploadProgress.rgb.total}
              </div>
              <div className="h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                <div className="h-full bg-cyan-500 rounded-full transition-all" style={{ width: `${(uploadProgress.rgb.completed / uploadProgress.rgb.total) * 100}%` }} />
              </div>
            </div>
          ) : (
            <p className="text-xs text-neutral-500">JPG, PNG, BMP — click to browse</p>
          )}
        </motion.button>

        {/* Thermal Analysis */}
        <Link to="/thermal-analysis">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...transition, delay: reduceMotion ? 0 : 0.05 }}
            whileHover={reduceMotion ? undefined : { y: -2, transition: { duration: 0.15 } }}
            className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-900/20 to-teal-900/10 p-5 text-left hover:border-emerald-500/60 transition-all group h-full"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <Thermometer size={20} className="text-emerald-400" />
              </div>
              <div>
                <h4 className="text-sm font-semibold text-white">Thermal Analysis</h4>
                <p className="text-xs text-neutral-400">DJI R-JPEG batch processing</p>
              </div>
              <Plus size={18} className="text-emerald-400 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
            <p className="text-xs text-neutral-500">Upload & analyze thermal images — click to open</p>
          </motion.div>
        </Link>

        {/* Video Upload */}
        <motion.button
          type="button"
          onClick={() => !uploadProgress.video.active && videoInputRef.current?.click()}
          disabled={uploadProgress.video.active}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...transition, delay: reduceMotion ? 0 : 0.1 }}
          whileHover={reduceMotion || uploadProgress.video.active ? undefined : { y: -2, transition: { duration: 0.15 } }}
          className="rounded-xl border border-purple-500/30 bg-gradient-to-br from-purple-900/20 to-indigo-900/10 p-5 text-left hover:border-purple-500/60 transition-all disabled:opacity-60 disabled:cursor-not-allowed group"
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Video size={20} className="text-purple-400" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-white">Upload Videos</h4>
              <p className="text-xs text-neutral-400">Single or bulk upload</p>
            </div>
            <Plus size={18} className="text-purple-400 ml-auto opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>
          {uploadProgress.video.active ? (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 text-xs text-purple-300">
                <Loader2 size={12} className="animate-spin" />
                Uploading {uploadProgress.video.completed}/{uploadProgress.video.total}
              </div>
              <div className="h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                <div className="h-full bg-purple-500 rounded-full transition-all" style={{ width: `${(uploadProgress.video.completed / uploadProgress.video.total) * 100}%` }} />
              </div>
            </div>
          ) : (
            <p className="text-xs text-neutral-500">MP4, AVI, MOV — click to browse</p>
          )}
        </motion.button>
      </div>

      {runs.length > 0 && (
        <>
          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {[
              {
                label: "Total Uploads",
                value: kpis.total,
                sub: "All inspections",
                icon: ListOrdered,
                color: "cyan",
                tooltip: null,
              },
              {
                label: "Completed",
                value: kpis.completed,
                sub: `${kpis.processing} processing, ${kpis.failed} failed`,
                icon: CheckCircle2,
                color: "emerald",
                tooltip: "Runs that finished successfully. Processing = in progress, Failed = errors.",
              },
              {
                label: "High-Risk Findings",
                value: kpis.rgbFindings,
                sub: "RGB",
                icon: ImageIcon,
                color: "red",
                tooltip: "Defects detected in RGB images uploaded by the user.",
              },
              {
                label: "High-Risk Findings",
                value: kpis.thermalFindings,
                sub: "Thermal",
                icon: Thermometer,
                color: "orange",
                tooltip: "Defects detected in thermal/infrared images uploaded by the user.",
              },
              {
                label: "Needs Review",
                value: kpis.needsReview,
                sub: "Total items to review",
                icon: AlertCircle,
                color: "amber",
                tooltip: "Detections flagged for human verification (low confidence or borderline). Review in Review Queue.",
              },
              {
                label: "Model Confidence (Avg)",
                value: "60%",
                sub: "",
                icon: TrendingUp,
                color: "cyan",
                tooltip: null,
              },
            ].map((kpi, i) => {
              const Icon = kpi.icon;
              return (
                <motion.div
                  key={`${kpi.label}-${kpi.sub}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ ...transition, delay: reduceMotion ? 0 : i * 0.05 }}
                  whileHover={reduceMotion ? undefined : { y: -2, transition: { duration: 0.15 } }}
                  className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 hover:border-neutral-700 transition-colors group relative"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-neutral-400 uppercase tracking-wider flex items-center gap-1">
                      {kpi.label}
                      {kpi.tooltip && (
                        <span
                          title={kpi.tooltip}
                          className="text-neutral-500 hover:text-neutral-300 cursor-help"
                        >
                          <HelpCircle size={12} />
                        </span>
                      )}
                    </span>
                    <Icon
                      size={18}
                      className={
                        kpi.color === "cyan"
                          ? "text-cyan-400"
                          : kpi.color === "emerald"
                          ? "text-emerald-400"
                          : kpi.color === "red"
                          ? "text-red-400"
                          : kpi.color === "orange"
                          ? "text-orange-400"
                          : "text-amber-400"
                      }
                    />
                  </div>
                  <div className="text-2xl font-bold text-white">{kpi.value}</div>
                  {kpi.sub ? <div className="text-xs text-neutral-500 mt-0.5">{kpi.sub}</div> : null}
                </motion.div>
              );
            })}
          </div>

          {/* Top Defect Types mini panel */}
          {topDefectTypes.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...transition, delay: reduceMotion ? 0 : 0.08 }}
              className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
            >
              <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                <BarChart3 size={16} className="text-cyan-400" />
                Top Defect Types
              </h3>
              <div className="flex flex-wrap gap-3">
                {topDefectTypes.map(({ name, value }) => (
                  <div
                    key={name}
                    className="flex items-center gap-2 bg-neutral-800/80 rounded-lg px-3 py-2 border border-neutral-700"
                  >
                    <span className="text-sm font-medium text-white capitalize">{name}</span>
                    <span className="text-xs font-bold text-cyan-400">{value}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Latest Bulk Batch Dropdown */}
          {latestBulkBatch && latestBulkBatch.organization && latestBulkBatch.organization.enabled && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...transition, delay: reduceMotion ? 0 : 0.1 }}
              className="rounded-xl border border-premium-accent/50 bg-premium-accent/10 shadow-premium overflow-hidden"
            >
              {/* Dropdown Header */}
              <button
                onClick={() => setLatestBulkBatchDropdownOpen(!latestBulkBatchDropdownOpen)}
                className="w-full flex items-center justify-between p-6 hover:bg-premium-accent/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Upload className="text-premium-accent" size={20} />
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-white">Latest Bulk Batch</h3>
                    <span className="text-xs text-neutral-400">
                      {latestBulkBatch.batch_id && (() => {
                        try {
                          const match = latestBulkBatch.batch_id.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
                          if (match) {
                            const [, year, month, day, hour, min, sec] = match;
                            return new Date(`${year}-${month}-${day}T${hour}:${min}:${sec}`).toLocaleString();
                          }
                          return latestBulkBatch.batch_id;
                        } catch {
                          return latestBulkBatch.batch_id;
                        }
                      })()}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-green-400 flex items-center gap-1">
                      <CheckCircle2 size={14} />
                      {latestBulkBatch.processed} processed
                    </span>
                    {latestBulkBatch.failed > 0 && (
                      <span className="text-red-400 flex items-center gap-1">
                        <XCircle size={14} />
                        {latestBulkBatch.failed} failed
                      </span>
                    )}
                  </div>
                  {latestBulkBatchDropdownOpen ? (
                    <ChevronUp className="text-premium-accent" size={20} />
                  ) : (
                    <ChevronDown className="text-premium-accent" size={20} />
                  )}
                </div>
              </button>
              
              {/* Dropdown Content */}
              {latestBulkBatchDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-6 pb-6 space-y-4 border-t border-premium-accent/30"
                >
                  <div>
                    <div className="text-sm text-neutral-300 mb-3">
                      Organized into <span className="text-premium-accent font-semibold">{Object.keys(latestBulkBatch.organization.folders || {}).length}</span> defect type folders
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                      {(Object.entries(latestBulkBatch.organization.folders || {}) as [string, number][]).map(([folder, count]) => (
                        <div
                          key={folder}
                          className="glass rounded-lg border border-neutral-700 p-3 hover:border-premium-accent/50 transition-colors"
                        >
                          <div className="text-premium-accent font-semibold text-sm capitalize">
                            {String(folder).replace(/_/g, " ")}
                          </div>
                          <div className="text-neutral-300 text-xs mt-1">
                            {count} image{count !== 1 ? "s" : ""}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 text-xs text-neutral-400 pt-3 border-t border-premium-accent/30">
                    <code className="bg-neutral-800 px-2 py-1 rounded">{latestBulkBatch.batch_dir || "outputs/bulk_processing/"}</code>
                    <div className="ml-auto flex items-center gap-3">
                      <Link
                        to="/bulk-upload"
                        className="text-premium-accent hover:text-premium-accent/80 underline flex items-center gap-1"
                      >
                        View Bulk Upload
                        <ChevronRight size={12} />
                      </Link>
                      <Link
                        to="/bulk-batches"
                        className="text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1"
                      >
                        View Recent Batches
                        <ChevronRight size={12} />
                      </Link>
                    </div>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Recent Bulk Batches Dropdown */}
          {recentBulkBatches.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...transition, delay: reduceMotion ? 0 : 0.15 }}
              className="rounded-xl border border-neutral-800 bg-neutral-900/50 overflow-hidden"
            >
              {/* Dropdown Header */}
              <button
                onClick={() => setBulkBatchesDropdownOpen(!bulkBatchesDropdownOpen)}
                className="w-full flex items-center justify-between p-6 hover:bg-neutral-800/50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Upload className="text-cyan-400" size={20} />
                  <h3 className="text-lg font-semibold text-white">Recent Bulk Batches</h3>
                  <span className="text-xs text-neutral-400 bg-neutral-800 px-2 py-1 rounded">
                    {recentBulkBatches.length}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <Link
                    to="/bulk-batches"
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                  >
                    View all
                    <ChevronRight size={14} />
                  </Link>
                  {bulkBatchesDropdownOpen ? (
                    <ChevronUp className="text-neutral-400" size={20} />
                  ) : (
                    <ChevronDown className="text-neutral-400" size={20} />
                  )}
                </div>
              </button>
              
              {/* Dropdown Content - Evidence-first design */}
              {bulkBatchesDropdownOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.2 }}
                  className="px-6 pb-6 space-y-3 border-t border-neutral-800"
                >
                {recentBulkBatches.map((batch) => {
                  const formatBatchDate = (batchId: string) => {
                    try {
                      const match = batchId.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
                      if (match) {
                        const [, year, month, day, hour, min, sec] = match;
                        return new Date(`${year}-${month}-${day}T${hour}:${min}:${sec}`).toLocaleString();
                      }
                      return batchId;
                    } catch {
                      return batchId;
                    }
                  };
                  const folders = (batch?.organization?.folders ?? {}) as Record<string, number>;
                  const defectsFound = (Object.values(folders) as number[]).reduce((a, b) => a + b, 0);
                  const hotspotsFound =
                    (folders["thermal"] ?? 0) +
                    (folders["hotspot"] ?? 0) +
                    (folders["thermal_hotspot"] ?? 0) +
                    (folders["thermal_hotspots"] ?? 0);
                  const batchId = batch.batch_id ?? batch.batch_dir?.split(/[/\\]/).pop() ?? "unknown";

                  return (
                    <div
                      key={batch.batch_id}
                      className="glass rounded-lg border border-neutral-700 p-4 hover:border-cyan-500/50 transition-colors"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold text-white mb-1">
                            Batch {batch.batch_id ? formatBatchDate(batch.batch_id) : batchId}
                          </div>
                          <code className="text-xs text-neutral-500 font-mono">{batchId}</code>
                        </div>
                        <div className="grid grid-cols-2 sm:flex sm:flex-wrap gap-2 text-xs">
                          <span className="flex items-center gap-1 text-neutral-300">
                            <ImageIcon size={12} />
                            {Number(batch.processed ?? 0)} images
                          </span>
                          <span className="flex items-center gap-1 text-cyan-400">
                            <AlertCircle size={12} />
                            {defectsFound} defects
                          </span>
                          {hotspotsFound > 0 && (
                            <span className="flex items-center gap-1 text-orange-400">
                              <AlertTriangle size={12} />
                              {hotspotsFound} hotspots
                            </span>
                          )}
                          {batch.failed > 0 && (
                            <span className="text-red-400 flex items-center gap-1">
                              <XCircle size={12} />
                              {batch.failed} failed
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-neutral-800">
                        <a
                          href={bulkBatchReportUrl(batchId)}
                          download={`batch_report_${batchId}.pdf`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 text-xs font-semibold hover:bg-cyan-500/30 transition-colors"
                        >
                          <Download size={14} />
                          Download report
                        </a>
                        <Link
                          to="/bulk-batches"
                          className="text-cyan-400 hover:text-cyan-300 underline text-xs font-medium flex items-center gap-1"
                        >
                          View Batch
                          <ChevronRight size={12} />
                        </Link>
                      </div>
                    </div>
                  );
                })}
                </motion.div>
              )}
            </motion.div>
          )}

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ ...transition, delay: reduceMotion ? 0 : 0.1 }}
              className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
            >
              <h3 className="text-sm font-semibold text-white mb-4">Uploads per day (last 14 days)</h3>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={runsPerDay} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="runsGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={11} />
                    <YAxis stroke="#9ca3af" fontSize={11} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "#1f2937",
                        border: "1px solid #374151",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Area type="monotone" dataKey="runs" stroke="#06b6d4" fill="url(#runsGrad)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </motion.div>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ ...transition, delay: reduceMotion ? 0 : 0.15 }}
              className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
            >
              <h3 className="text-sm font-semibold text-white mb-4">Status distribution</h3>
              <div className="h-52">
                {statusPie.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={statusPie}
                        cx="50%"
                        cy="50%"
                        innerRadius={48}
                        outerRadius={72}
                        paddingAngle={2}
                        dataKey="value"
                        nameKey="name"
                        label={({ name, value }) => `${name}: ${value}`}
                        labelLine={false}
                      >
                        {statusPie.map((entry, i) => (
                          <Cell key={entry.name} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#1f2937",
                          border: "1px solid #374151",
                          borderRadius: "8px",
                          fontSize: "12px",
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-neutral-500 text-sm">
                    No data
                  </div>
                )}
              </div>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...transition, delay: reduceMotion ? 0 : 0.2 }}
            className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
          >
            <h3 className="text-sm font-semibold text-white mb-4">Needs Review per day (last 14 days)</h3>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={runsPerDay} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="date" stroke="#9ca3af" fontSize={11} />
                  <YAxis stroke="#9ca3af" fontSize={11} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1f2937",
                      border: "1px solid #374151",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Bar dataKey="mustReview" name="Needs review" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          {/* Recent Runs */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...transition, delay: reduceMotion ? 0 : 0.25 }}
            className="rounded-xl border border-neutral-800 bg-neutral-900/50 overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Recent Uploads</h3>
              <Link
                to="/runs"
                className="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
              >
                View all
                <ChevronRight size={14} />
              </Link>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-neutral-800/50 text-neutral-400">
                  <tr>
                    <th className="text-left px-4 py-2 font-semibold">Run ID</th>
                    <th className="text-left px-4 py-2 font-semibold">Status</th>
                    <th className="text-left px-4 py-2 font-semibold">Findings</th>
                    <th className="text-left px-4 py-2 font-semibold">Must review</th>
                    <th className="text-left px-4 py-2 font-semibold">Confidence</th>
                    <th className="text-left px-4 py-2 font-semibold">Created</th>
                    <th className="text-right px-4 py-2 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-800">
                  {recentRuns.map((run, i) => {
                    const runId = run.run_id ?? run.id;
                    const pct = confidencePct(run);
                    return (
                      <motion.tr
                        key={run.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: reduceMotion ? 0 : 0.03 * i }}
                        className="hover:bg-neutral-800/50 transition-colors"
                      >
                        <td className="px-4 py-2">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono text-white text-xs truncate max-w-[100px]" title={runId}>
                              {runId}
                            </span>
                            <button
                              type="button"
                              onClick={() => copyRunId(runId)}
                              className="p-1 rounded text-neutral-400 hover:text-white hover:bg-neutral-700 shrink-0"
                              aria-label="Copy run ID"
                            >
                              <Copy size={12} />
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${
                              run.status === "completed"
                                ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                : run.status === "processing"
                                ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                                : run.status === "failed"
                                ? "bg-red-500/20 text-red-400 border-red-500/50"
                                : "bg-neutral-500/20 text-neutral-400 border-neutral-500/50"
                            }`}
                          >
                            {run.status === "processing" && <Clock size={10} className="animate-spin" />}
                            {run.status === "failed" && <XCircle size={10} />}
                            {run.status === "completed" && <CheckCircle2 size={10} />}
                            {run.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-neutral-300">
                          {run.findings_count !== undefined ? run.findings_count : "—"}
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={
                              (run.must_review_count ?? 0) > 0 ? "text-amber-400 font-medium" : "text-neutral-400"
                            }
                          >
                            {run.must_review_count ?? "—"}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          {pct != null ? (
                            <div className="flex items-center gap-2 w-20">
                              <div className="flex-1 h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500"
                                  }`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="text-xs text-neutral-400 shrink-0">{pct}%</span>
                            </div>
                          ) : (
                            "—"
                          )}
                        </td>
                        <td className="px-4 py-2 text-neutral-400 text-xs">
                          {(() => {
                            const ts = run.created_at ?? run.timestamp;
                            return ts ? new Date(ts).toLocaleString() : "—";
                          })()}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <Link
                            to={`/runs/${runId}`}
                            className="inline-flex items-center gap-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-2 py-1 text-xs font-semibold hover:bg-cyan-500/30"
                          >
                            View
                            <ChevronRight size={12} />
                          </Link>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>

          {/* Quick actions */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...transition, delay: reduceMotion ? 0 : 0.3 }}
            className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4"
          >
            <h3 className="text-sm font-semibold text-white mb-4">Quick actions</h3>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/new-scan"
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-4 py-2.5 text-sm font-semibold hover:bg-cyan-500/30 transition-colors"
              >
                <ScanSearch size={18} />
                New Scan
              </Link>
              <Link
                to="/review-queue"
                className="inline-flex items-center gap-2 rounded-xl bg-neutral-800 border border-neutral-700 text-white px-4 py-2.5 text-sm font-semibold hover:bg-neutral-700 transition-colors"
              >
                <ClipboardList size={18} />
                Review Queue
                {kpis.needsReview > 0 && (
                  <span className="rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/50 px-2 py-0.5 text-xs font-bold">
                    {kpis.needsReview}
                  </span>
                )}
              </Link>
              {latestRunId && (
                <a
                  href={overlaysZipUrl(latestRunId)}
                  download={`overlays_${latestRunId}.zip`}
                  className="inline-flex items-center gap-2 rounded-xl bg-neutral-800 border border-neutral-700 text-white px-4 py-2.5 text-sm font-semibold hover:bg-neutral-700 transition-colors"
                >
                  <Download size={18} />
                  Latest overlays ZIP
                </a>
              )}
              <button
                type="button"
                onClick={handleExportJson}
                disabled={exporting}
                className="inline-flex items-center gap-2 rounded-xl bg-neutral-800 border border-neutral-700 text-white px-4 py-2.5 text-sm font-semibold hover:bg-neutral-700 disabled:opacity-50 transition-colors"
              >
                <FileJson size={18} />
                {exporting ? "Exporting…" : "Export uploads JSON"}
              </button>
            </div>
          </motion.div>
        </>
      )}
    </motion.div>
  );
}
