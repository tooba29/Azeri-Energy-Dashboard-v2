import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import { getRecentBulkBatches, getRun, resolveArtifactUrl, API_BASE } from "../api/api";
import { toast } from "../components/Toast";
import { formatDetectionLabel } from "../utils/formatLabels";
import {
  Upload,
  CheckCircle2,
  XCircle,
  ChevronRight,
  Folder,
  Calendar,
  FileText,
  ArrowLeft,
  Eye,
  ExternalLink,
  AlertTriangle,
  BarChart3,
  Image as ImageIcon,
  X,
  Download,
} from "lucide-react";

export default function BulkBatches() {
  const [batches, setBatches] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedBatches, setExpandedBatches] = useState<Set<string>>(new Set());
  const [runPreviews, setRunPreviews] = useState<Record<string, { overlayUrl?: string; loading: boolean; runData?: any }>>({});
  const [previewModal, setPreviewModal] = useState<{ runId: string; imageUrl: string } | null>(null);
  const [filteredDefect, setFilteredDefect] = useState<{ batchId: string; defectType: string } | null>(null);
  const reduceMotion = useReducedMotion();

  const toggleBatch = (batchId: string) => {
    setExpandedBatches(prev => {
      const next = new Set(prev);
      if (next.has(batchId)) {
        next.delete(batchId);
      } else {
        next.add(batchId);
        // Load previews when expanding
        const batch = batches.find(b => b.batch_id === batchId);
        if (batch?.runs && batch.runs.length > 0) {
          loadRunPreviews(batch.runs); // Load all previews for scroll
        }
      }
      return next;
    });
  };

  const downloadBatchReport = async (batchId: string) => {
    if (!batchId) {
      toast.error('Batch ID is missing');
      return;
    }
    
    try {
      const url = `${API_BASE}/api/bulk-batches/${batchId}/report`;
      console.log('Downloading batch report:', { batchId, url, API_BASE });
      toast.info('Generating batch report...', 2000);
      
      const response = await fetch(url);
      
      console.log('Response status:', response.status, response.statusText);
      
      // Check content type first before reading body
      const contentType = response.headers.get('content-type') || '';
      
      if (!response.ok) {
        // Try to get error message from response
        let errorMessage = `Failed to download report (${response.status})`;
        try {
          // Clone response to read it without consuming the original
          const clonedResponse = response.clone();
          if (contentType.includes('application/json')) {
            const errorData = await clonedResponse.json();
            errorMessage = errorData.detail || errorMessage;
            console.error('Error details:', errorData);
            console.error('Full error response:', JSON.stringify(errorData, null, 2));
          } else {
            const text = await clonedResponse.text();
            console.error('Error response text:', text);
            if (text) {
              errorMessage = text.length > 200 ? text.substring(0, 200) + '...' : text;
            } else {
              errorMessage = response.statusText || errorMessage;
            }
          }
        } catch (e) {
          console.error('Error parsing error response:', e);
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }
      
      // Check if response is actually a PDF
      if (!contentType.includes('application/pdf')) {
        // Read as text to see what we got
        const text = await response.text();
        throw new Error(`Server returned non-PDF response (${contentType}): ${text.substring(0, 100)}`);
      }
      
      // Read as blob for PDF
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `batch_report_${batchId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      document.body.removeChild(a);
      toast.success('Batch report downloaded successfully');
    } catch (error) {
      console.error('Error downloading batch report:', error);
      const errorMessage = error instanceof Error ? error.message : 'Failed to download batch report';
      toast.error(`Failed to download batch report: ${errorMessage}`, 5000);
    }
  };

  const loadRunPreviews = async (runIds: string[]) => {
    // Mark as loading
    setRunPreviews(prev => {
      const next = { ...prev };
      runIds.forEach(runId => {
        if (!next[runId]) {
          next[runId] = { loading: true };
        }
      });
      return next;
    });

    // Fetch previews in parallel (limit concurrent requests)
    const previewPromises = runIds.map(async (runId) => {
      try {
        const runDetail = await getRun(runId);
        const overlayUrl = runDetail.artifacts 
          ? resolveArtifactUrl(runDetail.artifacts, runId, "overlay")
          : undefined;
        return { runId, overlayUrl, runData: runDetail };
      } catch (e) {
        console.error(`Failed to load preview for ${runId}:`, e);
        return { runId, overlayUrl: undefined, runData: undefined };
      }
    });

    const results = await Promise.all(previewPromises);
    
    // Update previews
    setRunPreviews(prev => {
      const next = { ...prev };
      results.forEach(({ runId, overlayUrl, runData }) => {
        next[runId] = { overlayUrl, loading: false, runData };
      });
      return next;
    });
  };

  useEffect(() => {
    setLoading(true);
    setError(null);
    // Fetch more batches (e.g., 50) to show all old batches
    getRecentBulkBatches(50)
      .then(setBatches)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Failed to load bulk batches";
        setError(msg);
        toast.error(msg, 5000);
      })
      .finally(() => setLoading(false));
  }, []);

  const formatBatchDate = (batchId: string) => {
    try {
      const match = batchId.match(/(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})/);
      if (match) {
        const [, year, month, day, hour, min, sec] = match;
        return new Date(`${year}-${month}-${day}T${hour}:${min}:${sec}`);
      }
      return null;
    } catch {
      return null;
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
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 animate-pulse">
              <div className="h-6 w-48 bg-neutral-700/50 rounded mb-4" />
              <div className="h-4 w-32 bg-neutral-700/40 rounded" />
            </div>
          ))}
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
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <Link
              to="/dashboard"
              className="text-neutral-400 hover:text-white transition-colors"
            >
              <ArrowLeft size={20} />
            </Link>
            <h1 className="text-3xl font-bold text-white">Recent Bulk Batches</h1>
          </div>
          <p className="text-neutral-400">View all processed bulk upload batches</p>
        </div>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-amber-500/50 bg-amber-500/10 p-4 flex items-center gap-3 text-amber-200"
        >
          <XCircle size={20} className="shrink-0" />
          <span className="text-sm">{error}</span>
          <button
            type="button"
            onClick={() => {
              setError(null);
              setLoading(true);
              getRecentBulkBatches(50)
                .then(setBatches)
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

      {batches.length === 0 && !error ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-16 text-center"
        >
          <Upload className="mx-auto text-neutral-500 mb-4" size={56} />
          <h2 className="text-xl font-semibold text-white mb-2">No bulk batches found</h2>
          <p className="text-neutral-400 mb-6">No bulk processing batches have been created yet.</p>
          <Link
            to="/bulk-upload"
            className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-5 py-2.5 text-sm font-semibold hover:bg-cyan-500/30 transition-colors"
          >
            <Upload size={18} />
            Create Bulk Upload
          </Link>
        </motion.div>
      ) : (
        <div className="space-y-4">
          {batches.map((batch, index) => {
            const batchDate = batch.batch_id ? formatBatchDate(batch.batch_id) : null;
            const folderCount = batch.organization?.folders ? Object.keys(batch.organization.folders).length : 0;
            const runCount = batch.runs?.length || 0;
            const totalImages = batch.total_images || batch.processed + batch.failed;
            const isExpanded = expandedBatches.has(batch.batch_id);
            
            return (
              <motion.div
                key={batch.batch_id || index}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...transition, delay: reduceMotion ? 0 : index * 0.05 }}
                className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 hover:border-cyan-500/50 transition-colors"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Folder className="text-cyan-400" size={20} />
                      <h3 className="text-lg font-semibold text-white">
                        Batch {batch.batch_id || "Unknown"}
                      </h3>
                    </div>
                    {batchDate && (
                      <div className="flex items-center gap-2 text-sm text-neutral-400 ml-8">
                        <Calendar size={14} />
                        <span>{batchDate.toLocaleString()}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-cyan-400 flex items-center gap-1" title="Total images">
                      <FileText size={16} />
                      {totalImages} total
                    </span>
                    <span className="text-green-400 flex items-center gap-1">
                      <CheckCircle2 size={16} />
                      {batch.processed} processed
                    </span>
                    {batch.failed > 0 && (
                      <span className="text-red-400 flex items-center gap-1">
                        <XCircle size={16} />
                        {batch.failed} failed
                      </span>
                    )}
                  </div>
                </div>

                {/* Batch Statistics */}
                <div className="mb-4 ml-8 grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="glass rounded-lg border border-neutral-700 p-3">
                    <div className="text-xs text-neutral-400 mb-1">Total Images</div>
                    <div className="text-lg font-semibold text-white">{totalImages}</div>
                  </div>
                  <div className="glass rounded-lg border border-neutral-700 p-3">
                    <div className="text-xs text-neutral-400 mb-1">Runs Created</div>
                    <div className="text-lg font-semibold text-cyan-400">{runCount}</div>
                  </div>
                  <div className="glass rounded-lg border border-neutral-700 p-3">
                    <div className="text-xs text-neutral-400 mb-1">Success Rate</div>
                    <div className="text-lg font-semibold text-green-400">
                      {totalImages > 0 ? Math.round((batch.processed / totalImages) * 100) : 0}%
                    </div>
                  </div>
                  <div className="glass rounded-lg border border-neutral-700 p-3">
                    <div className="text-xs text-neutral-400 mb-1">Defect Folders</div>
                    <div className="text-lg font-semibold text-yellow-400">{folderCount}</div>
                  </div>
                </div>

                {batch.organization && batch.organization.enabled && folderCount > 0 && (
                  <div className="mb-4 ml-8">
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-sm text-neutral-300">
                        Organized into <span className="text-cyan-400 font-semibold">{folderCount}</span> defect type folders
                      </div>
                      {filteredDefect?.batchId === batch.batch_id && (
                        <button
                          onClick={() => {
                            setFilteredDefect(null);
                            // Reload previews for all runs when clearing filter
                            if (batch.runs && batch.runs.length > 0) {
                              loadRunPreviews(batch.runs);
                            }
                          }}
                          className="text-xs text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1"
                        >
                          <X size={12} />
                          Clear filter
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                      {Object.entries(batch.organization.folders || {}).map(([folder, count]) => {
                        const isFiltered = filteredDefect?.batchId === batch.batch_id && filteredDefect?.defectType === folder;
                        return (
                          <button
                            key={folder}
                            onClick={() => {
                              if (isFiltered) {
                                setFilteredDefect(null);
                                // Reload previews for all runs when clearing filter
                                if (batch.runs && batch.runs.length > 0) {
                                  loadRunPreviews(batch.runs.slice(0, 20));
                                }
                              } else {
                                setFilteredDefect({ batchId: batch.batch_id, defectType: folder });
                                // Load previews for filtered runs
                                const filteredRuns = batch.organization.details?.[folder]?.map((item: any) => item.run_id) || [];
                                if (filteredRuns.length > 0) {
                                  loadRunPreviews(filteredRuns);
                                }
                              }
                              // Auto-expand batch when filtering
                              if (!expandedBatches.has(batch.batch_id)) {
                                setExpandedBatches(prev => new Set(prev).add(batch.batch_id));
                              }
                            }}
                            className={`glass rounded-lg border p-3 transition-colors text-left ${
                              isFiltered 
                                ? "border-cyan-500 bg-cyan-500/10" 
                                : "border-neutral-700 hover:border-cyan-500/50"
                            }`}
                          >
                            <div className={`font-semibold text-sm capitalize ${
                              isFiltered ? "text-cyan-300" : "text-cyan-400"
                            }`}>
                              {String(folder).replace(/_/g, " ")}
                            </div>
                            <div className="text-neutral-300 text-xs mt-1">
                              {count} image{count !== 1 ? "s" : ""}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Runs List (Expandable) */}
                {runCount > 0 && (
                  <div className="mb-4 ml-8">
                    <button
                      onClick={() => toggleBatch(batch.batch_id)}
                      className="flex items-center gap-2 text-sm text-neutral-300 hover:text-white transition-colors mb-2"
                    >
                      <BarChart3 size={16} />
                      <span>
                        {filteredDefect?.batchId === batch.batch_id
                          ? `${(batch.organization.details?.[filteredDefect.defectType]?.length || 0)} run${(batch.organization.details?.[filteredDefect.defectType]?.length || 0) !== 1 ? "s" : ""} in ${filteredDefect.defectType.replace(/_/g, " ")}`
                          : `${runCount} run${runCount !== 1 ? "s" : ""} in this batch`}
                      </span>
                      <ChevronRight 
                        size={14} 
                        className={`transition-transform ${isExpanded ? "rotate-90" : ""}`}
                      />
                    </button>
                    {isExpanded && batch.runs && batch.runs.length > 0 && (() => {
                      // Filter runs based on selected defect type
                      let displayRuns: string[] = [];
                      if (filteredDefect?.batchId === batch.batch_id && batch.organization.details) {
                        const filteredRuns = batch.organization.details[filteredDefect.defectType]?.map((item: any) => item.run_id) || [];
                        displayRuns = filteredRuns;
                      } else {
                        displayRuns = batch.runs;
                      }
                      
                      return (
                        <div className="mt-2 space-y-2 max-h-96 overflow-y-auto">
                          {displayRuns.length === 0 ? (
                            <div className="text-center py-8 text-neutral-400">
                              <AlertTriangle size={24} className="mx-auto mb-2" />
                              <p>No runs found for this filter</p>
                            </div>
                          ) : (
                            <>
                              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                {displayRuns.map((runId: string, idx: number) => {
                                  const preview = runPreviews[runId];
                                  const detections = preview?.runData?.detections || [];
                                  return (
                                    <div
                                      key={runId}
                                      className="glass rounded-lg border border-neutral-700 hover:border-cyan-500/50 transition-colors overflow-hidden group relative"
                                    >
                                      {/* Image Preview - Square Size */}
                                      {preview?.overlayUrl ? (
                                        <div 
                                          className="relative w-full aspect-square bg-neutral-800 cursor-pointer"
                                          onClick={() => setPreviewModal({ runId, imageUrl: preview.overlayUrl! })}
                                        >
                                          <img
                                            src={preview.overlayUrl}
                                            alt={`Run ${runId.substring(0, 8)}`}
                                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
                                            onError={(e) => {
                                              (e.target as HTMLImageElement).style.display = "none";
                                            }}
                                          />
                                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                            <ImageIcon size={20} className="text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                                          </div>
                                          
                                          {/* Hover Detection Details Tooltip - Centered */}
                                          {detections.length > 0 && (
                                            <div className="absolute inset-0 bg-black/80 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center p-3 z-20 pointer-events-none">
                                              <div className="text-center w-full">
                                                <div className="text-white text-xs font-semibold mb-2">
                                                  Detections ({detections.length})
                                                </div>
                                                <div className="space-y-1.5">
                                                  {detections.slice(0, 3).map((det: any, detIdx: number) => (
                                                    <div key={detIdx} className="text-[10px] text-neutral-200">
                                                      <div className="font-medium text-white">
                                                        {formatDetectionLabel(det.component_type || "Unknown")}
                                                        {det.defect_type && ` - ${formatDetectionLabel(det.defect_type)}`}
                                                      </div>
                                                      <div className="text-neutral-300 mt-0.5">
                                                        {Math.round((det.det_conf || 0) * 100)}%
                                                        {det.defect_conf && `/${Math.round(det.defect_conf * 100)}%`}
                                                        {" • "}
                                                        <span className={`${
                                                          det.severity === "HIGH" ? "text-red-400" :
                                                          det.severity === "MEDIUM" ? "text-yellow-400" :
                                                          "text-green-400"
                                                        }`}>
                                                          {det.severity}
                                                        </span>
                                                      </div>
                                                    </div>
                                                  ))}
                                                  {detections.length > 3 && (
                                                    <div className="text-[10px] text-neutral-400 pt-1">
                                                      +{detections.length - 3} more
                                                    </div>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          )}
                                        </div>
                                      ) : preview?.loading ? (
                                        <div className="w-full aspect-square bg-neutral-800 flex items-center justify-center">
                                          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-400"></div>
                                        </div>
                                      ) : (
                                        <div className="w-full aspect-square bg-neutral-800 flex items-center justify-center">
                                          <ImageIcon size={24} className="text-neutral-600" />
                                        </div>
                                      )}
                                      
                                      {/* Run Info */}
                                      <Link
                                        to={`/runs/${runId}`}
                                        className="p-2 flex items-center justify-between group/link"
                                      >
                                        <div className="flex items-center gap-2">
                                          <Eye size={14} className="text-neutral-400 group-hover/link:text-cyan-400" />
                                          <span className="text-xs text-neutral-300 font-mono truncate">
                                            {runId.substring(0, 8)}...
                                          </span>
                                        </div>
                                        <ExternalLink size={12} className="text-neutral-500 group-hover/link:text-cyan-400" />
                                      </Link>
                                    </div>
                                  );
                                })}
                              </div>
                            </>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                )}

                <div className="flex items-center gap-2 text-xs text-neutral-400 pt-4 border-t border-neutral-800 ml-8">
                  <div className="ml-auto flex items-center gap-2">
                    <button
                      onClick={() => downloadBatchReport(batch.batch_id)}
                      className="text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1 transition-colors"
                      title="Download batch report PDF"
                    >
                      <Download size={14} />
                      Download Report
                    </button>
                    {runCount > 0 && (
                      <Link
                        to="/runs"
                        className="text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1"
                        title="View all runs"
                      >
                        <Eye size={14} />
                        View Runs
                      </Link>
                    )}
                    <Link
                      to="/bulk-upload"
                      className="text-cyan-400 hover:text-cyan-300 underline flex items-center gap-1"
                    >
                      New Upload
                      <ChevronRight size={12} />
                    </Link>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {batches.length > 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ ...transition, delay: reduceMotion ? 0 : 0.3 }}
          className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 text-center"
        >
          <p className="text-sm text-neutral-400">
            Showing {batches.length} bulk batch{batches.length !== 1 ? "es" : ""}
          </p>
        </motion.div>
      )}

      {/* Image Preview Modal */}
      {previewModal && (
        <div 
          className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4"
          onClick={() => setPreviewModal(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] w-full">
            <button
              onClick={() => setPreviewModal(null)}
              className="absolute top-4 right-4 z-10 bg-neutral-800 hover:bg-neutral-700 rounded-full p-2 transition-colors"
            >
              <X size={20} className="text-white" />
            </button>
            <img
              src={previewModal.imageUrl}
              alt={`Run ${previewModal.runId.substring(0, 8)}`}
              className="w-full h-auto rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="absolute bottom-4 left-4 bg-black/70 text-white px-3 py-2 rounded-lg text-sm font-mono">
              {previewModal.runId.substring(0, 8)}...
            </div>
            <Link
              to={`/runs/${previewModal.runId}`}
              className="absolute bottom-4 right-4 bg-cyan-500 hover:bg-cyan-600 text-white px-4 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              <Eye size={16} />
              View Details
            </Link>
          </div>
        </div>
      )}
    </motion.div>
  );
}
