import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ToastContainer, useToast } from "../components/Toast";
import AppBar from "../components/appBar/appBar";
import LeftSideBar from "../components/leftSideBar/leftSideBar";

export default function HomeLayout({ children }: { children: React.ReactNode }) {
  const { toasts, remove } = useToast();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white relative overflow-x-hidden">
      <ToastContainer toasts={toasts} onRemove={remove} />

      <AppBar onMenuClick={() => setSidebarOpen((o) => !o)} />

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

      <LeftSideBar
        sidebarCollapsed={sidebarCollapsed}
        sidebarOpen={sidebarOpen}
        onToggleCollapsed={() => setSidebarCollapsed((c) => !c)}
        onCloseMobileSidebar={() => setSidebarOpen(false)}
      />

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
