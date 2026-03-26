import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { getRuns, checkApiHealth, API_BASE } from "../api/api";
import { toast } from "../components/Toast";
import {
  Settings as SettingsIcon,
  Server,
  Download,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Info,
  FileJson,
} from "lucide-react";

export default function Settings() {
  const [exporting, setExporting] = useState(false);
  const [health, setHealth] = useState<{ healthy: boolean; latency?: number } | null>(null);

  useEffect(() => {
    const run = async () => {
      const h = await checkApiHealth();
      setHealth(h);
    };
    run();
  }, []);

  const exportRunsJSON = async () => {
    try {
      setExporting(true);
      const runs = await getRuns();
      const data = {
        export_metadata: {
          export_date: new Date().toISOString(),
          system: "Powerline Inspection AI",
          total_runs: runs.length,
        },
        runs: runs.map((r) => ({
          id: r.id,
          run_id: r.run_id,
          tower_id: r.tower_id,
          status: r.status,
          created_at: r.created_at ?? r.timestamp,
          findings_count: r.findings_count,
          must_review_count: r.must_review_count,
          avg_confidence: r.avg_confidence ?? r.ai_confidence,
        })),
      };
      const json = JSON.stringify(data, null, 2);
      const blob = new Blob([json], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `runs_export_${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Runs exported to JSON", 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Export failed";
      toast.error(msg, 5000);
    } finally {
      setExporting(false);
    }
  };

  const apiBase = typeof import.meta.env.VITE_API_BASE === "string" ? import.meta.env.VITE_API_BASE : API_BASE;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
      className="space-y-6"
    >
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
        <p className="text-neutral-400">
          API configuration, health status, and data export.
        </p>
      </div>

      {/* API & Health */}
      <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-6 backdrop-blur-sm space-y-4">
        <div className="flex items-center gap-2 mb-4">
          <Server className="text-cyan-400" size={22} />
          <h2 className="text-lg font-semibold text-white">API & Health</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
            <div className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">API base URL</div>
            <div className="font-mono text-sm text-white break-all">{apiBase}</div>
            <div className="flex items-start gap-2 mt-2 text-xs text-neutral-400">
              <Info size={14} className="shrink-0 mt-0.5" />
              <span>Set VITE_API_BASE in .env (default: http://localhost:8080). Restart dev server after change.</span>
            </div>
          </div>
          <div className="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
            <div className="text-xs font-medium text-neutral-400 uppercase tracking-wider mb-2">Health status</div>
            {health === null ? (
              <div className="text-sm text-neutral-400">Checking...</div>
            ) : (
              <div
                className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${
                  health.healthy
                    ? health.latency != null && health.latency > 2000
                      ? "bg-amber-500/10 border-amber-500/50 text-amber-400"
                      : "bg-emerald-500/10 border-emerald-500/50 text-emerald-400"
                    : "bg-red-500/10 border-red-500/50 text-red-400"
                }`}
              >
                {health.healthy ? (
                  health.latency != null && health.latency > 2000 ? (
                    <AlertCircle size={16} />
                  ) : (
                    <CheckCircle2 size={16} />
                  )
                ) : (
                  <XCircle size={16} />
                )}
                <span>
                  {health.healthy
                    ? health.latency != null
                      ? `Online (${health.latency}ms)`
                      : "Online"
                    : "Offline"}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Preferences */}
      <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-6 backdrop-blur-sm space-y-4">
        <div className="flex items-center gap-2 mb-4">
          <SettingsIcon className="text-cyan-400" size={22} />
          <h2 className="text-lg font-semibold text-white">Preferences</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
            <div className="text-sm font-semibold text-white">Security</div>
            <div className="mt-2 text-sm text-neutral-300">
              <span className="text-cyan-400">Zero-Exfiltration:</span> images and inference outputs can run on an offline workstation (air-gapped option).
            </div>
          </div>
          <div className="rounded-xl border border-neutral-700 bg-neutral-800/50 p-4">
            <div className="text-sm font-semibold text-white">Model versions</div>
            <div className="mt-2 text-sm text-neutral-400">
              Shown in run detail metadata when available. Backend supplies pipeline/model info per run.
            </div>
          </div>
        </div>
      </div>

      {/* Export runs */}
      <div className="rounded-2xl border border-neutral-800 bg-neutral-900/50 p-6 backdrop-blur-sm space-y-4">
        <div className="flex items-center gap-2 mb-4">
          <FileJson className="text-cyan-400" size={22} />
          <h2 className="text-lg font-semibold text-white">Export data</h2>
        </div>
        <p className="text-sm text-neutral-400">
          Export inspection runs list as JSON for backup or analysis.
        </p>
        <div className="flex gap-3 flex-wrap">
          <button
            type="button"
            onClick={exportRunsJSON}
            disabled={exporting}
            className="inline-flex items-center gap-2 rounded-xl bg-neutral-800 border border-neutral-700 text-white px-4 py-2 text-sm font-semibold hover:bg-neutral-700 disabled:opacity-50 transition-colors"
          >
            <Download size={18} />
            {exporting ? "Exporting…" : "Export runs (JSON)"}
          </button>
        </div>
      </div>
    </motion.div>
  );
}
