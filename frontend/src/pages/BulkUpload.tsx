import React, { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { runPipeline, bulkProcess, getRun, resolveArtifactUrl } from "../api/api";
import { toast } from "../components/Toast";
import { formatDetectionLabel } from "../utils/formatLabels";
import {
  Upload,
  X,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  FileImage,
  Thermometer,
  Folder,
  Eye,
  Download,
  ArrowLeft,
} from "lucide-react";
import { Link } from "react-router-dom";

const BULK_PROCESSING_MESSAGES = [
  "Bulk images are being processed — hang tight!",
  "Model is processing and predicting...",
  "Identifying components and defects...",
  "Running AI detection pipeline...",
  "Almost there — analyzing images...",
];

type FileWithPreview = {
  file: File;
  preview: string;
  towerId: string;
  thermalFile?: File;
  thermalPreview?: string;
  status?: "pending" | "processing" | "completed" | "failed";
  error?: string;
  runId?: string;
  runData?: any; // Will store run details with detections
  overlayUrl?: string; // Overlay image URL
};

export default function BulkUpload() {
  const nav = useNavigate();
  const [files, setFiles] = useState<FileWithPreview[]>([]);
  const [processing, setProcessing] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);
  const [results, setResults] = useState<{
    success: number;
    failed: number;
    organization?: {
      enabled: boolean;
      folders: Record<string, number>;
      batch_dir?: string;
      batch_id?: string;
    };
  }>({ success: 0, failed: 0 });
  const [processingMessageIndex, setProcessingMessageIndex] = useState(0);

  useEffect(() => {
    if (!processing) return;
    const interval = setInterval(() => {
      setProcessingMessageIndex((i) => (i + 1) % BULK_PROCESSING_MESSAGES.length);
    }, 3000);
    return () => clearInterval(interval);
  }, [processing]);

  // Helper function to calculate detection summary
  const getDetectionSummary = (detections: any[]) => {
    if (!detections || detections.length === 0) return null;
    const high = detections.filter((d: any) => d.severity === "HIGH").length;
    const medium = detections.filter((d: any) => d.severity === "MEDIUM").length;
    const low = detections.filter((d: any) => d.severity === "LOW").length;
    const needsReview = detections.filter((d: any) => d.status === "needs_review").length;
    return { total: detections.length, high, medium, low, needsReview };
  };

  function fileToDataUrl(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(String(r.result));
      r.onerror = () => reject(new Error("Failed to read file"));
      r.readAsDataURL(file);
    });
  }

  const handleFileSelect = (selectedFiles: File[]) => {
    const newFiles: FileWithPreview[] = selectedFiles.map(file => {
      const preview = URL.createObjectURL(file);
      const towerId = file.name.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9-_]/g, "_");
      return { file, preview, towerId, status: "pending" as const };
    });
    setFiles(prev => [...prev, ...newFiles]);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      handleFileSelect(selectedFiles);
    }
    // Reset input to allow selecting the same files again
    e.target.value = '';
  };

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    if (selectedFiles.length > 0) {
      // Filter only image files from the folder
      const imageFiles = selectedFiles.filter(
        file => file.type.startsWith("image/")
      );
      if (imageFiles.length > 0) {
        handleFileSelect(imageFiles);
        toast.success(`Added ${imageFiles.length} image(s) from folder`, 3000);
      } else {
        toast.warning("No image files found in the selected folder", 3000);
      }
    }
    // Reset input to allow selecting the same folder again
    e.target.value = '';
  };

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files).filter(
        file => file.type.startsWith("image/")
      );
      if (droppedFiles.length > 0) {
        handleFileSelect(droppedFiles);
      } else {
        toast.warning("Please drop image files only", 3000);
      }
    }
  }, []);

  const removeFile = (index: number) => {
    setFiles(prev => {
      const removed = prev[index];
      if (removed.preview) URL.revokeObjectURL(removed.preview);
      if (removed.thermalPreview) URL.revokeObjectURL(removed.thermalPreview);
      return prev.filter((_, i) => i !== index);
    });
  };

  const updateTowerId = (index: number, id: string) => {
    setFiles(prev => prev.map((f, i) => i === index ? { ...f, towerId: id } : f));
  };

  const handleThermalSelect = (index: number, file: File) => {
    const preview = URL.createObjectURL(file);
    setFiles(prev => prev.map((f, i) => i === index ? { ...f, thermalFile: file, thermalPreview: preview } : f));
  };

  const processAll = async () => {
    if (files.length === 0) {
      toast.warning("Please select files to upload", 3000);
      return;
    }
    
    // Use bulk endpoint for 10+ images
    const useBulkEndpoint = files.length >= 10;
    
    setProcessing(true);
    setOverallProgress(0);
    setResults({ success: 0, failed: 0 });
    
    // Reset all file statuses
    setFiles(prev => prev.map(f => ({ ...f, status: "pending" as const, error: undefined })));
    
    if (useBulkEndpoint) {
      // Use bulk processing endpoint for large batches
      try {
        setOverallProgress(5); // Show initial progress
        
        // Prepare images array
        const imagesData = await Promise.all(
          files.map(async (item) => {
            const rgbData = await fileToDataUrl(item.file);
            const thermalData = item.thermalFile ? await fileToDataUrl(item.thermalFile) : undefined;
            return {
              filename: item.file.name,
              rgb_base64: rgbData,
              thermal_base64: thermalData,
              tower_id: item.towerId || undefined
            };
          })
        );
        
        setOverallProgress(10);
        
        // Update all files to processing status
        setFiles(prev => prev.map(f => ({ ...f, status: "processing" as const })));
        
        const result = await bulkProcess({
          images: imagesData,
          organize_by_defect: true
        });
        
        setOverallProgress(100);
        
        // Fetch run details for each processed image
        if (result.runs && result.runs.length > 0) {
          // Map run IDs to files and fetch details
          const runPromises = result.runs.map(async (runId: string, idx: number) => {
            if (idx < files.length) {
              try {
                const runDetails = await getRun(runId);
                return { index: idx, runId, runData: runDetails };
              } catch (e) {
                console.error(`Failed to fetch run details for ${runId}:`, e);
                return { index: idx, runId, runData: null };
              }
            }
            return null;
          });
          
          const runDetailsList = await Promise.all(runPromises);
          
          // Update files with run data
          setFiles(prev => prev.map((f, idx) => {
            const runDetail = runDetailsList.find(rd => rd && rd.index === idx);
            if (runDetail && runDetail.runData) {
              const overlayUrl = runDetail.runData.artifacts 
                ? resolveArtifactUrl(runDetail.runData.artifacts, runDetail.runId, "overlay")
                : undefined;
              return {
                ...f,
                status: "completed" as const,
                runId: runDetail.runId,
                runData: runDetail.runData,
                overlayUrl: overlayUrl
              };
            }
            return { ...f, status: "completed" as const };
          }));
        } else {
          // Update all files to completed
          setFiles(prev => prev.map(f => ({ ...f, status: "completed" as const })));
        }
        
        // Show success message with organization info
        const folderCount = Object.keys(result.organization.folders).length;
        toast.success(
          `Bulk processing complete! Processed ${result.processed} images organized into ${folderCount} folders.`,
          6000
        );
        
        // Set results with organization details
        setResults({
          success: result.processed,
          failed: result.failed,
          organization: {
            ...result.organization,
            batch_dir: result.batch_dir,
            batch_id: result.batch_id
          }
        });
        
      } catch (e: any) {
        const errorMessage = e instanceof Error ? e.message : "Unknown error";
        console.error("Bulk processing failed:", e);
        
        // Update all files to failed
        setFiles(prev => prev.map(f => ({ 
          ...f, 
          status: "failed" as const,
          error: errorMessage.length > 100 ? errorMessage.substring(0, 100) + "..." : errorMessage
        })));
        
        toast.error(`Bulk processing failed: ${errorMessage}`, 5000);
        setResults({ success: 0, failed: files.length });
      } finally {
        setProcessing(false);
      }
    } else {
      // Use single-image processing for small batches
      let successCount = 0;
      let failedCount = 0;

      for (let i = 0; i < files.length; i++) {
        const item = files[i];
        
        // Update status to processing
        setFiles(prev => prev.map((f, idx) => 
          idx === i ? { ...f, status: "processing" as const } : f
        ));
        
        try {
          const rgbData = await fileToDataUrl(item.file);
          const thermalData = item.thermalFile ? await fileToDataUrl(item.thermalFile) : undefined;

          const result = await runPipeline({
            tower_id: item.towerId || undefined,
            rgb_base64: rgbData,
            thermal_base64: thermalData,
            ambient_c: 25,
          });

          // Fetch run details to get detections
          if (result.run_id) {
            try {
              const runDetails = await getRun(result.run_id);
              const overlayUrl = runDetails.artifacts 
                ? resolveArtifactUrl(runDetails.artifacts, result.run_id, "overlay")
                : undefined;
              setFiles(prev => prev.map((f, idx) => 
                idx === i ? { 
                  ...f, 
                  status: "completed" as const,
                  runId: result.run_id,
                  runData: runDetails,
                  overlayUrl: overlayUrl
                } : f
              ));
            } catch (e) {
              console.error("Failed to fetch run details:", e);
              setFiles(prev => prev.map((f, idx) => 
                idx === i ? { 
                  ...f, 
                  status: "completed" as const,
                  runId: result.run_id
                } : f
              ));
            }
          } else {
            setFiles(prev => prev.map((f, idx) => 
              idx === i ? { ...f, status: "completed" as const } : f
            ));
          }
          
          successCount++;
          setResults(prev => ({ ...prev, success: prev.success + 1 }));
          
          // Navigate to run detail if run_id is available (only for first)
          if (result.run_id && i === 0) {
            setTimeout(() => {
              nav(`/runs/${result.run_id}`);
            }, 500);
            break;
          }
        } catch (e: any) {
          const errorMessage = e instanceof Error ? e.message : "Unknown error";
          console.error(`Failed to process ${item.towerId || item.file.name}:`, e);
          
          // Update status to failed with error message
          setFiles(prev => prev.map((f, idx) => 
            idx === i ? { 
              ...f, 
              status: "failed" as const,
              error: errorMessage.length > 100 ? errorMessage.substring(0, 100) + "..." : errorMessage
            } : f
          ));
          
          failedCount++;
          setResults(prev => ({ ...prev, failed: prev.failed + 1 }));
        }
        
        // Update overall progress
        const progress = ((i + 1) / files.length) * 100;
        setOverallProgress(progress);
      }

      setProcessing(false);
      
      // Show toast with actual counts
      if (successCount > 0 && failedCount === 0) {
        toast.success(`Successfully processed ${successCount} file(s)`, 4000);
      } else if (successCount > 0 && failedCount > 0) {
        toast.warning(`Processed ${successCount} file(s), ${failedCount} failed`, 4000);
      } else if (failedCount > 0) {
        toast.error(`Failed to process ${failedCount} file(s)`, 5000);
      }
    }
  };

  const clearAll = () => {
    files.forEach(f => {
      if (f.preview) URL.revokeObjectURL(f.preview);
      if (f.thermalPreview) URL.revokeObjectURL(f.thermalPreview);
    });
    setFiles([]);
    setResults({ success: 0, failed: 0 });
    setOverallProgress(0);
  };

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <Link
                to="/dashboard"
                className="text-neutral-400 hover:text-white transition-colors"
              >
                <ArrowLeft size={20} />
              </Link>
              <Upload className="text-premium-accent text-xl" />
              <div className="text-sm text-premium-accent uppercase tracking-wider">Bulk Operations</div>
            </div>
            <div className="text-2xl font-bold text-white mb-2">Bulk Upload</div>
            <div className="text-sm text-neutral-300 leading-relaxed">
              Upload multiple RGB images (and optional thermal) for batch processing. Each image will be processed through the AI pipeline and added to the system.
              {files.length >= 10 && (
                <div className="mt-2 text-xs text-premium-accent flex items-center gap-1">
                  <FileImage size={14} />
                  Bulk mode: Results will be organized into folders by defect type (rust, dirty, broken, etc.)
                </div>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            {files.length > 0 && !processing && (
              <button
                onClick={clearAll}
                className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors"
              >
                Clear All
              </button>
            )}
            <input
              type="file"
              accept="image/*"
              multiple
              onChange={handleInputChange}
              className="hidden"
              id="bulk-file-input"
              disabled={processing}
            />
            <label
              htmlFor="bulk-file-input"
              className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors cursor-pointer disabled:opacity-50"
            >
              <Upload className="inline mr-2" size={16} />
              Add Images
            </label>
            <input
              type="file"
              // @ts-ignore - webkitdirectory is a valid HTML attribute but not in React types
              webkitdirectory=""
              multiple
              onChange={handleFolderChange}
              className="hidden"
              id="bulk-folder-input"
              disabled={processing}
            />
            <label
              htmlFor="bulk-folder-input"
              className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors cursor-pointer disabled:opacity-50"
            >
              <Folder className="inline mr-2" size={16} />
              Add Folder
            </label>
            <button
              onClick={processAll}
              disabled={files.length === 0 || processing}
              className="rounded-xl bg-gradient-accent text-white px-5 py-2.5 text-sm font-semibold hover:shadow-glow disabled:opacity-60 transition-all flex items-center gap-2"
            >
              {processing ? (
                <>
                  <Clock className="animate-spin" size={16} />
                  Processing...
                </>
              ) : (
                <>
                  <CheckCircle2 size={16} />
                  Process All ({files.length})
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Overall Progress Bar */}
      {processing && (() => {
        const completedCount = files.filter(f => f.status === "completed" || f.status === "failed").length;
        const isIndeterminate = completedCount === 0;
        const displayProgress = isIndeterminate ? overallProgress : (completedCount / files.length) * 100;
        const displayCount = results.success + results.failed || completedCount;
        return (
          <div className="glass rounded-2xl border border-premium-accent/50 bg-premium-accent/10 p-4 shadow-premium">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Clock className="text-premium-accent animate-spin" size={18} />
                <span className="font-semibold text-white">Processing Images</span>
              </div>
              <span className="text-sm text-neutral-300">
                {isIndeterminate ? "—" : `${Math.round(displayProgress)}%`}
              </span>
            </div>
            <div className="w-full bg-neutral-800 rounded-full h-2.5 overflow-hidden">
              {isIndeterminate ? (
                <div className="h-full w-1/3 animate-progress-indeterminate rounded-full bg-gradient-to-r from-transparent via-cyan-500/70 to-transparent" />
              ) : (
                <div
                  className="bg-gradient-accent h-full transition-all duration-300 rounded-full"
                  style={{ width: `${displayProgress}%` }}
                />
              )}
            </div>
            <div className="mt-2 text-xs text-neutral-400">
              {isIndeterminate ? (
                <>{BULK_PROCESSING_MESSAGES[processingMessageIndex]}</>
              ) : (
                <>
                  {displayCount} of {files.length} completed
                  {results.success > 0 && <span className="text-green-400 ml-2">✓ {results.success} successful</span>}
                  {results.failed > 0 && <span className="text-red-400 ml-2">✗ {results.failed} failed</span>}
                </>
              )}
            </div>
          </div>
        );
      })()}

      {/* Results Summary */}
      {!processing && results.success + results.failed > 0 && (
        <div className="glass rounded-2xl border border-premium-accent/50 bg-premium-accent/10 p-6 shadow-premium">
          <div className="flex items-center justify-between mb-4">
            <div className="text-white font-semibold text-lg">Processing Complete</div>
            <div className="flex gap-4 text-sm">
              <span className="text-green-400 flex items-center gap-1">
                <CheckCircle2 size={16} />
                Success: {results.success}
              </span>
              {results.failed > 0 && (
                <span className="text-red-400 flex items-center gap-1">
                  <XCircle size={16} />
                  Failed: {results.failed}
                </span>
              )}
            </div>
          </div>
          
          {/* Organization Summary */}
          {results.organization && results.organization.enabled && (
            <div className="mt-4 pt-4 border-t border-premium-accent/30">
              <div className="text-white font-semibold mb-3 flex items-center gap-2">
                <FileImage size={18} />
                Organized by Defect Type
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {Object.entries(results.organization.folders).map(([folder, count]: [string, number]) => (
                  <div
                    key={folder}
                    className="glass rounded-lg border border-neutral-700 p-3 hover:border-premium-accent/50 transition-colors"
                  >
                    <div className="text-premium-accent font-semibold text-sm capitalize">
                      {folder.replace(/_/g, " ")}
                    </div>
                    <div className="text-neutral-300 text-xs mt-1">
                      {count} image{count !== 1 ? "s" : ""}
                    </div>
                  </div>
                ))}
              </div>
              {results.organization && (
                <div className="mt-3 text-xs text-neutral-400">
                  Results saved to: <code className="bg-neutral-800 px-1 rounded">{results.organization.batch_dir || "outputs/bulk_processing/"}</code>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Drag and Drop Zone */}
      {files.length === 0 && (
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`glass rounded-2xl border-2 border-dashed p-12 text-center shadow-premium transition-all ${
            dragActive
              ? "border-premium-accent bg-premium-accent/10"
              : "border-neutral-700 hover:border-premium-accent/50"
          }`}
        >
          <Upload className="text-4xl text-neutral-500 mx-auto mb-4" />
          <div className="text-neutral-300 text-lg mb-2">
            {dragActive ? "Drop images here" : "Drag & drop images here, or click 'Add Images' or 'Add Folder'"}
          </div>
          <div className="text-neutral-500 text-sm">Supports: JPEG, PNG, BMP, TIFF</div>
        </div>
      )}

      {/* Files Grid */}
      {files.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {files.map((item, index) => {
            const statusIcon = 
              item.status === "completed" ? (
                <CheckCircle2 className="text-green-400" size={20} />
              ) : item.status === "failed" ? (
                <XCircle className="text-red-400" size={20} />
              ) : item.status === "processing" ? (
                <Clock className="text-premium-accent animate-spin" size={20} />
              ) : (
                <FileImage className="text-neutral-400" size={20} />
              );

            return (
              <div
                key={index}
                className={`glass rounded-2xl border p-4 shadow-premium transition-all ${
                  item.status === "completed"
                    ? "border-green-500/30 bg-green-500/5"
                    : item.status === "failed"
                    ? "border-red-500/30 bg-red-500/5"
                    : item.status === "processing"
                    ? "border-premium-accent/50 bg-premium-accent/10"
                    : "border-neutral-800"
                }`}
              >
                {/* Image Preview Container - Original by default, Overlay on hover */}
                <div 
                  className="relative mb-3 cursor-pointer group"
                  onClick={() => item.runId && nav(`/runs/${item.runId}`)}
                >
                  <div className="relative w-full aspect-square bg-neutral-800 rounded-lg overflow-hidden group-hover:scale-110 transition-transform duration-300 ease-out">
                    {/* Original Image - Always visible */}
                    <img
                      src={item.preview}
                      alt={`Preview ${index}`}
                      className="w-full h-full object-cover"
                    />
                    
                    {/* Overlay Image - Shown on hover if available */}
                    {item.status === "completed" && item.overlayUrl && (
                      <img
                        src={item.overlayUrl}
                        alt={`Overlay ${index}`}
                        className="absolute inset-0 w-full h-full object-cover opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none"
                        onError={(e) => {
                          console.error("Failed to load overlay image:", item.overlayUrl);
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    )}
                    
                    {/* Detection count badge */}
                    {item.status === "completed" && item.runData?.detections && item.runData.detections.length > 0 && (
                      <div className="absolute top-2 left-2 bg-cyan-500/90 text-white text-xs font-bold px-2 py-1 rounded-lg z-10 shadow-lg">
                        {item.runData.detections.length} detection{item.runData.detections.length !== 1 ? "s" : ""}
                      </div>
                    )}
                    
                    <div className="absolute top-2 right-2 flex items-center gap-1 bg-black/70 rounded-lg px-2 py-1 z-10">
                      {statusIcon}
                    </div>
                    
                    {/* Hover Detection Details Tooltip - Bottom Left */}
                    {item.status === "completed" && item.runData?.detections && item.runData.detections.length > 0 && (
                      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/95 via-black/90 to-transparent rounded-b-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 p-3 z-20 pointer-events-none">
                        <div className="text-left w-full">
                          <div className="text-white text-xs font-semibold mb-1.5">
                            Detections ({item.runData.detections.length})
                          </div>
                          <div className="space-y-1">
                            {item.runData.detections.slice(0, 3).map((det: any, detIdx: number) => (
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
                            {item.runData.detections.length > 3 && (
                              <div className="text-[10px] text-neutral-400 pt-1">
                                +{item.runData.detections.length - 3} more
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {item.status === "processing" && (
                    <div className="absolute inset-0 bg-black/30 rounded-lg flex items-center justify-center z-30">
                      <div className="text-white font-semibold">Processing...</div>
                    </div>
                  )}
                </div>
                
                {/* Detection Summary */}
                {item.status === "completed" && item.runData?.detections && (() => {
                  const summary = getDetectionSummary(item.runData.detections);
                  if (!summary) return null;
                  return (
                    <div className="mb-2 p-2 bg-neutral-800/50 rounded-lg border border-neutral-700/50">
                      <div className="text-xs text-neutral-300">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-white">{summary.total} detection{summary.total !== 1 ? "s" : ""}</span>
                          {summary.needsReview > 0 && (
                            <span className="text-amber-400 font-semibold">• {summary.needsReview} need review</span>
                          )}
                        </div>
                        <div className="flex gap-2 text-neutral-400 flex-wrap">
                          {summary.high > 0 && <span className="text-red-400 font-medium">{summary.high} HIGH</span>}
                          {summary.medium > 0 && <span className="text-yellow-400 font-medium">{summary.medium} MEDIUM</span>}
                          {summary.low > 0 && <span className="text-green-400 font-medium">{summary.low} LOW</span>}
                        </div>
                      </div>
                    </div>
                  );
                })()}
                
                <div className="space-y-2">
                  <div>
                    <div className="text-xs text-neutral-400 mb-1">Tower ID</div>
                    <input
                      type="text"
                      value={item.towerId}
                      onChange={(e) => updateTowerId(index, e.target.value)}
                      placeholder="Auto-generated from filename"
                      disabled={processing}
                      className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-premium-accent disabled:opacity-50"
                    />
                  </div>
                  
                  <div>
                    <div className="text-xs text-neutral-400 mb-1 flex items-center gap-1">
                      <Thermometer size={12} />
                      Thermal Image (Optional)
                    </div>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleThermalSelect(index, file);
                      }}
                      disabled={processing}
                      className="w-full text-xs text-neutral-300 file:mr-2 file:py-1 file:px-2 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-premium-card file:text-white file:cursor-pointer disabled:opacity-50"
                    />
                    {item.thermalPreview && (
                      <img
                        src={item.thermalPreview}
                        alt="Thermal"
                        className="w-full h-16 object-cover rounded-lg mt-2"
                      />
                    )}
                  </div>

                  {item.error && (
                    <div className="rounded-lg bg-red-500/10 border border-red-500/30 p-2">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="text-red-400 flex-shrink-0 mt-0.5" size={14} />
                        <div className="text-xs text-red-400">{item.error}</div>
                      </div>
                    </div>
                  )}

                  {/* Action buttons for completed images */}
                  {item.status === "completed" && item.runId && (
                    <div className="flex gap-2">
                      <Link
                        to={`/runs/${item.runId}`}
                        className="flex-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-3 py-2 text-xs font-semibold hover:bg-cyan-500/30 transition-colors flex items-center justify-center gap-1"
                      >
                        <Eye size={14} />
                        View Details
                      </Link>
                      {item.overlayUrl && (
                        <a
                          href={item.overlayUrl}
                          download={`overlay_${item.runId}.jpg`}
                          className="rounded-lg bg-neutral-700/50 text-white border border-neutral-600 px-3 py-2 text-xs font-semibold hover:bg-neutral-600 transition-colors flex items-center justify-center"
                          title="Download overlay"
                        >
                          <Download size={14} />
                        </a>
                      )}
                    </div>
                  )}

                  {!processing && (
                    <button
                      onClick={() => removeFile(index)}
                      className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors flex items-center justify-center gap-2"
                    >
                      <X size={16} />
                      Remove
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

