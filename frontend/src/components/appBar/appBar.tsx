import React, { useEffect, useState } from "react";
import { CheckCircle2, XCircle, AlertCircle, User, Menu } from "lucide-react";
import { checkApiHealth } from "../../api/api";

export type AppBarProps = {
  onMenuClick: () => void;
};

export default function AppBar({ onMenuClick }: AppBarProps) {
  const [apiHealth, setApiHealth] = useState<{ healthy: boolean; latency?: number }>({ healthy: false });

  useEffect(() => {
    const run = async () => {
      const h = await checkApiHealth();
      setApiHealth(h);
    };
    run();
    const id = setInterval(run, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center justify-between px-4 md:px-6 bg-[#0f1419]/95 border-b border-neutral-800 backdrop-blur-sm">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onMenuClick}
          className="md:hidden p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
          aria-label="Toggle menu"
        >
          <Menu size={22} />
        </button>
        <div className="flex items-center gap-3">
          <img
            src="/azerenerji-logo.png"
            alt="AzərEnerji Logo"
            className="h-20 md:h-24 w-auto object-contain"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div
          className={`hidden flex items-center gap-2 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
            apiHealth.healthy
              ? apiHealth.latency != null && apiHealth.latency > 2000
                ? "bg-amber-500/10 border-amber-500/50 text-amber-400"
                : "bg-emerald-500/10 border-emerald-500/50 text-emerald-400"
              : "bg-red-500/10 border-red-500/50 text-red-400"
          }`}
          title={apiHealth.healthy ? `API OK${apiHealth.latency != null ? ` (${apiHealth.latency}ms)` : ""}` : "API offline"}
        >
          {apiHealth.healthy ? (
            apiHealth.latency != null && apiHealth.latency > 2000 ? (
              <AlertCircle size={14} />
            ) : (
              <CheckCircle2 size={14} />
            )
          ) : (
            <XCircle size={14} />
          )}
          <span className="hidden sm:inline">
            {apiHealth.healthy ? (apiHealth.latency != null ? `${apiHealth.latency}ms` : "Online") : "Offline"}
          </span>
        </div>
        <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-neutral-700">
          <div className="w-8 h-8 rounded-lg bg-neutral-800 flex items-center justify-center text-neutral-400">
            <User size={18} />
          </div>
          <span className="text-sm text-neutral-400 max-w-[100px] truncate">User</span>
        </div>
      </div>
    </header>
  );
}
