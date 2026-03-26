import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { API_BASE, getTower, getFindings, reportUrl, type Tower, type Finding } from "../api/api";
import StatusBadge from "../components/StatusBadge";
import ImageAnnotator from "../components/ImageAnnotator";
import LoadingSpinner from "../components/LoadingSpinner";
import { HiOutlineSparkles } from "react-icons/hi";
import { formatDetectionLabel } from "../utils/formatLabels";

export default function TowerDetail() {
  const { id } = useParams();
  const [tower, setTower] = useState<Tower | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"RGB" | "Thermal">("RGB");

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.all([getTower(id), getFindings(id)])
      .then(([t, f]) => {
        setTower(t);
        setFindings(f);
      })
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" text="Loading tower details..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass rounded-2xl border border-premium-danger/50 p-6 text-premium-danger shadow-premium">
        <div className="font-semibold mb-2">Error Loading Tower</div>
        <div className="text-sm">{error}</div>
      </div>
    );
  }

  if (!tower) {
    return (
      <div className="glass rounded-2xl border border-neutral-800 p-6 text-white">
        <div className="font-semibold">Tower not found</div>
        <div className="text-sm text-neutral-400 mt-2">The requested tower could not be found.</div>
      </div>
    );
  }

  const hasThermal = tower.thermal_image && tower.thermal_image !== null && tower.thermal_image !== "null";
  const rgbUrl = `${API_BASE}${tower.hero_image}`;
  const thermalUrl = hasThermal ? `${API_BASE}${tower.thermal_image}` : null;
  const heroUrl = view === "Thermal" && thermalUrl ? thermalUrl : rgbUrl;
  const viewFindings = view === "Thermal" 
    ? findings.filter((f) => f.source === "Thermal") 
    : findings.filter((f) => f.source === "RGB" || !f.source);

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl border border-neutral-800 p-5 shadow-premium">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm text-neutral-400">{tower.corridor}</div>
            <div className="mt-1 text-xl font-semibold text-white">{tower.id}</div>
            <div className="mt-2 flex items-center gap-2">
              <StatusBadge status={tower.status} />
              <span className="text-sm text-neutral-300">
                AI confidence: {Math.round(tower.ai_confidence * 100)}%
              </span>
            </div>
            {tower.image_dimensions && (
              <div className="mt-2 text-xs text-neutral-400">
                Image dimensions: {tower.image_dimensions.width}×{tower.image_dimensions.height}px
              </div>
            )}
            <div className="mt-2 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-neutral-800 border border-neutral-700 px-3 py-1 text-neutral-200">
                {tower.voltage_kv ? `${tower.voltage_kv} kV` : "Voltage N/A"}
              </span>
              <span className="rounded-full bg-neutral-800 border border-neutral-700 px-3 py-1 text-neutral-200">
                {tower.tower_type || "Type N/A"}
              </span>
              <span className="rounded-full bg-neutral-800 border border-neutral-700 px-3 py-1 text-neutral-200">
                {tower.region || "Region N/A"}
              </span>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <a
              href={reportUrl(tower.id)}
              className="rounded-xl bg-gradient-accent text-white px-4 py-2 text-sm font-semibold hover:shadow-glow transition-all"
            >
              Download PDF Report
            </a>
            <button
              className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors"
              onClick={() => {
                const data = {
                  tower,
                  findings,
                  export_date: new Date().toISOString(),
                  report_metadata: {
                    tower_id: tower.id,
                    findings_count: findings.length,
                    status: tower.status,
                    ai_confidence: tower.ai_confidence,
                  }
                };
                const json = JSON.stringify(data, null, 2);
                const blob = new Blob([json], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `tower_${tower.id}_export_${new Date().toISOString().split('T')[0]}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }}
            >
              Export JSON
            </button>
            <button
              className="rounded-xl glass border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors"
              onClick={() => alert("Import detection results from external analysis tools")}
            >
              Import Results
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="mb-3 flex items-center gap-2">
            <button
              onClick={() => setView("RGB")}
              className={
                "rounded-xl px-3 py-2 text-sm font-semibold border transition-all " +
                (view === "RGB" ? "bg-gradient-accent text-white border-premium-accent shadow-glow" : "glass border-neutral-700 text-neutral-300 hover:bg-premium-card-hover")
              }
            >
              RGB
            </button>
            <button
              disabled={!hasThermal}
              onClick={() => setView("Thermal")}
              className={
                "rounded-xl px-3 py-2 text-sm font-semibold border transition-all disabled:opacity-50 disabled:cursor-not-allowed " +
                (view === "Thermal" ? "bg-gradient-accent text-white border-premium-accent shadow-glow" : "glass border-neutral-700 text-neutral-300 hover:bg-premium-card-hover")
              }
            >
              Thermal
            </button>
            {view === "RGB" && (
              <div className="text-xs text-neutral-400">RGB view shows all RGB findings.</div>
            )}
            {view === "Thermal" && hasThermal && (
              <div className="text-xs text-neutral-400">Thermal view shows thermal-only findings.</div>
            )}
            {view === "Thermal" && !hasThermal && (
              <div className="text-xs text-amber-400">No thermal image available for this tower.</div>
            )}
          </div>

          <div className="glass rounded-2xl border border-neutral-800 p-4 shadow-premium bg-neutral-900/50">
            <ImageAnnotator 
              src={heroUrl} 
              findings={viewFindings}
              key={`${heroUrl}-${view}`}
            />
          </div>
          <div className="mt-3 text-xs text-neutral-400">
            Boxes are drawn from findings JSON (same data used to generate the PDF).
            {view === "RGB" && (
              <span className="ml-2">Showing {viewFindings.length} RGB findings.</span>
            )}
            {view === "Thermal" && (
              <span className="ml-2">Showing {viewFindings.length} thermal findings.</span>
            )}
          </div>
        </div>

        <div className="glass rounded-2xl border border-neutral-800 p-4 shadow-premium">
          <div className="flex items-center justify-between gap-2">
            <div className="font-semibold text-white">Findings</div>
            <div className="text-xs text-neutral-400">Showing: {view}</div>
          </div>
          <div className="mt-2 space-y-3 max-h-[600px] overflow-y-auto">
            {viewFindings.length ? (
              viewFindings.map((f) => {
                // Extract annotation ID from notes if present
                const annotationIdMatch = f.notes?.match(/annotation ID (\d+)/i);
                const annotationId = annotationIdMatch ? annotationIdMatch[1] : null;
                
                return (
                  <div key={f.id} className="rounded-xl border border-neutral-700 bg-premium-card/50 p-3 hover:bg-premium-card/70 transition-colors">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="text-sm font-semibold text-white">{formatDetectionLabel(f.label)}</div>
                      <span className="rounded-full border border-neutral-600 bg-neutral-800 px-2 py-1 text-xs font-semibold text-neutral-300">
                        {f.severity}
                      </span>
                    </div>
                    <div className="text-xs text-neutral-400 mb-1">
                      Source: {f.source} • conf {Math.round(f.confidence * 100)}%
                    </div>
                    {annotationId && (
                      <div className="text-xs text-neutral-300 mt-1">
                        Automated detection (annotation ID {annotationId})
                      </div>
                    )}
                    {!annotationId && f.notes && (
                      <div className="text-xs text-neutral-300 mt-1">{f.notes}</div>
                    )}
                    
                    {/* Thermal-Part Correlation Display */}
                    {f.correlated_part && (
                      <div className="mt-2 p-2 rounded-lg bg-premium-accent/10 border border-premium-accent/30">
                        <div className="flex items-center gap-2 mb-1">
                          <HiOutlineSparkles className="text-premium-accent text-xs" />
                          <span className="text-xs font-semibold text-premium-accent">Actionable Insight</span>
                        </div>
                        <div className="text-xs text-neutral-300">
                          Hotspot correlated with: <span className="font-semibold text-white">{f.correlated_part.label}</span>
                        </div>
                        <div className="text-xs text-neutral-400 mt-1">
                          Distance: {f.correlated_part.distance_pixels.toFixed(1)}px • 
                          Part confidence: {Math.round(f.correlated_part.confidence * 100)}%
                        </div>
                      </div>
                    )}
                    
                    {f.image_dimensions && (
                      <div className="mt-1 text-xs text-neutral-400">
                        Image: {f.image_dimensions.width}×{f.image_dimensions.height}px
                      </div>
                    )}
                    {f.detection_area_percent !== undefined && (
                      <div className="mt-1 text-xs text-neutral-400">
                        Area: {f.detection_area_percent.toFixed(2)}% of image
                      </div>
                    )}
                    {f.grade ? <div className="mt-1 text-xs text-neutral-400">Rust grade: {f.grade}</div> : null}
                    {f.distance_m ? <div className="mt-1 text-xs text-neutral-400">Distance: {f.distance_m}m</div> : null}
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-neutral-400">No defects detected.</div>
            )}
          </div>

          <div className="mt-4 rounded-xl bg-premium-card/50 border border-neutral-700 p-3">
            <div className="text-sm font-semibold text-white">Recommended action</div>
            <div className="mt-1 text-xs text-neutral-300">
              {tower.status === "REQUIRES_INSPECTION"
                ? "Dispatch inspection crew for confirmed repair scope. Prioritize thermal hotspot / broken insulator."
                : tower.status === "MONITOR"
                ? "Schedule follow-up scan in 7–14 days and track progression."
                : "No immediate action needed. Continue routine scanning cadence."}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
