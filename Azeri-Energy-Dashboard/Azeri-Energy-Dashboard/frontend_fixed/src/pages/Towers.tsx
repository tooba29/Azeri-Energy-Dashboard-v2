import React, { useEffect, useMemo, useState } from "react";
import { getTowers, type Tower } from "../api/api";
import StatusBadge from "../components/StatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import { Link } from "react-router-dom";

export default function Towers() {
  const [towers, setTowers] = useState<Tower[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [voltageFilter, setVoltageFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [regionFilter, setRegionFilter] = useState<string>("all");
  const [corridorFilter, setCorridorFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bulkAction, setBulkAction] = useState<string>("");
  const [itemsPerPage, setItemsPerPage] = useState<number>(50);
  const [showAll, setShowAll] = useState<boolean>(false);

  useEffect(() => {
    setLoading(true);
    getTowers()
      .then(setTowers)
      .catch((e) => setError(e.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    let result = towers;
    const s = q.trim().toLowerCase();
    if (s) {
      result = result.filter((t) => 
        t.id.toLowerCase().includes(s) || 
        t.status.toLowerCase().includes(s) ||
        t.name.toLowerCase().includes(s)
      );
    }
    if (statusFilter !== "all") {
      result = result.filter((t) => t.status === statusFilter);
    }
    if (voltageFilter !== "all") {
      result = result.filter((t) => (t.voltage_kv || "").toLowerCase() === voltageFilter.toLowerCase());
    }
    if (typeFilter !== "all") {
      result = result.filter((t) => (t.tower_type || "").toLowerCase() === typeFilter.toLowerCase());
    }
    if (regionFilter !== "all") {
      result = result.filter((t) => (t.region || "").toLowerCase() === regionFilter.toLowerCase());
    }
    if (corridorFilter !== "all") {
      result = result.filter((t) => (t.corridor_tag || "").toLowerCase() === corridorFilter.toLowerCase());
    }
    return result;
  }, [towers, q, statusFilter, voltageFilter, typeFilter, regionFilter, corridorFilter]);

  const voltageOptions = useMemo(() => Array.from(new Set(towers.map(t => t.voltage_kv).filter(Boolean))), [towers]);
  const typeOptions = useMemo(() => Array.from(new Set(towers.map(t => t.tower_type).filter(Boolean))), [towers]);
  const regionOptions = useMemo(() => Array.from(new Set(towers.map(t => t.region).filter(Boolean))), [towers]);
  const corridorTags = useMemo(() => Array.from(new Set(towers.map(t => t.corridor_tag).filter(Boolean))), [towers]);

  const paginated = useMemo(() => {
    if (showAll) {
      return filtered;
    }
    const start = (currentPage - 1) * itemsPerPage;
    return filtered.slice(start, start + itemsPerPage);
  }, [filtered, currentPage, itemsPerPage, showAll]);

  const totalPages = showAll ? 1 : Math.ceil(filtered.length / itemsPerPage);

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === paginated.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(paginated.map(t => t.id)));
    }
  };

  const handleBulkExport = () => {
    const selected = towers.filter(t => selectedIds.has(t.id));
    if (selected.length === 0) {
      alert("Please select towers to export");
      return;
    }
    const data = JSON.stringify(selected, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `towers_bulk_export_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleBulkStatusUpdate = async () => {
    if (!bulkAction || selectedIds.size === 0) {
      alert("Please select towers and a status");
      return;
    }
    if (!confirm(`Update ${selectedIds.size} towers to ${bulkAction}?`)) return;
    // In a real app, this would call an API endpoint
    alert(`Bulk status update: ${selectedIds.size} towers → ${bulkAction} (API integration needed)`);
    setSelectedIds(new Set());
    setBulkAction("");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" text="Loading towers..." />
      </div>
    );
  }

  if (error) {
    const isNetworkError = error.includes("Network error") || error.includes("fetch") || error.includes("Cannot connect");
    return (
      <div className="glass rounded-2xl border border-premium-danger/50 p-6 text-premium-danger shadow-premium">
        <div className="font-semibold mb-2">Error Loading Towers</div>
        <div className="text-sm mb-4">{error}</div>
        {isNetworkError && (
          <div className="mt-4 p-4 bg-neutral-900/50 rounded-lg border border-neutral-700">
            <div className="text-sm font-semibold text-white mb-2">Troubleshooting Steps:</div>
            <ol className="text-xs text-neutral-300 space-y-1 list-decimal list-inside">
              <li>Ensure backend services are running (API Gateway on port 8080, Data Service on port 8081)</li>
              <li>Start services using: <code className="bg-neutral-800 px-1 rounded">.\scripts\start_backend_test.ps1</code></li>
              <li>Check browser console (F12) for detailed error messages</li>
              <li>Verify API URL: <code className="bg-neutral-800 px-1 rounded">http://localhost:8080</code></li>
            </ol>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {selectedIds.size > 0 && (
        <div className="glass rounded-2xl border border-premium-accent/50 bg-premium-accent/10 p-4 shadow-premium">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="text-white font-semibold">
              {selectedIds.size} tower{selectedIds.size !== 1 ? 's' : ''} selected
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <select
                value={bulkAction}
                onChange={(e) => setBulkAction(e.target.value)}
                className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              >
                <option value="">Bulk Action...</option>
                <option value="HEALTHY">Set to Healthy</option>
                <option value="MONITOR">Set to Monitor</option>
                <option value="REQUIRES_INSPECTION">Set to Requires Inspection</option>
              </select>
              <button
                onClick={handleBulkStatusUpdate}
                disabled={!bulkAction}
                className="rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover disabled:opacity-50 transition-colors"
              >
                Update Status
              </button>
              <button
                onClick={handleBulkExport}
                className="rounded-xl bg-gradient-accent text-white px-4 py-2 text-sm font-semibold hover:shadow-glow transition-all"
              >
                Export Selected
              </button>
              <button
                onClick={() => setSelectedIds(new Set())}
                className="rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover transition-colors"
              >
                Clear Selection
              </button>
            </div>
          </div>
        </div>
      )}
    <div className="glass rounded-2xl border border-neutral-800 shadow-premium overflow-hidden">
        <div className="px-5 py-4 border-b border-neutral-800 flex items-center justify-between gap-3 flex-wrap">
          <div className="font-semibold text-white">
            Towers <span className="text-sm font-normal text-neutral-400">({filtered.length} total)</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <select
              value={showAll ? "all" : itemsPerPage.toString()}
              onChange={(e) => {
                if (e.target.value === "all") {
                  setShowAll(true);
                  setItemsPerPage(filtered.length);
                } else {
                  setShowAll(false);
                  setItemsPerPage(parseInt(e.target.value));
                  setCurrentPage(1);
                }
              }}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
            >
              <option value="20">20 per page</option>
              <option value="50">50 per page</option>
              <option value="100">100 per page</option>
              <option value="all">Show All ({filtered.length})</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
            >
              <option value="all">All Status</option>
              <option value="HEALTHY">Healthy</option>
              <option value="MONITOR">Monitor</option>
              <option value="REQUIRES_INSPECTION">Requires Inspection</option>
            </select>
            <select
              value={voltageFilter}
              onChange={(e) => {
                setVoltageFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
            >
              <option value="all">All Voltages</option>
              {voltageOptions.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            <select
              value={typeFilter}
              onChange={(e) => {
                setTypeFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
            >
              <option value="all">All Tower Types</option>
              {typeOptions.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            <select
              value={regionFilter}
              onChange={(e) => {
                setRegionFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
            >
              <option value="all">All Regions</option>
              {regionOptions.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {corridorTags.length > 0 && (
              <select
                value={corridorFilter}
                onChange={(e) => {
                  setCorridorFilter(e.target.value);
                  setCurrentPage(1);
                }}
                className="rounded-xl bg-premium-card border border-neutral-700 text-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent"
              >
                <option value="all">All Corridors</option>
                {corridorTags.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            )}
        <input
          value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Search towers…"
          className="w-56 rounded-xl bg-premium-card border border-neutral-700 text-white placeholder-neutral-500 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-premium-accent focus:border-premium-accent"
        />
          </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-premium-card/50 text-neutral-300">
            <tr>
              <th className="text-left px-5 py-3 font-semibold w-12">
                <input
                  type="checkbox"
                  checked={selectedIds.size === paginated.length && paginated.length > 0}
                  onChange={toggleSelectAll}
                  className="rounded border-neutral-600 bg-premium-card text-premium-accent focus:ring-premium-accent"
                />
              </th>
              <th className="text-left px-5 py-3 font-semibold">Tower</th>
              <th className="text-left px-5 py-3 font-semibold">Voltage / Type</th>
              <th className="text-left px-5 py-3 font-semibold">Region</th>
              <th className="text-left px-5 py-3 font-semibold">Status</th>
              <th className="text-left px-5 py-3 font-semibold">Sensors</th>
              <th className="text-left px-5 py-3 font-semibold">Last scan</th>
              <th className="text-left px-5 py-3 font-semibold">AI Confidence</th>
              <th className="text-right px-5 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {paginated.map((t) => (
              <tr key={t.id} className={`hover:bg-premium-card-hover/50 transition-colors ${selectedIds.has(t.id) ? 'bg-premium-accent/10' : ''}`}>
                <td className="px-5 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(t.id)}
                    onChange={() => toggleSelect(t.id)}
                    className="rounded border-neutral-600 bg-premium-card text-premium-accent focus:ring-premium-accent"
                  />
                </td>
                <td className="px-5 py-3 font-semibold text-white">
                  <div>{t.id}</div>
                  <div className="text-xs text-neutral-400">{t.name}</div>
                  <div className="text-[11px] text-neutral-500">{t.corridor}</div>
                  {t.corridor_tag && (
                    <div className="inline-flex mt-1 rounded-full bg-premium-card px-2 py-1 text-[11px] text-premium-accent border border-premium-accent/40">
                      {t.corridor_tag}
                    </div>
                  )}
                </td>
                <td className="px-5 py-3">
                  <div className="text-white">{t.voltage_kv || "—"}</div>
                  <div className="text-xs text-neutral-400 capitalize">{t.tower_type || "—"}</div>
                </td>
                <td className="px-5 py-3">
                  <div className="text-white">{t.region || "—"}</div>
                </td>
                <td className="px-5 py-3">
                  <StatusBadge status={t.status} />
                </td>
                <td className="px-5 py-3 text-neutral-300">{t.sensors.join(", ")}</td>
                <td className="px-5 py-3 text-neutral-300">{new Date(t.last_scan).toLocaleString()}</td>
                <td className="px-5 py-3 text-neutral-300">
                  <span className={`font-semibold ${t.ai_confidence >= 0.9 ? 'text-green-400' : t.ai_confidence >= 0.7 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {(t.ai_confidence * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="px-5 py-3 text-right">
                  <Link to={`/towers/${t.id}`} className="rounded-xl bg-gradient-accent text-white px-3 py-2 font-semibold hover:shadow-glow transition-all">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
            {!paginated.length ? (
              <tr>
                <td className="px-5 py-6 text-neutral-400 text-center" colSpan={7}>
                  No towers match your filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      {!showAll && totalPages > 1 && (
        <div className="px-5 py-4 border-t border-neutral-800 flex items-center justify-between">
          <div className="text-sm text-neutral-400">
            Showing {((currentPage - 1) * itemsPerPage) + 1} - {Math.min(currentPage * itemsPerPage, filtered.length)} of {filtered.length}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <span className="text-sm text-neutral-300 px-3">
              Page {currentPage} of {totalPages}
            </span>
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="rounded-xl bg-premium-card border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-premium-card-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
      {showAll && (
        <div className="px-5 py-4 border-t border-neutral-800">
          <div className="text-sm text-neutral-400 text-center">
            Showing all {filtered.length} towers
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
