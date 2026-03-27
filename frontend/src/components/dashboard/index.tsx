import React, { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { getRuns, getLatestBulkBatch, getRecentBulkBatches, bulkBatchReportUrl, type Run } from "../../api/api";
import { toast } from "../Toast";
import StatsCards from "../Common/statsCards";
import DashboardCharts from "./charts";
import DashboardRecent from "./recent";
import {
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  Download,
  ListOrdered,
  XCircle,
  Upload,
  Image as ImageIcon,
  BarChart3,
  AlertTriangle,
  Thermometer,
  Video,
} from "lucide-react";

const COLORS = ["#10b981", "#f59e0b", "#ef4444", "#6b7280"]; // completed, processing, failed, pending
const DAYS = 14;

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

export default function DashboardHome() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestBulkBatch, setLatestBulkBatch] = useState<any>(null);
  const [recentBulkBatches, setRecentBulkBatches] = useState<any[]>([]);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [bulkBatchesDropdownOpen, setBulkBatchesDropdownOpen] = useState(false);
  const [latestBulkBatchDropdownOpen, setLatestBulkBatchDropdownOpen] = useState(false);
  const reduceMotion = useReducedMotion();

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

  const filteredRuns = runs;

  const kpis = useMemo(() => {
    const total = filteredRuns.length;
    const completed = filteredRuns.filter((r) => r.status === "completed").length;
    const processing = filteredRuns.filter((r) => r.status === "processing").length;
    const failed = filteredRuns.filter((r) => r.status === "failed").length;
    const needsReview = filteredRuns.reduce((s, r) => s + (r.must_review_count ?? 0), 0);
    return { total, completed, processing, failed, needsReview };
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
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/ai-detection?tab=video"
            title="Video defect detection — open AI Detection"
            className="inline-flex items-center gap-1.5 rounded-lg border border-purple-500/40 bg-purple-500/15 px-2.5 py-1.5 text-xs font-semibold text-purple-200 hover:bg-purple-500/25 hover:border-purple-500/60 transition-colors"
          >
            <Video size={14} className="shrink-0 text-purple-400" />
            Upload video
          </Link>
          <Link
            to="/ai-detection?tab=thermal"
            title="Thermal analysis — DJI R-JPEG batch processing"
            className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1.5 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 hover:border-emerald-500/60 transition-colors"
          >
            <Thermometer size={14} className="shrink-0 text-emerald-400" />
            Thermal analysis
          </Link>
          <Link
            to="/ai-detection?tab=rgb"
            title="RGB defect detection — open AI Detection"
            className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-500/40 bg-cyan-500/15 px-2.5 py-1.5 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/25 hover:border-cyan-500/60 transition-colors"
          >
            <ImageIcon size={14} className="shrink-0 text-cyan-400" />
            RGB image
          </Link>
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

      {runs.length > 0 && (
        <>
          <StatsCards
            transition={transition}
            reduceMotion={reduceMotion}
            items={[
              {
                heading: "Uploads",
                value: kpis.total,
                subheading: "All inspections",
                icon: ListOrdered,
                color: "cyan",
                tooltip: null,
              },
              {
                heading: "Completed",
                value: kpis.completed,
                subheading: `${kpis.processing} processing, ${kpis.failed} failed`,
                icon: CheckCircle2,
                color: "emerald",
                tooltip: "Runs that finished successfully. Processing = in progress, Failed = errors.",
              },
              {
                heading: "Needs Review",
                value: kpis.needsReview,
                subheading: "Total items to review",
                icon: AlertCircle,
                color: "amber",
                tooltip: "Detections flagged for human verification (low confidence or borderline). Review in Review Queue.",
              },
              {
                heading: "Model Precision Confidence",
                value: "96%",
                icon: TrendingUp,
                color: "cyan",
                tooltip: null,
              },
            ]}
          />

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

          <DashboardCharts
            runsPerDay={runsPerDay}
            statusPie={statusPie}
            transition={transition}
            reduceMotion={reduceMotion}
          />

          <DashboardRecent recentRuns={recentRuns} transition={transition} reduceMotion={reduceMotion} />
        </>
      )}
    </motion.div>
  );
}
