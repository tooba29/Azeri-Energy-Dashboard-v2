import React from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowLeft, Crosshair } from "lucide-react";
import RgbAnalysis from "./rgbAnalysis";
import ThermalAnalysisTab from "./thermalAnalysis";
import VideoAnalysis from "./videoAnalysis";

const TABS = [
  { id: "video" as const, label: "Video analysis" },
  { id: "thermal" as const, label: "Thermal Analysis" },
  { id: "rgb" as const, label: "RGB analysis" },
];

type TabId = (typeof TABS)[number]["id"];

function parseTab(v: string | null): TabId {
  if (v === "video" || v === "thermal" || v === "rgb") return v;
  return "video";
}

export default function AIDetectionIndex() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = parseTab(searchParams.get("tab"));

  const setTab = (id: TabId) => {
    setSearchParams({ tab: id }, { replace: true });
  };

  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl border border-neutral-800 p-6 shadow-premium">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <Link to="/dashboard" className="text-neutral-400 hover:text-white transition-colors">
              <ArrowLeft size={20} />
            </Link>
            <Crosshair className="text-premium-accent text-xl" />
            <div className="text-sm text-premium-accent uppercase tracking-wider font-medium">AI Detection</div>
          </div>
          <p className="text-sm text-neutral-400">
            Choose a mode: video defect detection, DJI thermal analysis, or RGB image detection.
          </p>
          <div className="flex flex-wrap gap-2">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={`px-4 py-2 rounded-xl text-sm font-semibold transition-colors ${
                  activeTab === t.id
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/50"
                    : "text-neutral-400 border border-neutral-700 bg-neutral-900/40 hover:border-neutral-600 hover:text-white"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {activeTab === "rgb" && <RgbAnalysis />}
      {activeTab === "thermal" && <ThermalAnalysisTab />}
      {activeTab === "video" && <VideoAnalysis />}
    </div>
  );
}
