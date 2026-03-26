import React, { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  ListOrdered,
  Map,
  ClipboardList,
  Settings,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  User,
  Menu,
  Video,
  Crosshair,
} from "lucide-react";
import { ToastContainer, useToast } from "./Toast";
import { checkApiHealth } from "../api/api";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/runs", label: "Scan Uploads", icon: ListOrdered },
  { to: "/ai-detection", label: "AI Detection", icon: Crosshair },
  { to: "/video-upload", label: "Video Upload", icon: Video },
  { to: "/map", label: "Corridor Map", icon: Map },
  { to: "/review-queue", label: "Review Queue", icon: ClipboardList },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { toasts, remove } = useToast();
  const [apiHealth, setApiHealth] = useState<{ healthy: boolean; latency?: number }>({ healthy: false });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const run = async () => {
      const h = await checkApiHealth();
      setApiHealth(h);
    };
    run();
    const id = setInterval(run, 30000);
    return () => clearInterval(id);
  }, []);

  const showFullLabels = sidebarOpen || !sidebarCollapsed;

  const sideContent = (
    <>
      {navItems.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/dashboard"}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500/50 ${
                isActive
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-neutral-400 hover:bg-neutral-800 hover:text-white border border-transparent"
              }`
            }
          >
            <Icon size={20} className="shrink-0" />
            {showFullLabels && <span>{item.label}</span>}
          </NavLink>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white relative overflow-x-hidden">
      <ToastContainer toasts={toasts} onRemove={remove} />

      {/* Top header */}
      <header className="fixed top-0 left-0 right-0 z-50 h-14 flex items-center justify-between px-4 md:px-6 bg-[#0f1419]/95 border-b border-neutral-800 backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setSidebarOpen((o) => !o)}
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
            <span className="font-semibold text-white text-xs md:text-sm truncate max-w-[180px] md:max-w-none hidden md:inline">
              Powerline Inspection AI
            </span>
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

      {/* Mobile overlay when sidebar open */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden
          />
        )}
      </AnimatePresence>

      {/* Sidebar: desktop always visible, mobile slide-out */}
      <aside
        className={`fixed top-14 left-0 z-50 h-[calc(100vh-3.5rem)] bg-[#0f1419] border-r border-neutral-800 flex flex-col transition-all duration-200
          ${sidebarCollapsed ? "w-16 md:w-16" : "w-64 md:w-64"}
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        <nav className="p-3 flex flex-col gap-1 overflow-y-auto flex-1">
          {sidebarCollapsed && !sidebarOpen ? (
            navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/dashboard"}
                  title={item.label}
                  className={({ isActive }) =>
                    `flex items-center justify-center w-10 h-10 rounded-xl transition-colors ${
                      isActive ? "bg-cyan-500/20 text-cyan-300" : "text-neutral-400 hover:bg-neutral-800 hover:text-white"
                    }`
                  }
                >
                  <Icon size={20} />
                </NavLink>
              );
            })
          ) : (
            sideContent
          )}
        </nav>
        <div className="p-2 border-t border-neutral-800">
          <button
            type="button"
            onClick={() => setSidebarCollapsed((c) => !c)}
            className="hidden md:flex w-full items-center justify-center gap-2 rounded-lg py-2 text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors text-sm"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            {!sidebarCollapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main
        className={`pt-14 min-h-screen transition-[margin-left] duration-200 ${
          sidebarCollapsed ? "md:ml-16" : "md:ml-64"
        }`}
      >
        <div className="p-4 md:p-6 max-w-[1600px] mx-auto">{children}</div>
      </main>
    </div>
  );
}
