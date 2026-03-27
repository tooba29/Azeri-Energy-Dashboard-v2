import React, { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { getRecentVideos, videoFrameUrl, type VideoResult } from "../../api/api";
import { toast } from "../Toast";
import MediaUploadBox from "../Common/upload";
import {
  Video,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  ChevronLeft,
  ChevronRight,
  SlidersHorizontal,
  Trash2,
  Layers,
  Play,
  Upload,
  AlertTriangle,
  Calendar,
  BarChart3,
  Eye,
  Film,
} from "lucide-react";
import { io, type Socket } from "socket.io-client";

const POLL_MS = 3000;

type VideoCard = {
  localId: string;
  fileId?: string;
  filename: string;
  localPreview?: string;
  status: "pending" | "uploading" | "queued" | "processing" | "complete" | "error";
  progress: number;
  progressLabel: string;
  thumbUrl?: string;
  videoUrl?: string;
  totalDetections: number;
  framesAnalyzed: number;
  duration: number;
  fps: number;
  avgConfidence: number;
  maxConfidence: number;
  error?: string;
};

type LocalVideo = {
  id: string;
  file: File;
  preview: string;
};

let _vid = 0;
const uid = () => `v_${++_vid}_${Date.now()}`;

export default function VideoAnalysis() {
  const reduceMotion = useReducedMotion();
  const pageTransition = reduceMotion ? { duration: 0 } : { duration: 0.2 };
  const uploadSectionRef = useRef<HTMLDivElement>(null);

  const [localVideos, setLocalVideos] = useState<LocalVideo[]>([]);
  const [cards, setCards] = useState<Map<string, VideoCard>>(new Map());
  const [jobId, setJobId] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [batchProgress, setBatchProgress] = useState({ completed: 0, total: 0 });
  const [config, setConfig] = useState({ confidence: 0.25, sliceSize: 640, overlap: 0.2, frameInterval: 1 });
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const [videos, setVideos] = useState<VideoResult[]>([]);
  const [videosLoading, setVideosLoading] = useState(true);
  const [videosError, setVideosError] = useState<string | null>(null);
  const [expandedVideos, setExpandedVideos] = useState<Set<string>>(new Set());

  const socketRef = useRef<Socket | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);
  const nameToKeyRef = useRef<Map<string, string>>(new Map());

  const totalVideos = localVideos.length;
  const canStart = totalVideos > 0 && !processing;

  useEffect(() => { jobIdRef.current = jobId; }, [jobId]);
  useEffect(() => {
    return () => {
      socketRef.current?.disconnect();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    setVideosLoading(true);
    setVideosError(null);
    getRecentVideos(50)
      .then(setVideos)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Failed to load videos";
        setVideosError(msg);
        toast.error(msg, 5000);
      })
      .finally(() => setVideosLoading(false));
  }, []);

  const toggleVideo = (videoId: string) => {
    setExpandedVideos((prev) => {
      const next = new Set(prev);
      if (next.has(videoId)) next.delete(videoId);
      else next.add(videoId);
      return next;
    });
  };

  const formatVideoDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const scrollToUpload = () => uploadSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const updateCard = useCallback((key: string, patch: Partial<VideoCard>) => {
    setCards(prev => {
      const existing = prev.get(key);
      if (!existing) return prev;
      const next = new Map(prev);
      next.set(key, { ...existing, ...patch });
      return next;
    });
  }, []);

  const uploadToActiveJob = useCallback(async (vids: LocalVideo[]) => {
    const activeJobId = jobIdRef.current;
    if (!activeJobId) return;

    for (const lv of vids) {
      const cardData: VideoCard = {
        localId: lv.id, filename: lv.file.name, localPreview: lv.preview,
        status: "uploading", progress: 0, progressLabel: "Uploading...",
        totalDetections: 0, framesAnalyzed: 0, duration: 0, fps: 0,
        avgConfidence: 0, maxConfidence: 0,
      };
      setCards(prev => { const n = new Map(prev); n.set(lv.id, cardData); return n; });
      nameToKeyRef.current.set(lv.file.name, lv.id);

      const formData = new FormData();
      formData.append("job_id", activeJobId);
      formData.append("file", lv.file);
      try {
        const res = await fetch("/api/video/upload", { method: "POST", body: formData });
        if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
        const data = await res.json();
        nameToKeyRef.current.set(data.file_id, lv.id);
        updateCard(lv.id, { fileId: data.file_id, status: "queued", progressLabel: "Queued" });
      } catch (err: any) {
        updateCard(lv.id, { status: "error", error: err.message || "Upload failed" });
      }
    }
    setBatchProgress(prev => ({ ...prev, total: prev.total + vids.length }));
  }, [updateCard]);

  const addVideos = useCallback((files: File[]) => {
    const videoFiles = files.filter(f => f.type.startsWith("video/"));
    if (videoFiles.length === 0) {
      toast.warning("No video files found", 3000);
      return;
    }
    const newVids: LocalVideo[] = videoFiles.map(file => ({
      id: uid(), file, preview: URL.createObjectURL(file),
    }));
    setLocalVideos(prev => [...prev, ...newVids]);
    toast.success(`Added ${videoFiles.length} video(s)`, 2000);

    if (processing && jobIdRef.current) {
      uploadToActiveJob(newVids);
    }
  }, [processing, uploadToActiveJob]);

  const removeVideo = useCallback((id: string) => {
    setLocalVideos(prev => {
      const v = prev.find(f => f.id === id);
      if (v) URL.revokeObjectURL(v.preview);
      return prev.filter(f => f.id !== id);
    });
  }, []);

  const clearAll = useCallback(() => {
    localVideos.forEach(v => URL.revokeObjectURL(v.preview));
    setLocalVideos([]);
    setCards(new Map());
    setJobId(null);
    setBatchProgress({ completed: 0, total: 0 });
    setProcessing(false);
    socketRef.current?.disconnect();
    socketRef.current = null;
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    nameToKeyRef.current.clear();
  }, [localVideos]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length > 0) {
      addVideos(Array.from(e.dataTransfer.files));
    }
  }, [addVideos]);

  const syncFromApi = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/video/results/${id}`);
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
          if (r.status === "done" || r.video_url) {
            changed = true;
            next.set(cardKey, {
              ...(existing || {} as VideoCard),
              fileId: r.file_id,
              status: "complete",
              progress: 100,
              progressLabel: "Complete",
              thumbUrl: r.thumb_url,
              videoUrl: r.video_url,
              totalDetections: r.total_detections || 0,
              framesAnalyzed: r.frames_analyzed || 0,
              duration: r.duration || 0,
              fps: r.fps || 0,
              avgConfidence: r.avg_confidence || 0,
              maxConfidence: r.max_confidence || 0,
            });
          }
        });
        return changed ? next : prev;
      });

      setBatchProgress({ completed: body.completed || 0, total: body.total || 0 });
      if (body.status === "complete") {
        setProcessing(false);
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      }
    } catch { /* retry */ }
  }, []);

  const connectSocket = useCallback((id: string) => {
    if (socketRef.current) { socketRef.current.disconnect(); socketRef.current = null; }
    const sock = io({ path: "/socket.io/", transports: ["websocket", "polling"] });
    socketRef.current = sock;

    sock.on("connect", () => {
      sock.emit("subscribe_job", { job_id: id });
      syncFromApi(id);
    });

    sock.on("video_item_queued", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const key = nameToKeyRef.current.get(d.filename);
      if (key) {
        nameToKeyRef.current.set(d.file_id, key);
        updateCard(key, { fileId: d.file_id, status: "queued", progressLabel: "Queued" });
      }
    });

    sock.on("video_item_start", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const key = nameToKeyRef.current.get(d.file_id) || nameToKeyRef.current.get(d.filename);
      if (key) updateCard(key, { status: "processing", progressLabel: "Analyzing..." });
    });

    sock.on("video_progress", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const key = nameToKeyRef.current.get(d.file_id);
      if (key) updateCard(key, { progress: d.percent, progressLabel: `${d.percent}% — ${d.frames_done} frames analyzed` });
    });

    sock.on("video_item_result", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      const key = nameToKeyRef.current.get(d.file_id) || nameToKeyRef.current.get(d.filename);
      if (key) {
        if (d.error) {
          updateCard(key, { status: "error", error: d.error });
        } else {
          updateCard(key, {
            fileId: d.file_id, status: "complete", progress: 100, progressLabel: "Complete",
            thumbUrl: d.thumb_url, videoUrl: d.video_url,
            totalDetections: d.total_detections || 0,
            framesAnalyzed: d.frames_analyzed || 0,
            duration: d.duration || 0, fps: d.fps || 0,
            avgConfidence: d.avg_confidence || 0, maxConfidence: d.max_confidence || 0,
          });
        }
      }
      setBatchProgress({ completed: d.completed || 0, total: d.total || 0 });
    });

    sock.on("video_batch_complete", (d: any) => {
      if (d.job_id !== jobIdRef.current) return;
      setProcessing(false);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      toast.success(`All videos processed! ${d.total_detections} defects found.`, 5000);
      getRecentVideos(50).then(setVideos).catch(() => {});
    });
  }, [syncFromApi, updateCard]);

  const startDetection = useCallback(async () => {
    if (localVideos.length === 0) return;
    setProcessing(true);
    nameToKeyRef.current.clear();

    const newCards = new Map<string, VideoCard>();
    localVideos.forEach(lv => {
      newCards.set(lv.id, {
        localId: lv.id, filename: lv.file.name, localPreview: lv.preview,
        status: "pending", progress: 0, progressLabel: "Pending",
        totalDetections: 0, framesAnalyzed: 0, duration: 0, fps: 0,
        avgConfidence: 0, maxConfidence: 0,
      });
      nameToKeyRef.current.set(lv.file.name, lv.id);
    });
    setCards(newCards);
    setBatchProgress({ completed: 0, total: localVideos.length });

    try {
      const batchRes = await fetch("/api/video/batch/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          total: localVideos.length,
          det_confidence: config.confidence,
          det_slice_size: config.sliceSize,
          det_overlap: config.overlap,
          frame_interval: config.frameInterval,
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

      for (const lv of localVideos) {
        updateCard(lv.id, { status: "uploading", progressLabel: "Uploading..." });
        const formData = new FormData();
        formData.append("job_id", job_id);
        formData.append("file", lv.file);
        try {
          const uploadRes = await fetch("/api/video/upload", { method: "POST", body: formData });
          if (!uploadRes.ok) throw new Error(`Upload failed: ${uploadRes.status}`);
          const data = await uploadRes.json();
          nameToKeyRef.current.set(data.file_id, lv.id);
          updateCard(lv.id, { fileId: data.file_id, status: "queued", progressLabel: "Queued" });
        } catch (err: any) {
          updateCard(lv.id, { status: "error", error: err.message || "Upload failed" });
        }
      }
      toast.info(`Uploaded ${localVideos.length} video(s). Processing...`, 3000);
    } catch (err: any) {
      toast.error(`Failed: ${err.message}`, 5000);
      setProcessing(false);
    }
  }, [localVideos, config, connectSocket, syncFromApi, updateCard]);

  const completedCards = useMemo(() =>
    Array.from(cards.entries()).filter(([, c]) => c.status === "complete").map(([key]) => key),
    [cards]
  );

  const previewCard = previewId ? cards.get(previewId) : null;
  const previewIndex = previewId ? completedCards.indexOf(previewId) : -1;

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

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <Video className="text-premium-accent text-xl" />
              <div className="text-sm text-premium-accent uppercase tracking-wider">Video Analysis</div>
            </div>
            <div className="text-2xl font-bold text-white mb-2">Video Defect Detection</div>
            <div className="text-sm text-neutral-300 leading-relaxed">
              Upload one or more video files. Each video is analyzed frame-by-frame using YOLO detection
              on GPU, producing a fully annotated output video with bounding boxes overlaid.
            </div>
          </div>
          <div className="flex gap-2">
            {totalVideos > 0 && !processing && (
              <button onClick={clearAll}
                className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors flex items-center gap-2">
                <Trash2 size={16} /> Clear All
              </button>
            )}
            <button onClick={startDetection} disabled={!canStart}
              className="rounded-xl bg-gradient-accent text-white px-5 py-2.5 text-sm font-semibold hover:shadow-glow disabled:opacity-60 transition-all flex items-center gap-2">
              {processing ? (
                <><Clock className="text-lg animate-spin" /> Processing...</>
              ) : (
                <><Play className="text-lg" /> Process Videos{totalVideos > 0 ? ` (${totalVideos})` : ""}</>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Upload + Config */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div ref={uploadSectionRef} className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
          <div className="flex items-center gap-2 mb-6">
            <Upload className="text-premium-accent text-xl" />
            <div className="font-semibold text-white text-lg">Video Upload</div>
          </div>

          <MediaUploadBox
            accent="purple"
            dragActive={dragActive}
            disabled={processing}
            hasFiles={localVideos.length > 0}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            inputId="vid-upload"
            accept="video/*"
            multiple
            onInputChange={(e) => {
              if (e.target.files?.length) addVideos(Array.from(e.target.files));
              e.target.value = "";
            }}
            addMoreInputId="vid-add-more"
            onAddMoreChange={(e) => {
              if (e.target.files?.length) addVideos(Array.from(e.target.files));
              e.target.value = "";
            }}
            emptyIcon={<Video className="text-3xl text-neutral-500" />}
            emptyDescription="Drop video files here or click to browse"
            primaryButtonLabel="Select Videos"
            hint="Supports MP4, AVI, MOV — multiple files allowed"
          >
            <div className="flex items-center gap-2 text-sm text-premium-success">
              <CheckCircle2 size={16} />
              <span>{localVideos.length} video(s) selected</span>
            </div>
            <div className="flex flex-wrap gap-2 max-h-40 overflow-y-auto">
              {localVideos.map((lv) => (
                <div
                  key={lv.id}
                  className="relative group rounded-lg border border-neutral-700 bg-neutral-800 overflow-hidden"
                  style={{ width: 120 }}
                >
                  <video src={lv.preview} muted className="w-full h-16 object-cover" />
                  <div className="p-1">
                    <p className="text-[9px] text-white truncate">{lv.file.name}</p>
                    <p className="text-[8px] text-neutral-400">{(lv.file.size / 1024 / 1024).toFixed(1)} MB</p>
                  </div>
                  {!processing && (
                    <button
                      type="button"
                      onClick={() => removeVideo(lv.id)}
                      className="absolute -top-1 -right-1 bg-red-500 rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X size={10} className="text-white" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </MediaUploadBox>
        </div>

        {/* Config */}
        <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
          <div className="flex items-center gap-2 mb-6">
            <SlidersHorizontal className="text-premium-accent text-xl" />
            <div className="font-semibold text-white text-lg">Detection Configuration</div>
          </div>
          <div className="space-y-5">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-white">Frame Interval</div>
                <span className="text-sm font-mono text-premium-accent">{config.frameInterval}s</span>
              </div>
              <input type="range" min="1" max="10" step="1" value={config.frameInterval}
                onChange={e => setConfig(p => ({ ...p, frameInterval: parseInt(e.target.value) }))}
                disabled={processing}
                className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-neutral-700 accent-cyan-500 disabled:opacity-50" />
              <div className="flex justify-between text-xs text-neutral-500 mt-1"><span>1s (detailed)</span><span>10s (fast)</span></div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-white">Confidence Threshold</div>
                <span className="text-sm font-mono text-premium-accent">{config.confidence.toFixed(2)}</span>
              </div>
              <input type="range" min="5" max="95" step="5" value={Math.round(config.confidence * 100)}
                onChange={e => setConfig(p => ({ ...p, confidence: parseInt(e.target.value) / 100 }))}
                disabled={processing}
                className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-neutral-700 accent-cyan-500 disabled:opacity-50" />
              <div className="flex justify-between text-xs text-neutral-500 mt-1"><span>0.05</span><span>0.95</span></div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-white">SAHI Slice Size</div>
                <span className="text-sm font-mono text-premium-accent">{config.sliceSize}px</span>
              </div>
              <select value={config.sliceSize}
                onChange={e => setConfig(p => ({ ...p, sliceSize: parseInt(e.target.value) }))}
                disabled={processing}
                className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent outline-none disabled:opacity-50">
                <option value="256">256px (Fine)</option>
                <option value="512">512px</option>
                <option value="640">640px (Default)</option>
                <option value="1024">1024px (Fast)</option>
              </select>
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-white">SAHI Overlap</div>
                <span className="text-sm font-mono text-premium-accent">{config.overlap.toFixed(2)}</span>
              </div>
              <input type="range" min="10" max="50" step="5" value={Math.round(config.overlap * 100)}
                onChange={e => setConfig(p => ({ ...p, overlap: parseInt(e.target.value) / 100 }))}
                disabled={processing}
                className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-neutral-700 accent-cyan-500 disabled:opacity-50" />
              <div className="flex justify-between text-xs text-neutral-500 mt-1"><span>0.10</span><span>0.50</span></div>
            </div>

            <div className="rounded-xl border border-neutral-700 bg-premium-card/30 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="text-premium-accent" size={16} />
                <div className="text-sm font-semibold text-white">GPU-Accelerated Pipeline</div>
              </div>
              <div className="space-y-1.5 text-xs text-neutral-300">
                <div>1. Upload video &rarr; extract frames at interval</div>
                <div>2. Run YOLO detection on GPU per sampled frame</div>
                <div>3. Annotate every frame with detections</div>
                <div>4. Re-encode annotated MP4 for playback</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Processing Progress */}
      {processing && (
        <div className="glass rounded-2xl border border-premium-accent/50 bg-premium-accent/10 p-4 shadow-premium">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Clock className="text-premium-accent animate-spin" size={18} />
              <span className="font-semibold text-white">Processing Videos</span>
            </div>
            <span className="text-sm text-neutral-300">
              {batchProgress.total > 0 ? `${Math.round((batchProgress.completed / batchProgress.total) * 100)}%` : "—"}
            </span>
          </div>
          <div className="w-full bg-neutral-800 rounded-full h-2.5 overflow-hidden">
            {batchProgress.total > 0 ? (
              <div className="bg-gradient-accent h-full transition-all duration-300 rounded-full" style={{ width: `${(batchProgress.completed / batchProgress.total) * 100}%` }} />
            ) : (
              <div className="h-full w-1/3 animate-progress-indeterminate rounded-full bg-gradient-to-r from-transparent via-cyan-500/70 to-transparent" />
            )}
          </div>
          <div className="mt-2 text-xs text-neutral-400">
            {batchProgress.total > 0 ? `${batchProgress.completed} of ${batchProgress.total} videos completed` : "Uploading videos..."}
          </div>
        </div>
      )}

      {/* Video Grid */}
      {cards.size > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Layers className="text-premium-accent" size={20} />
              Video Results ({cards.size})
            </h2>
            <div className="flex gap-3 text-xs text-neutral-400">
              {(() => {
                const completed = Array.from(cards.values()).filter(c => c.status === "complete").length;
                const errors = Array.from(cards.values()).filter(c => c.status === "error").length;
                const active = Array.from(cards.values()).filter(c => ["processing", "queued", "uploading"].includes(c.status)).length;
                return (
                  <>
                    {completed > 0 && <span className="text-green-400">&#x2713; {completed} complete</span>}
                    {active > 0 && <span className="text-premium-accent">&#x21BB; {active} processing</span>}
                    {errors > 0 && <span className="text-red-400">&#x2717; {errors} failed</span>}
                  </>
                );
              })()}
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {Array.from(cards.entries()).map(([key, card]) => (
              <div key={key}
                onClick={() => card.status === "complete" && setPreviewId(key)}
                className={`rounded-xl border overflow-hidden transition-all group ${
                  card.status === "complete"
                    ? "border-green-500/30 bg-green-500/5 cursor-pointer hover:shadow-glow hover:border-premium-accent/50"
                    : card.status === "error"
                    ? "border-red-500/30 bg-red-500/5"
                    : card.status === "processing"
                    ? "border-premium-accent/50 bg-premium-accent/5"
                    : "border-neutral-800 bg-premium-card/30"
                }`}
              >
                <div className="relative aspect-video bg-neutral-800 overflow-hidden">
                  {card.status === "complete" && card.thumbUrl ? (
                    <img src={card.thumbUrl} alt={card.filename}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200" loading="lazy" />
                  ) : card.localPreview ? (
                    <video src={card.localPreview} muted className="w-full h-full object-cover opacity-50" />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center"><Video className="text-neutral-600" size={28} /></div>
                  )}

                  {card.status !== "complete" && card.status !== "error" && (
                    <div className="absolute inset-0 bg-black/40 flex flex-col items-center justify-center gap-2">
                      {card.status === "processing"
                        ? <Clock className="text-premium-accent animate-spin" size={22} />
                        : <Clock className="text-neutral-400" size={22} />}
                      <span className="text-[10px] text-white font-medium px-2 text-center">{card.progressLabel}</span>
                      {card.status === "processing" && (
                        <div className="w-3/4 bg-neutral-700 rounded-full h-1 overflow-hidden">
                          <div className="bg-cyan-500 h-full rounded-full transition-all duration-300" style={{ width: `${card.progress}%` }} />
                        </div>
                      )}
                    </div>
                  )}

                  {card.status === "error" && (
                    <div className="absolute inset-0 bg-black/50 flex flex-col items-center justify-center gap-1 px-2">
                      <XCircle className="text-red-400" size={22} />
                      <span className="text-[9px] text-red-300 text-center">{card.error || "Error"}</span>
                    </div>
                  )}

                  {card.status === "complete" && (
                    <>
                      <div className="absolute top-1 right-1">
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${card.totalDetections > 0 ? "bg-red-500/90 text-white" : "bg-green-500/90 text-white"}`}>
                          {card.totalDetections} det
                        </span>
                      </div>
                      <div className="absolute bottom-1 left-1">
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-blue-500/80 text-white">
                          {formatTime(card.duration)}
                        </span>
                      </div>
                      <div className="absolute bottom-1 right-1"><CheckCircle2 className="text-green-400 drop-shadow-lg" size={14} /></div>
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="bg-black/60 rounded-full p-2"><Play className="text-white" size={24} /></div>
                      </div>
                    </>
                  )}

                  <div className="absolute top-1 left-1">
                    <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-purple-500/80 text-white">VIDEO</span>
                  </div>
                </div>

                <div className="p-2">
                  <p className="text-[11px] truncate font-medium text-white" title={card.filename}>{card.filename}</p>
                  {card.status === "complete" && card.avgConfidence > 0 && (
                    <div className="mt-1 flex items-center gap-1">
                      <div className="flex-1 bg-neutral-700 rounded-full h-1.5 overflow-hidden">
                        <div className={`h-full rounded-full ${card.avgConfidence >= 0.7 ? "bg-green-500" : card.avgConfidence >= 0.4 ? "bg-yellow-500" : "bg-red-500"}`}
                          style={{ width: `${Math.round(card.avgConfidence * 100)}%` }} />
                      </div>
                      <span className="text-[10px] font-mono text-neutral-400">{Math.round(card.avgConfidence * 100)}%</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Progress Bar below grid */}
      {cards.size > 0 && (() => {
        const allCards = Array.from(cards.values());
        const completed = allCards.filter(c => c.status === "complete").length;
        const errors = allCards.filter(c => c.status === "error").length;
        const done = completed + errors;
        const total = allCards.length;
        const pct = total > 0 ? Math.round((done / total) * 100) : 0;
        const totalDets = allCards.reduce((s, c) => s + c.totalDetections, 0);
        const isRunning = done < total;
        const currentlyProcessing = allCards.find(c => c.status === "processing");

        return (
          <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Layers className="text-premium-accent" size={18} />
                <span className="font-semibold text-white text-sm">Video Detection Progress</span>
              </div>
              <span className="text-xs font-mono text-premium-accent">{pct}%</span>
            </div>
            <div className="w-full bg-neutral-800 rounded-full h-3 overflow-hidden mb-3">
              <div className={`h-full rounded-full transition-all duration-500 ${
                isRunning ? "bg-gradient-to-r from-cyan-500 to-blue-500"
                : errors > 0 ? "bg-gradient-to-r from-green-500 to-yellow-500"
                : "bg-gradient-to-r from-green-500 to-emerald-400"
              }`} style={{ width: `${pct}%` }} />
            </div>
            <div className="flex items-center justify-between text-xs text-neutral-400">
              <div className="flex gap-4">
                <span>{done} / {total} videos</span>
                {totalDets > 0 && <span className="text-red-400">{totalDets} defect{totalDets !== 1 ? "s" : ""}</span>}
              </div>
              <div>
                {isRunning && currentlyProcessing && (
                  <span className="text-premium-accent">
                    Analyzing: {currentlyProcessing.filename.length > 25 ? currentlyProcessing.filename.slice(0, 22) + "..." : currentlyProcessing.filename}
                  </span>
                )}
                {!isRunning && done === total && (
                  <span className="text-green-400 flex items-center gap-1"><CheckCircle2 size={12} /> All videos processed</span>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Empty state */}
      {cards.size === 0 && totalVideos === 0 && (
        <div className="glass rounded-2xl border-2 border-dashed border-neutral-700 p-12 text-center shadow-premium">
          <Video className="text-4xl text-neutral-500 mx-auto mb-4" />
          <div className="text-neutral-300 text-lg mb-2">No videos uploaded yet</div>
          <div className="text-neutral-500 text-sm">Upload one or more videos above to start defect detection</div>
        </div>
      )}

      {/* Recent scanned videos (from former Videos page) */}
      <div className="space-y-4">
        <div>
          <h2 className="text-xl font-bold text-white mb-1">Recent Scanned Videos</h2>
          <p className="text-sm text-neutral-400">Processed video analysis results</p>
        </div>
        {videosLoading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="glass rounded-xl border border-neutral-800 p-6 h-48 animate-pulse" />
            ))}
          </div>
        ) : videosError ? (
          <div className="glass rounded-xl border border-premium-danger/50 bg-premium-danger/10 p-6">
            <div className="flex items-center gap-3 text-premium-danger">
              <AlertTriangle size={20} />
              <span>{videosError}</span>
            </div>
          </div>
        ) : videos.length === 0 ? (
          <div className="glass rounded-xl border border-neutral-800 p-12 text-center">
            <Film className="text-neutral-600 mx-auto mb-4" size={48} />
            <h3 className="text-xl font-semibold text-white mb-2">No Videos Yet</h3>
            <p className="text-neutral-400 mb-6">Upload videos above to start processing and analyzing power line inspections</p>
            <button
              type="button"
              onClick={scrollToUpload}
              className="inline-flex items-center gap-2 px-6 py-3 bg-premium-accent hover:bg-premium-accent/90 text-white rounded-lg font-medium transition-colors"
            >
              <Video size={18} />
              Upload Video
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {videos.map((video) => {
              const isExpanded = expandedVideos.has(video.video_id);
              const stats = video.processing_stats || {};
              const videoInfo = video.video_info || {};
              const defectSummary = video.defect_summary || {};
              const frameResults = video.frame_results || [];

              return (
                <motion.div
                  key={video.video_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={pageTransition}
                  className="glass rounded-xl border border-neutral-800 overflow-hidden"
                >
                  <div
                    className="p-6 cursor-pointer hover:bg-neutral-800/50 transition-colors"
                    onClick={() => toggleVideo(video.video_id)}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <div className="rounded-full bg-premium-accent/20 p-2 border border-premium-accent/30">
                            <Film className="text-premium-accent" size={20} />
                          </div>
                          <div>
                            <h3 className="text-lg font-semibold text-white">
                              {videoInfo.filename || `Video ${video.video_id}`}
                            </h3>
                            {video.tower_id && (
                              <div className="text-sm text-neutral-400 mt-1">Tower ID: {video.tower_id}</div>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-wrap items-center gap-4 text-sm text-neutral-400 mt-3">
                          <div className="flex items-center gap-1">
                            <Calendar size={14} />
                            <span>{formatVideoDate(video.created_at)}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Clock size={14} />
                            <span>Duration: {formatDuration(videoInfo.duration_seconds || 0)}</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Video size={14} />
                            <span>{stats.processed_frames || 0} frames processed</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="text-green-400 flex items-center gap-1">
                            <CheckCircle2 size={14} />
                            {stats.processed_frames || 0} processed
                          </span>
                          {stats.failed_frames > 0 && (
                            <span className="text-red-400 flex items-center gap-1">
                              <XCircle size={14} />
                              {stats.failed_frames} failed
                            </span>
                          )}
                        </div>
                        <ChevronRight
                          className={`text-neutral-400 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                          size={20}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                      <div className="glass rounded-lg border border-neutral-700 p-3">
                        <div className="text-xs text-neutral-400 mb-1">Total Detections</div>
                        <div className="text-xl font-bold text-white">{stats.total_detections || 0}</div>
                      </div>
                      <div className="glass rounded-lg border border-neutral-700 p-3">
                        <div className="text-xs text-neutral-400 mb-1">Avg Confidence</div>
                        <div className="text-xl font-bold text-white">
                          {((stats.average_confidence || 0) * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div className="glass rounded-lg border border-neutral-700 p-3">
                        <div className="text-xs text-neutral-400 mb-1">FPS</div>
                        <div className="text-xl font-bold text-white">{videoInfo.fps?.toFixed(1) || "—"}</div>
                      </div>
                      <div className="glass rounded-lg border border-neutral-700 p-3">
                        <div className="text-xs text-neutral-400 mb-1">Defect Types</div>
                        <div className="text-xl font-bold text-white">{Object.keys(defectSummary).length}</div>
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="px-6 pb-6 border-t border-neutral-800 space-y-4"
                    >
                      {Object.keys(defectSummary).length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                            <BarChart3 size={16} />
                            Detections by Type
                          </h4>
                          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                            {Object.entries(defectSummary).map(([type, count]) => (
                              <div key={type} className="glass rounded-lg border border-neutral-700 p-3">
                                <div className="text-premium-accent font-semibold text-sm capitalize">
                                  {String(type).replace(/_/g, " ")}
                                </div>
                                <div className="text-neutral-300 text-xs mt-1">
                                  {count} detection{count !== 1 ? "s" : ""}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {frameResults.length > 0 && (
                        <div>
                          <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                            <Eye size={16} />
                            Frame Analysis ({frameResults.length} frames)
                          </h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-96 overflow-y-auto">
                            {frameResults.map((frame) => (
                              <div key={frame.frame_number} className="glass rounded-lg border border-neutral-700 overflow-hidden">
                                <img
                                  src={videoFrameUrl(
                                    video.video_id,
                                    `overlay_${frame.frame_number.toString().padStart(4, "0")}.jpg`
                                  )}
                                  alt={`Frame ${frame.frame_number}`}
                                  className="w-full h-24 object-cover"
                                />
                                <div className="p-2">
                                  <div className="text-xs text-neutral-400">{frame.timestamp?.toFixed(1)}s</div>
                                  <div className="text-xs text-white font-medium">
                                    {frame.detections_count} detection{frame.detections_count !== 1 ? "s" : ""}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="pt-4 border-t border-neutral-800">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                          <div>
                            <div className="text-neutral-400">Video ID</div>
                            <div className="text-white font-mono text-xs mt-1">{video.video_id}</div>
                          </div>
                          <div>
                            <div className="text-neutral-400">Frame Interval</div>
                            <div className="text-white mt-1">1 frame every {videoInfo.frame_interval || 1} second</div>
                          </div>
                          <div>
                            <div className="text-neutral-400">Status</div>
                            <div className="text-green-400 mt-1 capitalize">{video.status}</div>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Preview Modal — Full annotated video */}
      {previewId && previewCard && (
        <div className="fixed inset-0 z-50 bg-black/90 flex" onClick={() => setPreviewId(null)}>
          <button onClick={() => setPreviewId(null)}
            className="absolute top-4 right-4 z-10 rounded-full bg-neutral-800/90 text-white p-2 hover:bg-neutral-700 transition-colors">
            <X size={24} />
          </button>

          {completedCards.length > 1 && (
            <>
              <button onClick={e => { e.stopPropagation(); navigatePreview(-1); }}
                className="absolute left-4 top-1/2 -translate-y-1/2 z-10 rounded-full bg-neutral-800/90 text-white p-2 hover:bg-neutral-700 transition-colors">
                <ChevronLeft size={24} />
              </button>
              <button onClick={e => { e.stopPropagation(); navigatePreview(1); }}
                className="absolute right-[340px] top-1/2 -translate-y-1/2 z-10 rounded-full bg-neutral-800/90 text-white p-2 hover:bg-neutral-700 transition-colors">
                <ChevronRight size={24} />
              </button>
            </>
          )}

          {/* Video Player */}
          <div className="flex-1 flex items-center justify-center overflow-auto p-8" onClick={e => e.stopPropagation()}>
            <div className="relative w-full max-w-5xl">
              <div className="absolute top-2 right-2 z-10 rounded-lg bg-neutral-900/90 border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300">
                {previewIndex + 1} / {completedCards.length}
              </div>
              {previewCard.videoUrl ? (
                <video
                  key={previewCard.videoUrl}
                  src={previewCard.videoUrl}
                  controls autoPlay
                  className="w-full rounded-xl shadow-2xl max-h-[80vh] bg-black"
                />
              ) : (
                <div className="w-full aspect-video bg-neutral-900 rounded-xl flex items-center justify-center text-neutral-500">
                  Video not available
                </div>
              )}
            </div>
          </div>

          {/* Detail Panel */}
          <div className="w-[320px] bg-[#0f1419] border-l border-neutral-800 overflow-y-auto flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b border-neutral-800">
              <div className="text-lg font-bold text-white truncate" title={previewCard.filename}>{previewCard.filename}</div>
              <div className="flex items-center gap-2 mt-2">
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/50">VIDEO</span>
                <span className="text-xs text-neutral-400">{formatTime(previewCard.duration)}</span>
                <span className="text-xs text-neutral-500">{previewCard.fps} fps</span>
              </div>
            </div>

            <div className="p-4 border-b border-neutral-800 grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-neutral-400">Total Detections</div>
                <div className="text-xl font-bold text-white">{previewCard.totalDetections}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-400">Frames Analyzed</div>
                <div className="text-xl font-bold text-white">{previewCard.framesAnalyzed}</div>
              </div>
              <div>
                <div className="text-xs text-neutral-400">Avg Confidence</div>
                <div className="text-sm font-semibold text-green-400">
                  {previewCard.avgConfidence ? `${Math.round(previewCard.avgConfidence * 100)}%` : "—"}
                </div>
              </div>
              <div>
                <div className="text-xs text-neutral-400">Max Confidence</div>
                <div className="text-sm font-semibold text-cyan-400">
                  {previewCard.maxConfidence ? `${Math.round(previewCard.maxConfidence * 100)}%` : "—"}
                </div>
              </div>
            </div>

            <div className="p-4 border-b border-neutral-800">
              <div className="text-xs text-neutral-400 mb-2">Detection Density</div>
              <div className="w-full bg-neutral-700 rounded-full h-2 overflow-hidden">
                <div className={`h-full rounded-full ${previewCard.avgConfidence >= 0.7 ? "bg-green-500" : previewCard.avgConfidence >= 0.4 ? "bg-yellow-500" : "bg-red-500"}`}
                  style={{ width: `${Math.min(100, Math.round(previewCard.avgConfidence * 100))}%` }} />
              </div>
              <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                <span>Low</span><span>High</span>
              </div>
            </div>

            <div className="flex-1 p-4">
              <div className="text-xs text-neutral-400 mb-3">Summary</div>
              <div className="space-y-2 text-sm text-neutral-300">
                <div className="flex justify-between">
                  <span>Video Duration</span>
                  <span className="text-white font-medium">{formatTime(previewCard.duration)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Frame Rate</span>
                  <span className="text-white font-medium">{previewCard.fps} fps</span>
                </div>
                <div className="flex justify-between">
                  <span>Frames Sampled</span>
                  <span className="text-white font-medium">{previewCard.framesAnalyzed}</span>
                </div>
                <div className="flex justify-between">
                  <span>Detections Found</span>
                  <span className="text-white font-medium">{previewCard.totalDetections}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
