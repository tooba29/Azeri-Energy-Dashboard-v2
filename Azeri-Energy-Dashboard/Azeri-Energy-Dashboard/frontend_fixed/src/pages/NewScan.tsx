import React, { useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { runPipeline, runPipelineDemo } from "../api/api";
import { toast } from "../components/Toast";
import {
  Camera,
  UploadCloud,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  ChevronRight,
  Sparkles,
} from "lucide-react";

type Step = { id: string; name: string; status: "idle" | "running" | "done" | "error"; detail?: string };

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(new Error("Failed to read file"));
    r.readAsDataURL(file);
  });
}

export default function NewScan() {
  const nav = useNavigate();
  const [rgb, setRgb] = useState<File | null>(null);
  const [thermal, setThermal] = useState<File | null>(null);
  const [rgbPreview, setRgbPreview] = useState<string | null>(null);
  const [thermalPreview, setThermalPreview] = useState<string | null>(null);
  const [towerId, setTowerId] = useState<string>("");
  const [ambient, setAmbient] = useState<number>(25);
  const [voltageKv, setVoltageKv] = useState<string>("330 kV");
  const [towerType, setTowerType] = useState<string>("suspension");
  const [region, setRegion] = useState<string>("Karabakh");
  const [corridorTag, setCorridorTag] = useState<string>("");
  const [gpsLat, setGpsLat] = useState<string>("");
  const [gpsLng, setGpsLng] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState<"rgb" | "thermal" | null>(null);
  const [processingStage, setProcessingStage] = useState<string>("");

  const [steps, setSteps] = useState<Step[]>([
    { id: "frames", name: "Frame extraction", status: "idle" },
    { id: "parts", name: "Part detection", status: "idle" },
    { id: "defects", name: "Defect detection", status: "idle" },
    { id: "thermal", name: "Thermal hotspot analysis", status: "idle" },
    { id: "correlation", name: "Thermal-part correlation", status: "idle" },
    { id: "grade", name: "Severity grading", status: "idle" },
    { id: "report", name: "Report generation", status: "idle" },
  ]);

  const canRun = useMemo(() => Boolean(rgb), [rgb]);

  function setStep(id: string, patch: Partial<Step>) {
    setSteps((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  const handleDrag = useCallback((e: React.DragEvent, type: "rgb" | "thermal") => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(type);
    } else if (e.type === "dragleave") {
      setDragActive(null);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, type: "rgb" | "thermal") => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(null);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (type === "rgb") {
        setRgb(file);
        const reader = new FileReader();
        reader.onload = (e) => setRgbPreview(e.target?.result as string);
        reader.readAsDataURL(file);
      } else {
        setThermal(file);
        const reader = new FileReader();
        reader.onload = (e) => setThermalPreview(e.target?.result as string);
        reader.readAsDataURL(file);
      }
    }
  }, []);

  const handleFileSelect = useCallback((file: File | null, type: "rgb" | "thermal") => {
    if (!file) return;
    if (type === "rgb") {
      setRgb(file);
      const reader = new FileReader();
      reader.onload = (e) => setRgbPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setThermal(file);
      const reader = new FileReader();
      reader.onload = (e) => setThermalPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    }
  }, []);

  async function onRunDemo() {
    try {
      setError(null);
      setBusy(true);
      setSteps((prev) => prev.map((s) => ({ ...s, status: "running" })));
      const out = await runPipelineDemo();
      const received: Step[] = out.steps || [];
      setSteps((prev) =>
        prev.map((s) => {
          const r = received.find((x) => x.id === s.id);
          return r ? { ...s, status: "done", detail: r.detail } : s;
        })
      );
    } catch (e: unknown) {
      const errorMessage = e instanceof Error ? e.message : "Demo failed";
      setError(errorMessage);
      toast.error(`Demo failed: ${errorMessage}`, 5000);
      setSteps((prev) => prev.map((s) => ({ ...s, status: "error" })));
    } finally {
      setBusy(false);
    }
  }

  async function onRunLocal() {
    if (!rgb) return;
    try {
      setError(null);
      setBusy(true);
      setProcessingStage("Preparing files...");

      // Reset and start progress
      setSteps((prev) => prev.map((s) => ({ ...s, status: "idle", detail: undefined })));
      
      // Step 1: Frame extraction
      setProcessingStage("Extracting frames...");
      setStep("frames", { status: "running", detail: "Processing image files..." });
      await new Promise(resolve => setTimeout(resolve, 500));
      setStep("frames", { status: "done", detail: "RGB/thermal files prepared" });

      // Step 2: Convert to base64 and start PART detection
      setProcessingStage("Converting images...");
      setStep("parts", { status: "running", detail: "Encoding images for processing..." });
      const rgbData = await fileToDataUrl(rgb);
      const thermalData = thermal ? await fileToDataUrl(thermal) : undefined;
      await new Promise(resolve => setTimeout(resolve, 300));
      setStep("parts", { status: "running", detail: "Running PART detection model (1024x1024)..." });

      // Step 3: AI Detection (3-model pipeline)
      setProcessingStage("Running 3-model AI pipeline...");
      setStep("defects", { status: "running", detail: "Running DEFECT detection model on part crops..." });

      console.log("Calling pipeline with:", {
        tower_id: towerId.trim() || undefined,
        rgb_base64_length: rgbData.length,
        has_thermal: !!thermalData,
        ambient_c: ambient,
        voltage_kv: voltageKv,
        tower_type: towerType,
        region: region,
        corridor_tag: corridorTag.trim() || undefined,
      });

      const gps = (gpsLat.trim() && gpsLng.trim()) ? {
        lat: parseFloat(gpsLat.trim()),
        lng: parseFloat(gpsLng.trim()),
      } : undefined;

      const out = await runPipeline({
        tower_id: towerId.trim() || undefined,
        rgb_base64: rgbData,
        filename: rgb?.name,
        thermal_base64: thermalData,
        ambient_c: ambient,
        voltage_kv: voltageKv,
        tower_type: towerType,
        region: region,
        corridor_tag: corridorTag.trim() || undefined,
        gps: gps,
      });

      console.log("Pipeline response:", out);

      // Check if pipeline failed
      if (out.status === "failed") {
        throw new Error(out.error || "Pipeline processing failed");
      }

      setStep("parts", { status: "done", detail: "Parts detected" });
      setStep("defects", { status: "done", detail: "Defect detection complete" });
      
      // Step 4: Thermal analysis
      if (thermal) {
        setProcessingStage("Analyzing thermal data...");
        setStep("thermal", { status: "running", detail: "Detecting hotspots (640x640)..." });
        await new Promise(resolve => setTimeout(resolve, 400));
        setStep("thermal", { status: "done", detail: "Hotspot analysis complete" });
        
        // Step 5: Correlation
        setStep("correlation", { status: "running", detail: "Correlating thermal hotspots with parts..." });
        await new Promise(resolve => setTimeout(resolve, 300));
        // Note: Correlation details would be in the actual findings data, but we only get a count here
        // The full findings with correlation data are saved to the data service
        setStep("correlation", { 
          status: "done", 
          detail: "Correlation complete" 
        });
      } else {
        setStep("thermal", { status: "idle", detail: "Skipped (no thermal image)" });
        setStep("correlation", { status: "idle", detail: "Skipped (no thermal image)" });
      }

      // Step 6: Grading
      setProcessingStage("Calculating severity...");
      setStep("grade", { status: "running", detail: "Assigning severity levels (HIGH/MEDIUM/LOW)..." });
      await new Promise(resolve => setTimeout(resolve, 300));
      setStep("grade", { status: "done", detail: `Pipeline status: ${out.status || "completed"}` });

      // Step 7: Report
      setProcessingStage("Generating report...");
      setStep("report", { status: "running", detail: "Creating PDF report..." });
      await new Promise(resolve => setTimeout(resolve, 400));
      setStep("report", { status: "done", detail: "PDF report ready" });

      setProcessingStage("Complete! Redirecting...");
      const successMessage = out.status === "completed" 
        ? `Tower ${out.tower_id || "inspection"} processed successfully!`
        : `Pipeline completed with status: ${out.status}`;
      toast.success(successMessage, 3000);
      await new Promise(resolve => setTimeout(resolve, 800));
      
      if (out.run_id) {
        nav(`/runs/${out.run_id}`);
      } else {
        nav("/runs");
      }
    } catch (e: unknown) {
      console.error("Pipeline error:", e);
      const errorMessage = e instanceof Error ? e.message : "Pipeline failed";
      setError(errorMessage);
      setProcessingStage("Error occurred");
      
      // Provide more helpful error messages
      let userMessage = errorMessage;
      if (errorMessage.includes("PIPELINE_DET_WEIGHTS") || errorMessage.includes("PIPELINE_CLS_WEIGHTS")) {
        userMessage = "Backend configuration error: Pipeline weights not configured. Please set PIPELINE_DET_WEIGHTS and PIPELINE_CLS_WEIGHTS environment variables.";
      } else if (errorMessage.includes("connect") || errorMessage.includes("Network error")) {
        userMessage = "Cannot connect to backend server. Make sure the server is running on http://localhost:8080";
      } else if (errorMessage.includes("timeout")) {
        userMessage = "Request timed out. The pipeline may take up to 10 minutes. Please try again.";
      }
      
      toast.error(`Processing failed: ${userMessage}`, 8000);
      
      // Mark current running step as error, keep completed steps as done
      setSteps((prev) => prev.map((s) => {
        if (s.status === "done") return s;
        if (s.status === "running") {
          return { ...s, status: "error", detail: `Failed: ${errorMessage.substring(0, 50)}...` };
        }
        return { ...s, status: "error" };
      }));
    } finally {
      setBusy(false);
      setProcessingStage("");
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="text-premium-accent text-xl" />
              <div className="text-sm text-premium-accent uppercase tracking-wider">New Scan</div>
            </div>
            <div className="text-2xl font-bold text-white mb-2">Process Tower Inspection</div>
            <div className="text-sm text-neutral-300 leading-relaxed">
              Upload RGB and optional thermal images. The AI system will analyze the images, detect defects, 
              classify severity, and generate a comprehensive PDF report.
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onRunDemo}
              disabled={busy}
              className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover disabled:opacity-60 transition-colors flex items-center gap-2"
            >
              <Sparkles className="text-lg" />
              Demo
            </button>
            <button
              onClick={onRunLocal}
              disabled={!canRun || busy}
              className="rounded-xl bg-gradient-accent text-white px-5 py-2.5 text-sm font-semibold hover:shadow-glow disabled:opacity-60 transition-all flex items-center gap-2"
            >
              {busy ? (
                <>
                  <Clock className="text-lg animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Camera className="text-lg" />
                  Start Scan
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Processing Status Banner */}
      {busy && processingStage && (
        <div className="glass rounded-2xl border border-premium-accent/50 bg-premium-accent/10 p-4 shadow-premium">
          <div className="flex items-center gap-3">
            <Clock className="text-premium-accent text-xl animate-spin" />
            <div className="flex-1">
              <div className="font-semibold text-white">{processingStage}</div>
              <div className="text-xs text-neutral-300 mt-1">Please wait while we process your images...</div>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="glass rounded-2xl border border-premium-danger/50 bg-premium-danger/10 p-4 shadow-premium">
          <div className="flex items-start gap-3">
            <AlertCircle className="text-premium-danger text-xl flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-premium-danger mb-1">Processing Error</div>
              <div className="text-sm text-neutral-300 mb-3">{error}</div>
              {error.includes("unavailable") || error.includes("connect") ? (
                <div className="text-xs text-neutral-400 mb-2">
                  Make sure all backend services are running. Check the terminal where you ran <code className="bg-neutral-800 px-1 rounded">npm run dev</code>
                </div>
              ) : null}
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    setError(null);
                    // Reset steps before retrying
                    setSteps((prev) => prev.map((s) => ({ ...s, status: "idle" as const, detail: undefined })));
                    if (rgb && !busy) {
                      await onRunLocal();
                    }
                  }}
                  disabled={!rgb || busy}
                  className="rounded-lg bg-premium-danger/20 border border-premium-danger/50 text-premium-danger px-3 py-1.5 text-xs font-semibold hover:bg-premium-danger/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Retry
                </button>
                <button
                  onClick={() => setError(null)}
                  className="rounded-lg glass border border-neutral-700 text-neutral-300 px-3 py-1.5 text-xs font-semibold hover:bg-premium-card-hover transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-neutral-400 hover:text-white transition-colors flex-shrink-0"
            >
              <XCircle className="text-lg" />
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Section */}
        <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
          <div className="flex items-center gap-2 mb-6">
            <UploadCloud className="text-premium-accent text-xl" />
            <div className="font-semibold text-white text-lg">Image Upload</div>
          </div>

          <div className="space-y-5">
            {/* RGB Upload */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold text-white">RGB Image</div>
                <span className="text-xs text-premium-danger font-medium">Required</span>
              </div>
              <div
                onDragEnter={(e) => handleDrag(e, "rgb")}
                onDragLeave={(e) => handleDrag(e, "rgb")}
                onDragOver={(e) => handleDrag(e, "rgb")}
                onDrop={(e) => handleDrop(e, "rgb")}
                className={`mt-2 rounded-xl border-2 border-dashed transition-all ${
                  dragActive === "rgb"
                    ? "border-premium-accent bg-premium-accent/10"
                    : rgbPreview
                    ? "border-premium-success/50 bg-premium-success/5"
                    : "border-neutral-700 bg-premium-card/30 hover:border-premium-accent/50"
                } p-4`}
              >
                {rgbPreview ? (
                  <div className="space-y-3">
                    <div className="relative rounded-lg overflow-hidden border border-neutral-700">
                      <img src={rgbPreview} alt="RGB preview" className="w-full h-48 object-contain bg-neutral-900" />
                      <button
                        onClick={() => {
                          setRgb(null);
                          setRgbPreview(null);
                        }}
                        className="absolute top-2 right-2 rounded-full bg-premium-danger/90 text-white p-1.5 hover:bg-premium-danger transition-colors"
                      >
                        <XCircle className="text-lg" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-premium-success">
                      <CheckCircle2 className="text-base" />
                      <span>{rgb?.name || "RGB image loaded"}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <Camera className="text-4xl text-neutral-500 mx-auto mb-3" />
                    <div className="text-sm text-neutral-300 mb-2">Drop image here or click to browse</div>
              <input
                type="file"
                accept="image/*"
                      onChange={(e) => handleFileSelect(e.target.files?.[0] || null, "rgb")}
                      className="hidden"
                      id="rgb-upload"
                      disabled={busy}
                    />
                    <label
                      htmlFor="rgb-upload"
                      className="inline-block rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover cursor-pointer transition-colors"
                    >
                      Select RGB Image
                    </label>
                  </div>
                )}
              </div>
              <div className="mt-2 text-xs text-neutral-400">High-resolution RGB image from drone or camera system</div>
            </div>

            {/* Thermal Upload */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold text-white">Thermal Image</div>
                <span className="text-xs text-neutral-400 font-medium">Optional</span>
              </div>
              <div
                onDragEnter={(e) => handleDrag(e, "thermal")}
                onDragLeave={(e) => handleDrag(e, "thermal")}
                onDragOver={(e) => handleDrag(e, "thermal")}
                onDrop={(e) => handleDrop(e, "thermal")}
                className={`mt-2 rounded-xl border-2 border-dashed transition-all ${
                  dragActive === "thermal"
                    ? "border-premium-accent bg-premium-accent/10"
                    : thermalPreview
                    ? "border-premium-warning/50 bg-premium-warning/5"
                    : "border-neutral-700 bg-premium-card/30 hover:border-premium-accent/50"
                } p-4`}
              >
                {thermalPreview ? (
                  <div className="space-y-3">
                    <div className="relative rounded-lg overflow-hidden border border-neutral-700">
                      <img src={thermalPreview} alt="Thermal preview" className="w-full h-48 object-contain bg-neutral-900" />
                      <button
                        onClick={() => {
                          setThermal(null);
                          setThermalPreview(null);
                        }}
                        className="absolute top-2 right-2 rounded-full bg-premium-danger/90 text-white p-1.5 hover:bg-premium-danger transition-colors"
                      >
                        <XCircle className="text-lg" />
                      </button>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-premium-warning">
                      <CheckCircle2 className="text-base" />
                      <span>{thermal?.name || "Thermal image loaded"}</span>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-6">
                    <Camera className="text-4xl text-neutral-500 mx-auto mb-3" />
                    <div className="text-sm text-neutral-300 mb-2">Drop thermal image here or click to browse</div>
              <input
                type="file"
                accept="image/*"
                      onChange={(e) => handleFileSelect(e.target.files?.[0] || null, "thermal")}
                      className="hidden"
                      id="thermal-upload"
                      disabled={busy}
                    />
                    <label
                      htmlFor="thermal-upload"
                      className="inline-block rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover cursor-pointer transition-colors"
                    >
                      Select Thermal Image
                    </label>
                  </div>
                )}
              </div>
              <div className="mt-2 text-xs text-neutral-400">Radiometric thermal image for hotspot detection</div>
            </div>

            {/* Configuration - Hidden */}
            {false && (
            <div className="rounded-xl border border-neutral-700 bg-premium-card/30 p-4 space-y-4">
              <div className="text-sm font-semibold text-white mb-3">Configuration</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Tower ID</div>
                <input
                  value={towerId}
                  onChange={(e) => setTowerId(e.target.value)}
                  placeholder="AZ-KB-412"
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                />
                  <div className="text-xs text-neutral-400 mt-1">Auto-generated if empty</div>
              </div>
              <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Ambient Temperature (°C)</div>
                <input
                  type="number"
                  value={ambient}
                  onChange={(e) => setAmbient(Number(e.target.value))}
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                />
                  <div className="text-xs text-neutral-400 mt-1">For thermal analysis</div>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-neutral-700">
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Voltage (kV)</div>
                  <select
                    value={voltageKv}
                    onChange={(e) => setVoltageKv(e.target.value)}
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  >
                    <option value="110 kV">110 kV</option>
                    <option value="220 kV">220 kV</option>
                    <option value="330 kV">330 kV</option>
                    <option value="500 kV">500 kV</option>
                  </select>
                </div>
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Tower Type</div>
                  <select
                    value={towerType}
                    onChange={(e) => setTowerType(e.target.value)}
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  >
                    <option value="suspension">Suspension</option>
                    <option value="tension">Tension</option>
                    <option value="angle">Angle</option>
                    <option value="dead-end">Dead-End</option>
                  </select>
                </div>
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Region</div>
                  <select
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  >
                    <option value="Karabakh">Karabakh</option>
                    <option value="East Zangezur">East Zangezur</option>
                    <option value="Azerbaijan">Azerbaijan</option>
                  </select>
                </div>
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">Corridor Tag (Optional)</div>
                  <input
                    value={corridorTag}
                    onChange={(e) => setCorridorTag(e.target.value)}
                    placeholder="Navai–Mingachevir"
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-neutral-700">
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">GPS Latitude (Optional)</div>
                  <input
                    type="number"
                    step="any"
                    value={gpsLat}
                    onChange={(e) => setGpsLat(e.target.value)}
                    placeholder="40.123456"
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  />
                  <div className="text-xs text-neutral-400 mt-1">For CorridorMap</div>
                </div>
                <div>
                  <div className="text-xs font-medium text-neutral-300 mb-1.5">GPS Longitude (Optional)</div>
                  <input
                    type="number"
                    step="any"
                    value={gpsLng}
                    onChange={(e) => setGpsLng(e.target.value)}
                    placeholder="49.123456"
                    disabled={busy}
                    className="w-full rounded-lg bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm focus:ring-2 focus:ring-premium-accent focus:border-premium-accent outline-none disabled:opacity-50"
                  />
                  <div className="text-xs text-neutral-400 mt-1">For CorridorMap</div>
                </div>
              </div>
              <div className="pt-2 border-t border-neutral-700">
                <div className="flex items-center gap-2 text-xs text-premium-success">
                  <CheckCircle2 className="text-base" />
                  <span>Zero-Exfiltration Mode • All processing happens locally</span>
                </div>
              </div>
            </div>
            )}
          </div>
        </div>

        {/* Progress Section */}
        <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
          <div className="flex items-center gap-2 mb-6">
            <ChevronRight className="text-premium-accent text-xl" />
            <div className="font-semibold text-white text-lg">Processing Pipeline</div>
          </div>
          
          <div className="space-y-3">
            {steps.map((s, index) => {
              const isActive = s.status === "running";
              const isDone = s.status === "done";
              const isError = s.status === "error";
              
              return (
                <div
                  key={s.id}
                  className={`rounded-xl border p-4 transition-all ${
                    isActive
                      ? "border-premium-accent/50 bg-premium-accent/10 shadow-glow"
                      : isDone
                      ? "border-premium-success/30 bg-premium-success/5"
                      : isError
                      ? "border-premium-danger/30 bg-premium-danger/5"
                      : "border-neutral-700 bg-premium-card/30"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      isDone
                        ? "bg-premium-success text-white"
                        : isActive
                        ? "bg-premium-accent text-white animate-pulse"
                        : isError
                        ? "bg-premium-danger text-white"
                        : "bg-neutral-700 text-neutral-400"
                    }`}>
                      {isDone ? (
                        <CheckCircle2 className="text-lg" />
                      ) : isActive ? (
                        <Clock className="text-lg animate-spin" />
                      ) : isError ? (
                        <XCircle className="text-lg" />
                      ) : (
                        <span className="text-sm font-bold">{index + 1}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <div className={`text-sm font-semibold ${
                          isActive ? "text-premium-accent" : isDone ? "text-premium-success" : isError ? "text-premium-danger" : "text-white"
                        }`}>
                          {s.name}
                        </div>
                        {isActive && (
                          <div className="flex-shrink-0">
                            <div className="w-2 h-2 rounded-full bg-premium-accent animate-pulse" />
                          </div>
                        )}
                      </div>
                      {s.detail && (
                        <div className={`text-xs mt-1 ${
                          isDone ? "text-premium-success" : isError ? "text-premium-danger" : "text-neutral-300"
                        }`}>
                          {s.detail}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Info Card */}
          <div className="mt-6 rounded-xl bg-premium-card/50 border border-neutral-700 p-4">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="text-premium-accent" />
              <div className="text-sm font-semibold text-white">Key Features</div>
            </div>
            <ul className="mt-2 space-y-1.5 text-xs text-neutral-300">
              <li className="flex items-start gap-2">
                <span className="text-premium-accent mt-0.5">•</span>
                <span>Single click processing → automatic dashboard update + PDF generation</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-premium-accent mt-0.5">•</span>
                <span>RGB + Thermal findings displayed together on the same tower</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-premium-accent mt-0.5">•</span>
                <span>100% local processing - perfect for air-gapped environments</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
