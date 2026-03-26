import React, { useState, useEffect } from "react";
import { 
  HiOutlineChartBar, 
  HiOutlineDocumentReport,
  HiOutlineCheckCircle,
  HiOutlineXCircle,
  HiOutlineClock,
  HiOutlineDownload,
  HiOutlineAcademicCap,
  HiOutlineCog
} from "react-icons/hi";
import { getTowers, getSummary, getEvaluationReports, getMetricsSummary } from "../api/api";
import LoadingSpinner from "../components/LoadingSpinner";

type ModelMetrics = {
  modelName: string;
  modelType: "PART" | "DEFECT" | "THERMAL";
  precision: number;
  recall: number;
  mAP50: number;
  status: "PASS" | "FAIL" | "PENDING";
  evaluationDate?: string;
  trainingDate?: string;
};

type EvaluationReport = {
  id: string;
  modelName: string;
  reportPath: string;
  generatedDate: string;
  metrics: ModelMetrics;
};

export default function Reports() {
  const [summary, setSummary] = useState<any>(null);
  const [towers, setTowers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [evaluationReports, setEvaluationReports] = useState<EvaluationReport[]>([]);
  const [metricsSummary, setMetricsSummary] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      getSummary(), 
      getTowers(),
      getEvaluationReports().catch(() => []),
      getMetricsSummary().catch(() => null)
    ])
      .then(([s, t, reports, metrics]) => {
        setSummary(s);
        setTowers(t);
        setEvaluationReports(reports || []);
        setMetricsSummary(metrics);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const successCriteria = {
    precision: 0.75,
    recall: 0.70,
    mAP50: 0.70
  };

  const checkSuccess = (metrics: ModelMetrics): boolean => {
    return (
      metrics.precision >= successCriteria.precision &&
      metrics.recall >= successCriteria.recall &&
      metrics.mAP50 >= successCriteria.mAP50
    );
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "PASS": return "text-green-400";
      case "FAIL": return "text-red-400";
      case "PENDING": return "text-yellow-400";
      default: return "text-neutral-400";
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case "PASS": return "bg-green-500/20 border-green-500/50";
      case "FAIL": return "bg-red-500/20 border-red-500/50";
      case "PENDING": return "bg-yellow-500/20 border-yellow-500/50";
      default: return "bg-neutral-500/20 border-neutral-500/50";
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" text="Loading reports..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Reports & Metrics</h1>
        <p className="text-neutral-400">
          Phase 6 Deliverables: Model evaluation metrics, performance summaries, and inspection reports
        </p>
      </div>

      {/* Success Criteria Summary */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-center gap-3 mb-4">
          <HiOutlineCheckCircle className="text-2xl text-premium-accent" />
          <h2 className="text-xl font-semibold text-white">Success Criteria</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
            <div className="text-sm text-neutral-400">Precision</div>
            <div className="text-2xl font-bold text-white">≥ {(successCriteria.precision * 100).toFixed(0)}%</div>
          </div>
          <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
            <div className="text-sm text-neutral-400">Recall</div>
            <div className="text-2xl font-bold text-white">≥ {(successCriteria.recall * 100).toFixed(0)}%</div>
          </div>
          <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
            <div className="text-sm text-neutral-400">mAP@0.5</div>
            <div className="text-2xl font-bold text-white">≥ {(successCriteria.mAP50 * 100).toFixed(0)}%</div>
          </div>
        </div>
      </div>

      {/* Model Evaluation Reports */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <HiOutlineAcademicCap className="text-2xl text-premium-accent" />
            <h2 className="text-xl font-semibold text-white">Model Evaluation Reports</h2>
          </div>
        </div>

        <div className="space-y-4">
          {evaluationReports.length === 0 ? (
            <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-8 text-center">
              <HiOutlineDocumentReport className="text-4xl text-neutral-500 mx-auto mb-3" />
              <div className="text-white font-semibold mb-2">No Evaluation Reports Available</div>
              <div className="text-sm text-neutral-400 mb-4">
                Run model evaluation using the evaluation script to generate reports.
              </div>
              <a
                href="/train-model"
                className="inline-block px-4 py-2 rounded-lg bg-premium-accent/20 text-premium-accent text-sm font-semibold hover:bg-premium-accent/30 transition-colors"
              >
                Go to Training
              </a>
            </div>
          ) : (
            evaluationReports.map((report) => {
            const metrics = report.metrics;
            const passed = checkSuccess(metrics);
            
            return (
              <div
                key={report.id}
                className={`rounded-xl border p-5 transition-all cursor-pointer ${
                  selectedModel === report.id
                    ? "border-premium-accent bg-premium-card"
                    : "border-neutral-700 bg-premium-card/50 hover:border-neutral-600"
                }`}
                onClick={() => setSelectedModel(selectedModel === report.id ? null : report.id)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white">{metrics.modelName}</h3>
                      <span className={`px-2 py-1 rounded-lg text-xs font-semibold ${getStatusBg(metrics.status)} ${getStatusColor(metrics.status)}`}>
                        {metrics.status}
                      </span>
                      <span className="px-2 py-1 rounded-lg text-xs font-semibold bg-neutral-700 text-neutral-300">
                        {metrics.modelType}
                      </span>
                    </div>
                    {metrics.evaluationDate && (
                      <div className="text-xs text-neutral-400">
                        Evaluated: {new Date(metrics.evaluationDate).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      // Download report
                      window.open(report.reportPath, '_blank');
                    }}
                    className="p-2 rounded-lg hover:bg-neutral-700 transition-colors"
                  >
                    <HiOutlineDownload className="text-xl text-neutral-400" />
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div>
                    <div className="text-xs text-neutral-400 mb-1">Precision</div>
                    <div className={`text-2xl font-bold ${metrics.precision >= successCriteria.precision ? 'text-green-400' : 'text-red-400'}`}>
                      {(metrics.precision * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      Target: ≥ {(successCriteria.precision * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-neutral-400 mb-1">Recall</div>
                    <div className={`text-2xl font-bold ${metrics.recall >= successCriteria.recall ? 'text-green-400' : 'text-red-400'}`}>
                      {(metrics.recall * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      Target: ≥ {(successCriteria.recall * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-neutral-400 mb-1">mAP@0.5</div>
                    <div className={`text-2xl font-bold ${metrics.mAP50 >= successCriteria.mAP50 ? 'text-green-400' : 'text-red-400'}`}>
                      {(metrics.mAP50 * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-neutral-500 mt-1">
                      Target: ≥ {(successCriteria.mAP50 * 100).toFixed(0)}%
                    </div>
                  </div>
                </div>

                {selectedModel === report.id && (
                  <div className="mt-4 pt-4 border-t border-neutral-700">
                    <div className="text-sm text-neutral-300 mb-2">
                      <strong>Model Details:</strong>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs text-neutral-400">
                      <div>Model Type: {metrics.modelType}</div>
                      <div>Status: {metrics.status}</div>
                      {metrics.trainingDate && (
                        <div>Training Date: {new Date(metrics.trainingDate).toLocaleDateString()}</div>
                      )}
                      {metrics.evaluationDate && (
                        <div>Evaluation Date: {new Date(metrics.evaluationDate).toLocaleDateString()}</div>
                      )}
                    </div>
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          window.open(report.reportPath, '_blank');
                        }}
                        className="px-3 py-1.5 rounded-lg bg-premium-accent/20 text-premium-accent text-xs font-semibold hover:bg-premium-accent/30 transition-colors"
                      >
                        View Full Report
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          }))}
        </div>
      </div>

      {/* System Summary Metrics */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-center gap-3 mb-6">
          <HiOutlineChartBar className="text-2xl text-premium-accent" />
          <h2 className="text-xl font-semibold text-white">System Summary</h2>
        </div>

        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
              <div className="text-sm text-neutral-400 mb-1">Total Towers</div>
              <div className="text-2xl font-bold text-white">{summary.towers_total || 0}</div>
            </div>
            <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
              <div className="text-sm text-neutral-400 mb-1">Total Findings</div>
              <div className="text-2xl font-bold text-white">{summary.findings_total || 0}</div>
            </div>
            <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
              <div className="text-sm text-neutral-400 mb-1">Avg AI Confidence</div>
              <div className="text-2xl font-bold text-white">
                {summary.avg_ai_confidence ? (summary.avg_ai_confidence * 100).toFixed(1) : 0}%
              </div>
            </div>
            <div className="rounded-xl border border-neutral-700 bg-premium-card/50 p-4">
              <div className="text-sm text-neutral-400 mb-1">Status Distribution</div>
              <div className="text-xs text-neutral-300 mt-2 space-y-1">
                {summary.status_counts && Object.entries(summary.status_counts).map(([status, count]: [string, any]) => (
                  <div key={status} className="flex justify-between">
                    <span>{status}:</span>
                    <span className="font-semibold">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Phase 6 Deliverables Checklist */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-center gap-3 mb-6">
          <HiOutlineDocumentReport className="text-2xl text-premium-accent" />
          <h2 className="text-xl font-semibold text-white">Phase 6 Deliverables</h2>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 rounded-lg bg-premium-card/50 border border-neutral-700">
            <HiOutlineCheckCircle className="text-green-400 text-xl flex-shrink-0" />
            <div className="flex-1">
              <div className="font-semibold text-white">Sample Inspection Report</div>
              <div className="text-sm text-neutral-400">PDF reports available for each tower inspection</div>
            </div>
            <a
              href="/towers"
              className="px-3 py-1.5 rounded-lg bg-premium-accent/20 text-premium-accent text-xs font-semibold hover:bg-premium-accent/30 transition-colors"
            >
              View Reports
            </a>
          </div>

          <div className="flex items-center gap-3 p-3 rounded-lg bg-premium-card/50 border border-neutral-700">
            <HiOutlineCheckCircle className="text-green-400 text-xl flex-shrink-0" />
            <div className="flex-1">
              <div className="font-semibold text-white">Metrics Summary</div>
              <div className="text-sm text-neutral-400">Model evaluation metrics displayed above</div>
            </div>
          </div>

          <div className="flex items-center gap-3 p-3 rounded-lg bg-premium-card/50 border border-neutral-700">
            <HiOutlineCheckCircle className="text-green-400 text-xl flex-shrink-0" />
            <div className="flex-1">
              <div className="font-semibold text-white">POC Demo Ready</div>
              <div className="text-sm text-neutral-400">All systems operational for demonstration</div>
            </div>
            <a
              href="/new-scan"
              className="px-3 py-1.5 rounded-lg bg-premium-accent/20 text-premium-accent text-xs font-semibold hover:bg-premium-accent/30 transition-colors"
            >
              Run Demo
            </a>
          </div>
        </div>
      </div>

      {/* Export Options */}
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex items-center gap-3 mb-4">
          <HiOutlineDownload className="text-2xl text-premium-accent" />
          <h2 className="text-xl font-semibold text-white">Export Reports</h2>
        </div>

        <div className="flex gap-3 flex-wrap">
          <button
            onClick={() => {
              const data = {
                export_date: new Date().toISOString(),
                success_criteria: successCriteria,
                model_evaluations: evaluationReports.map(r => r.metrics),
                system_summary: summary
              };
              const json = JSON.stringify(data, null, 2);
              const blob = new Blob([json], { type: 'application/json' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `poc_metrics_summary_${new Date().toISOString().split('T')[0]}.json`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="px-4 py-2 rounded-xl bg-premium-card border border-neutral-700 text-white text-sm font-semibold hover:bg-premium-card-hover transition-colors"
          >
            Export Metrics JSON
          </button>
          <button
            onClick={() => {
              // Generate CSV
              const csv = [
                ['Model Name', 'Type', 'Precision', 'Recall', 'mAP@0.5', 'Status'],
                ...evaluationReports.map(r => [
                  r.metrics.modelName,
                  r.metrics.modelType,
                  (r.metrics.precision * 100).toFixed(2) + '%',
                  (r.metrics.recall * 100).toFixed(2) + '%',
                  (r.metrics.mAP50 * 100).toFixed(2) + '%',
                  r.metrics.status
                ])
              ].map(row => row.join(',')).join('\n');
              
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = `poc_metrics_summary_${new Date().toISOString().split('T')[0]}.csv`;
              a.click();
              URL.revokeObjectURL(url);
            }}
            className="px-4 py-2 rounded-xl bg-premium-card border border-neutral-700 text-white text-sm font-semibold hover:bg-premium-card-hover transition-colors"
          >
            Export Metrics CSV
          </button>
        </div>
      </div>
    </div>
  );
}

