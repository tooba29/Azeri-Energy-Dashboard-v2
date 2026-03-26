import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { getRecentVideos, videoFrameUrl, type VideoResult } from "../api/api";
import { toast } from "../components/Toast";
import {
  Video,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Calendar,
  Clock,
  BarChart3,
  Film,
  Eye,
  Download,
  AlertTriangle,
} from "lucide-react";

export default function Videos() {
  const [videos, setVideos] = useState<VideoResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedVideos, setExpandedVideos] = useState<Set<string>>(new Set());
  const reduceMotion = useReducedMotion();

  const toggleVideo = (videoId: string) => {
    setExpandedVideos(prev => {
      const next = new Set(prev);
      if (next.has(videoId)) {
        next.delete(videoId);
      } else {
        next.add(videoId);
      }
      return next;
    });
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRecentVideos(50)
      .then(setVideos)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Failed to load videos";
        setError(msg);
        toast.error(msg, 5000);
      })
      .finally(() => setLoading(false));
  }, []);

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
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const transition = reduceMotion ? { duration: 0 } : { duration: 0.2 };

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={transition}
        className="space-y-6"
      >
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Recent Scanned Videos</h1>
          <p className="text-neutral-400">View processed video analysis results</p>
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass rounded-xl border border-neutral-800 p-6 h-48 animate-pulse" />
          ))}
        </div>
      </motion.div>
    );
  }

  if (error) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={transition}
        className="space-y-6"
      >
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Recent Scanned Videos</h1>
          <p className="text-neutral-400">View processed video analysis results</p>
        </div>
        <div className="glass rounded-xl border border-premium-danger/50 bg-premium-danger/10 p-6">
          <div className="flex items-center gap-3 text-premium-danger">
            <AlertTriangle size={20} />
            <span>{error}</span>
          </div>
        </div>
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
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Recent Scanned Videos</h1>
        <p className="text-neutral-400">
          {videos.length === 0
            ? "No videos processed yet"
            : `${videos.length} video${videos.length !== 1 ? "s" : ""} processed`}
        </p>
      </div>

      {videos.length === 0 ? (
        <div className="glass rounded-xl border border-neutral-800 p-12 text-center">
          <Film className="text-neutral-600 mx-auto mb-4" size={48} />
          <h3 className="text-xl font-semibold text-white mb-2">No Videos Yet</h3>
          <p className="text-neutral-400 mb-6">
            Upload videos to start processing and analyzing power line inspections
          </p>
          <Link
            to="/video-upload"
            className="inline-flex items-center gap-2 px-6 py-3 bg-premium-accent hover:bg-premium-accent/90 text-white rounded-lg font-medium transition-colors"
          >
            <Video size={18} />
            Upload Video
          </Link>
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
                transition={transition}
                className="glass rounded-xl border border-neutral-800 overflow-hidden"
              >
                {/* Video Header */}
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
                            <div className="text-sm text-neutral-400 mt-1">
                              Tower ID: {video.tower_id}
                            </div>
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
                        className={`text-neutral-400 transition-transform ${
                          isExpanded ? "rotate-90" : ""
                        }`}
                        size={20}
                      />
                    </div>
                  </div>

                  {/* Quick Stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                    <div className="glass rounded-lg border border-neutral-700 p-3">
                      <div className="text-xs text-neutral-400 mb-1">Total Detections</div>
                      <div className="text-xl font-bold text-white">
                        {stats.total_detections || 0}
                      </div>
                    </div>
                    <div className="glass rounded-lg border border-neutral-700 p-3">
                      <div className="text-xs text-neutral-400 mb-1">Avg Confidence</div>
                      <div className="text-xl font-bold text-white">
                        {((stats.average_confidence || 0) * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="glass rounded-lg border border-neutral-700 p-3">
                      <div className="text-xs text-neutral-400 mb-1">FPS</div>
                      <div className="text-xl font-bold text-white">
                        {videoInfo.fps?.toFixed(1) || "—"}
                      </div>
                    </div>
                    <div className="glass rounded-lg border border-neutral-700 p-3">
                      <div className="text-xs text-neutral-400 mb-1">Defect Types</div>
                      <div className="text-xl font-bold text-white">
                        {Object.keys(defectSummary).length}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.2 }}
                    className="px-6 pb-6 border-t border-neutral-800 space-y-4"
                  >
                    {/* Defect Summary */}
                    {Object.keys(defectSummary).length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                          <BarChart3 size={16} />
                          Detections by Type
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                          {Object.entries(defectSummary).map(([type, count]) => (
                            <div
                              key={type}
                              className="glass rounded-lg border border-neutral-700 p-3"
                            >
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

                    {/* Frame Preview */}
                    {frameResults.length > 0 && (
                      <div>
                        <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                          <Eye size={16} />
                          Frame Analysis ({frameResults.length} frames)
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-96 overflow-y-auto">
                          {frameResults.map((frame) => (
                            <div
                              key={frame.frame_number}
                              className="glass rounded-lg border border-neutral-700 overflow-hidden"
                            >
                              <img
                                src={videoFrameUrl(
                                  video.video_id,
                                  `overlay_${frame.frame_number.toString().padStart(4, "0")}.jpg`
                                )}
                                alt={`Frame ${frame.frame_number}`}
                                className="w-full h-24 object-cover"
                              />
                              <div className="p-2">
                                <div className="text-xs text-neutral-400">
                                  {frame.timestamp?.toFixed(1)}s
                                </div>
                                <div className="text-xs text-white font-medium">
                                  {frame.detections_count} detection
                                  {frame.detections_count !== 1 ? "s" : ""}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Video Info */}
                    <div className="pt-4 border-t border-neutral-800">
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                        <div>
                          <div className="text-neutral-400">Video ID</div>
                          <div className="text-white font-mono text-xs mt-1">
                            {video.video_id}
                          </div>
                        </div>
                        <div>
                          <div className="text-neutral-400">Frame Interval</div>
                          <div className="text-white mt-1">
                            1 frame every {videoInfo.frame_interval || 1} second
                          </div>
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
    </motion.div>
  );
}
