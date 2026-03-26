import React, { useEffect, useState, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import { getRuns, type Run } from "../api/api";
import { toast } from "../components/Toast";
import {
  Map,
  Filter,
  Search,
  ChevronRight,
  ChevronLeft,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Clock,
  ExternalLink,
  ScanSearch,
  Layers,
  X,
} from "lucide-react";

import "leaflet/dist/leaflet.css";

const DUBAI_CENTER: [number, number] = [25.2048, 55.2708];
const DEFAULT_ZOOM = 10;

// Fixed drone run locations
const DRONE_RUN_LOCATIONS: Array<{ lat: number; lng: number; label: string }> = [
  { lat: 40.187722, lng: 49.433331, label: "First Drone Run" },
  { lat: 40.499472, lng: 49.729306, label: "Second Drone Run" }, // 40°29'58.1"N 49°43'45.5"E converted
];

function createDroneRunIcon(): L.DivIcon {
  return L.divIcon({
    className: "drone-run-marker",
    html: `<div style="
      width: 24px;
      height: 24px;
      background-color: #8b5cf6;
      border: 3px solid white;
      border-radius: 50%;
      box-shadow: 0 2px 6px rgba(0,0,0,0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: bold;
      color: white;
    ">✈</div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

function isValidGps(lat: number, lng: number): boolean {
  return typeof lat === "number" && typeof lng === "number" && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180;
}

function getRunGps(run: Run): { lat: number; lng: number } | null {
  const g = run.gps ?? (run.metadata as { gps?: { lat: number; lng: number } } | undefined)?.gps;
  if (!g || !isValidGps(g.lat, g.lng)) return null;
  return { lat: g.lat, lng: g.lng };
}

function runTime(run: Run): number {
  const t = run.created_at ?? run.timestamp;
  return t ? new Date(t).getTime() : 0;
}

function confidencePct(run: Run): number | null {
  const v = run.avg_confidence ?? run.ai_confidence;
  return typeof v === "number" ? Math.round(v * 100) : null;
}

function markerColor(run: Run): string {
  if (run.status === "failed") return "#ef4444";
  if ((run.must_review_count ?? 0) > 0) return "#f59e0b";
  if (run.status === "completed") return "#10b981";
  return "#6b7280";
}

function createRunIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: "run-marker",
    html: `<div style="
      width: 20px;
      height: 20px;
      background-color: ${color};
      border: 2px solid white;
      border-radius: 50%;
      box-shadow: 0 1px 4px rgba(0,0,0,0.3);
    "></div>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

function FitBounds({
  runs,
  deps,
}: {
  runs: Array<Run & { _gps: { lat: number; lng: number } }>;
  deps: unknown[];
}) {
  const map = useMap();
  useEffect(() => {
    if (runs.length === 0) return;
    const bounds = L.latLngBounds(runs.map((r) => [r._gps.lat, r._gps.lng] as [number, number]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  }, [runs.length, map, deps]);
  return null;
}

function FlyTo({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo([lat, lng], map.getZoom(), { duration: 0.4 });
  }, [lat, lng, map]);
  return null;
}

type RunWithGps = Run & { _gps: { lat: number; lng: number }; _runId: string };

export default function CorridorMap() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [needsReviewOnly, setNeedsReviewOnly] = useState(false);
  const [dateRange, setDateRange] = useState<"7" | "14" | "30" | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedRun, setSelectedRun] = useState<RunWithGps | null>(null);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    setLoading(true);
    setError(null);
    getRuns()
      .then(setRuns)
      .catch((e) => {
        const msg = e instanceof Error ? e.message : "Failed to load runs";
        setError(msg);
        toast.error(msg, 5000);
      })
      .finally(() => setLoading(false));
  }, []);

  const runsWithGps = useMemo((): RunWithGps[] => {
    return runs
      .map((r) => {
        const gps = getRunGps(r);
        if (!gps) return null;
        return { ...r, _gps: gps, _runId: r.run_id ?? r.id } as RunWithGps;
      })
      .filter((r): r is RunWithGps => r != null);
  }, [runs]);

  const now = Date.now();
  const dateCutoff = useMemo(() => {
    if (dateRange === "all") return 0;
    const d = Number(dateRange);
    return now - d * 24 * 60 * 60 * 1000;
  }, [dateRange, now]);

  const filtered = useMemo(() => {
    let list = runsWithGps;
    if (statusFilter !== "all") list = list.filter((r) => r.status === statusFilter);
    if (needsReviewOnly) list = list.filter((r) => (r.must_review_count ?? 0) > 0);
    if (dateCutoff > 0) list = list.filter((r) => runTime(r) >= dateCutoff);
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter((r) => {
        const id = (r.run_id ?? r.id).toLowerCase();
        const tid = (r.tower_id ?? "").toLowerCase();
        return id.includes(q) || tid.includes(q);
      });
    }
    return [...list].sort((a, b) => runTime(b) - runTime(a));
  }, [runsWithGps, statusFilter, needsReviewOnly, dateCutoff, searchQuery]);

  const stats = useMemo(() => {
    const total = filtered.length;
    const needsReview = filtered.reduce((s, r) => s + (r.must_review_count ?? 0), 0);
    const failed = filtered.filter((r) => r.status === "failed").length;
    return { total, needsReview, failed };
  }, [filtered]);

  const listRuns = filtered.slice(0, 20);

  const handleSelectRun = useCallback((run: RunWithGps) => {
    setSelectedRun(run);
  }, []);

  const transition = reduceMotion ? { duration: 0 } : { duration: 0.2 };

  if (loading) {
    return (
      <div className="h-[calc(100vh-3.5rem)] flex">
        <div className="flex-1 bg-neutral-900 animate-pulse" />
        <div className="w-80 border-l border-neutral-800 bg-[#0f1419] p-4 space-y-4">
          <div className="h-6 w-32 bg-neutral-700/50 rounded animate-pulse" />
          <div className="h-10 w-full bg-neutral-700/40 rounded animate-pulse" />
          <div className="h-16 w-full bg-neutral-700/40 rounded animate-pulse" />
          <div className="h-24 w-full bg-neutral-700/40 rounded animate-pulse" />
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3.5rem)] flex relative">
      <div className="flex-1 relative z-0">
        <MapContainer
          center={runsWithGps.length ? [runsWithGps[0]._gps.lat, runsWithGps[0]._gps.lng] : DUBAI_CENTER}
          zoom={runsWithGps.length ? 12 : DEFAULT_ZOOM}
          className="h-full w-full"
          style={{ background: "#1a2332" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          {(runsWithGps.length > 0 || DRONE_RUN_LOCATIONS.length > 0) && (
            <FitBounds
              runs={[
                ...runsWithGps,
                ...DRONE_RUN_LOCATIONS.map((loc, idx) => ({
                  id: `drone-run-${idx}`,
                  _gps: { lat: loc.lat, lng: loc.lng },
                  _runId: loc.label,
                })) as any
              ]}
              deps={[runsWithGps, DRONE_RUN_LOCATIONS]}
            />
          )}
          {selectedRun && (
            <FlyTo lat={selectedRun._gps.lat} lng={selectedRun._gps.lng} />
          )}
          {/* Fixed drone run locations */}
          {DRONE_RUN_LOCATIONS.map((location, idx) => (
            <Marker
              key={`drone-run-${idx}`}
              position={[location.lat, location.lng]}
              icon={createDroneRunIcon()}
            >
              <Popup>
                <div className="text-sm text-neutral-800 min-w-[160px]">
                  <div className="font-semibold text-purple-600">{location.label}</div>
                  <div className="text-xs text-neutral-500 mt-1">
                    {location.lat.toFixed(6)}, {location.lng.toFixed(6)}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
          {/* Dynamic run markers */}
          {filtered.map((run) => (
            <Marker
              key={run.id}
              position={[run._gps.lat, run._gps.lng]}
              icon={createRunIcon(markerColor(run))}
              eventHandlers={{
                click: () => handleSelectRun(run),
              }}
            >
              <Popup>
                <div className="text-sm text-neutral-800 min-w-[140px]">
                  <div className="font-semibold truncate" title={run._runId}>
                    {run._runId}
                  </div>
                  <div className="text-xs text-neutral-500 mt-1">
                    {run.status} &bull; {(run.created_at ?? run.timestamp) ? new Date(run.created_at ?? run.timestamp).toLocaleDateString() : "—"}
                  </div>
                  <Link
                    to={`/runs/${run._runId}`}
                    className="mt-2 inline-block text-xs font-medium text-cyan-600 hover:text-cyan-800"
                  >
                    View Run
                  </Link>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      <AnimatePresence>
        {panelOpen ? (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 320, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={transition}
            className="flex flex-col w-80 border-l border-neutral-800 bg-[#0f1419] overflow-hidden shrink-0 fixed right-0 top-14 bottom-0 z-50 sm:relative sm:top-0 sm:z-auto"
          >
            <div className="p-4 border-b border-neutral-800 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <Layers size={18} className="text-cyan-400" />
                Corridor Map
              </h2>
              <button
                type="button"
                onClick={() => setPanelOpen(false)}
                className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                aria-label="Collapse panel"
              >
                <ChevronRight size={18} />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {runsWithGps.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-6 text-center"
                >
                  <Map className="mx-auto text-neutral-500 mb-3" size={40} />
                  <p className="text-sm text-neutral-400 mb-2">No GPS-tagged runs yet.</p>
                  <p className="text-xs text-neutral-500 mb-4">
                    Runs will appear here once metadata.gps is present in run.json.
                  </p>
                  <Link
                    to="/new-scan"
                    className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-4 py-2 text-sm font-semibold hover:bg-cyan-500/30 transition-colors"
                  >
                    <ScanSearch size={16} />
                    New Scan
                  </Link>
                </motion.div>
              ) : (
                <>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs font-medium text-neutral-400 uppercase tracking-wider">
                      <Filter size={14} />
                      Filters
                    </div>
                    <select
                      value={statusFilter}
                      onChange={(e) => setStatusFilter(e.target.value)}
                      className="w-full rounded-lg bg-neutral-800 border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-cyan-500/50"
                    >
                      <option value="all">All status</option>
                      <option value="completed">Completed</option>
                      <option value="processing">Processing</option>
                      <option value="failed">Failed</option>
                      <option value="pending">Pending</option>
                    </select>
                    <label className="flex items-center gap-2 cursor-pointer text-sm text-neutral-300">
                      <input
                        type="checkbox"
                        checked={needsReviewOnly}
                        onChange={(e) => setNeedsReviewOnly(e.target.checked)}
                        className="rounded border-neutral-600 bg-neutral-800 text-cyan-500 focus:ring-cyan-500/50"
                      />
                      Needs review only
                    </label>
                    <div className="flex gap-2 flex-wrap">
                      {(["7", "14", "30", "all"] as const).map((d) => (
                        <button
                          key={d}
                          type="button"
                          onClick={() => setDateRange(d)}
                          className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                            dateRange === d
                              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50"
                              : "bg-neutral-800 text-neutral-400 border border-neutral-700 hover:bg-neutral-700"
                          }`}
                        >
                          {d === "all" ? "All" : `${d}d`}
                        </button>
                      ))}
                    </div>
                    <div className="relative">
                      <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-500" size={16} />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search run ID / tower ID..."
                        className="w-full rounded-lg bg-neutral-800 border border-neutral-700 text-white pl-9 pr-3 py-2 text-sm placeholder-neutral-500 outline-none focus:ring-2 focus:ring-cyan-500/50"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: reduceMotion ? 0 : 0.05 }}
                      className="rounded-lg bg-neutral-800/80 border border-neutral-700 p-2 text-center"
                    >
                      <div className="text-lg font-bold text-white">{stats.total}</div>
                      <div className="text-[10px] text-neutral-500 uppercase">Mapped</div>
                    </motion.div>
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: reduceMotion ? 0 : 0.08 }}
                      className="rounded-lg bg-neutral-800/80 border border-neutral-700 p-2 text-center"
                    >
                      <div className="text-lg font-bold text-amber-400">{stats.needsReview}</div>
                      <div className="text-[10px] text-neutral-500 uppercase">Needs review</div>
                    </motion.div>
                    <motion.div
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: reduceMotion ? 0 : 0.11 }}
                      className="rounded-lg bg-neutral-800/80 border border-neutral-700 p-2 text-center"
                    >
                      <div className="text-lg font-bold text-red-400">{stats.failed}</div>
                      <div className="text-[10px] text-neutral-500 uppercase">Failed</div>
                    </motion.div>
                  </div>

                  {selectedRun && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="rounded-xl border border-cyan-500/40 bg-cyan-500/10 p-4"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-cyan-300 uppercase">Selected</span>
                        <button
                          type="button"
                          onClick={() => setSelectedRun(null)}
                          className="p-1 rounded text-neutral-400 hover:text-white"
                          aria-label="Clear selection"
                        >
                          <X size={14} />
                        </button>
                      </div>
                      <div className="font-mono text-sm text-white truncate" title={selectedRun._runId}>
                        {selectedRun._runId}
                      </div>
                      <div className="text-xs text-neutral-400 mt-1">
                        {selectedRun.status} &bull; {(selectedRun.must_review_count ?? 0) > 0 ? `${selectedRun.must_review_count} to review` : ""}
                      </div>
                      <Link
                        to={`/runs/${selectedRun._runId}`}
                        className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-cyan-400 hover:text-cyan-300"
                      >
                        View Run
                        <ExternalLink size={14} />
                      </Link>
                    </motion.div>
                  )}

                  <div>
                    <div className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">
                      Runs ({listRuns.length})
                    </div>
                    <ul className="space-y-1">
                      {listRuns.map((run) => {
                        const isSelected = selectedRun?.id === run.id;
                        const pct = confidencePct(run);
                        return (
                          <motion.li
                            key={run.id}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            whileHover={reduceMotion ? undefined : { backgroundColor: "rgba(55, 65, 81, 0.5)" }}
                            className={`rounded-lg border px-3 py-2 cursor-pointer transition-colors ${
                              isSelected ? "border-cyan-500/50 bg-cyan-500/10" : "border-neutral-700 bg-neutral-800/50 hover:bg-neutral-800"
                            }`}
                            onClick={() => handleSelectRun(run)}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span
                                className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border ${
                                  run.status === "completed"
                                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                                    : run.status === "failed"
                                    ? "bg-red-500/20 text-red-400 border-red-500/50"
                                    : run.status === "processing"
                                    ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                                    : "bg-neutral-500/20 text-neutral-400 border-neutral-500/50"
                                }`}
                              >
                                {run.status === "processing" && <Clock size={10} className="animate-spin" />}
                                {run.status === "failed" && <XCircle size={10} />}
                                {run.status === "completed" && <CheckCircle2 size={10} />}
                                {run.status}
                              </span>
                              <span className="text-[10px] text-neutral-500">
                                {(run.must_review_count ?? 0) > 0 ? `${run.must_review_count} review` : ""}
                                {pct != null ? ` ${pct}%` : ""}
                              </span>
                            </div>
                            <div className="font-mono text-xs text-white truncate mt-1" title={run._runId}>
                              {run._runId}
                            </div>
                            <Link
                              to={`/runs/${run._runId}`}
                              onClick={(e) => e.stopPropagation()}
                              className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-medium text-cyan-400 hover:text-cyan-300"
                            >
                              View
                              <ChevronRight size={10} />
                            </Link>
                          </motion.li>
                        );
                      })}
                    </ul>
                  </div>
                </>
              )}
            </div>
          </motion.aside>
        ) : (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            type="button"
            onClick={() => setPanelOpen(true)}
            className="absolute top-4 right-4 z-[1000] flex items-center gap-2 rounded-lg bg-[#0f1419] border border-neutral-700 text-white px-3 py-2 text-sm font-medium shadow-lg hover:bg-neutral-800 transition-colors"
            aria-label="Open panel"
          >
            <ChevronLeft size={18} />
            Panel
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
