import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ListOrdered,
  Map,
  ClipboardList,
  Settings,
  ChevronLeft,
  ChevronRight,
  Crosshair,
} from "lucide-react";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/ai-detection", label: "AI Detection", icon: Crosshair },
  { to: "/runs", label: "Recent Uploads", icon: ListOrdered },
  { to: "/review-queue", label: "Review Queue", icon: ClipboardList },
  { to: "/map", label: "Corridor Map", icon: Map },
  { to: "/settings", label: "Settings", icon: Settings },
];

export type LeftSideBarProps = {
  sidebarCollapsed: boolean;
  sidebarOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobileSidebar: () => void;
};

export default function LeftSideBar({
  sidebarCollapsed,
  sidebarOpen,
  onToggleCollapsed,
  onCloseMobileSidebar,
}: LeftSideBarProps) {
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
            onClick={onCloseMobileSidebar}
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
          onClick={onToggleCollapsed}
          className="hidden md:flex w-full items-center justify-center gap-2 rounded-lg py-2 text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors text-sm"
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          {!sidebarCollapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
