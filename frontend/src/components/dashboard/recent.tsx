import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Copy, ChevronRight, Clock, XCircle, CheckCircle2 } from "lucide-react";
import type { Run } from "../../api/api";
import { toast } from "../Toast";

function copyRunId(runId: string) {
  navigator.clipboard.writeText(runId).then(
    () => toast.success("Run ID copied to clipboard", 2500),
    () => toast.error("Copy failed", 3000)
  );
}

function confidencePct(r: Run): number | null {
  const v = r.avg_confidence ?? r.ai_confidence;
  return typeof v === "number" ? Math.round(v * 100) : null;
}

type DashboardRecentProps = {
  recentRuns: Run[];
  transition: { duration: number };
  reduceMotion: boolean | null;
};

export default function DashboardRecent({ recentRuns, transition, reduceMotion }: DashboardRecentProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ ...transition, delay: reduceMotion ? 0 : 0.25 }}
      className="rounded-xl border border-neutral-800 bg-neutral-900/50 overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">Recent Uploads</h3>
        <Link
          to="/runs"
          className="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
        >
          View all
          <ChevronRight size={14} />
        </Link>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-neutral-800/50 text-neutral-400">
            <tr>
              <th className="text-left px-4 py-2 font-semibold">Run ID</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Findings</th>
              <th className="text-left px-4 py-2 font-semibold">Must review</th>
              <th className="text-left px-4 py-2 font-semibold">Confidence</th>
              <th className="text-left px-4 py-2 font-semibold">Created</th>
              <th className="text-right px-4 py-2 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-800">
            {recentRuns.map((run, i) => {
              const runId = run.run_id ?? run.id;
              const pct = confidencePct(run);
              return (
                <motion.tr
                  key={run.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: reduceMotion ? 0 : 0.03 * i }}
                  className="hover:bg-neutral-800/50 transition-colors"
                >
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-white text-xs truncate max-w-[100px]" title={runId}>
                        {runId}
                      </span>
                      <button
                        type="button"
                        onClick={() => copyRunId(runId)}
                        className="p-1 rounded text-neutral-400 hover:text-white hover:bg-neutral-700 shrink-0"
                        aria-label="Copy run ID"
                      >
                        <Copy size={12} />
                      </button>
                    </div>
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${
                        run.status === "completed"
                          ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50"
                          : run.status === "processing"
                          ? "bg-amber-500/20 text-amber-400 border-amber-500/50"
                          : run.status === "failed"
                          ? "bg-red-500/20 text-red-400 border-red-500/50"
                          : "bg-neutral-500/20 text-neutral-400 border-neutral-500/50"
                      }`}
                    >
                      {run.status === "processing" && <Clock size={10} className="animate-spin" />}
                      {run.status === "failed" && <XCircle size={10} />}
                      {run.status === "completed" && <CheckCircle2 size={10} />}
                      {run.status.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-neutral-300">
                    {run.findings_count !== undefined ? run.findings_count : "—"}
                  </td>
                  <td className="px-4 py-2">
                    <span
                      className={
                        (run.must_review_count ?? 0) > 0 ? "text-amber-400 font-medium" : "text-neutral-400"
                      }
                    >
                      {run.must_review_count ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2">
                    {pct != null ? (
                      <div className="flex items-center gap-2 w-20">
                        <div className="flex-1 h-1.5 bg-neutral-700 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="text-xs text-neutral-400 shrink-0">{pct}%</span>
                      </div>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-4 py-2 text-neutral-400 text-xs">
                    {(() => {
                      const ts = run.created_at ?? run.timestamp;
                      return ts ? new Date(ts).toLocaleString() : "—";
                    })()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <Link
                      to={`/runs/${runId}`}
                      className="inline-flex items-center gap-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 px-2 py-1 text-xs font-semibold hover:bg-cyan-500/30"
                    >
                      View
                      <ChevronRight size={12} />
                    </Link>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}
