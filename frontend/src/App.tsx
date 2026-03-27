import React, { Suspense, lazy } from "react";
import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import HomeLayout from "./layouts/home";
import Settings from "./pages/Settings";
import LoadingSpinner from "./components/LoadingSpinner";

const Dashboard = lazy(() => import("./pages/Dashboard/Dashboard"));
const AIDetection = lazy(() => import("./pages/AIDetection/AIDetection"));
const Runs = lazy(() => import("./pages/Runs"));
const RunDetail = lazy(() => import("./pages/RunDetail"));
const CorridorMap = lazy(() => import("./pages/CorridorMap"));
const ReviewQueue = lazy(() => import("./pages/ReviewQueue"));
// Import BulkBatches directly to avoid lazy loading issues

const LazyRoute = ({ children }: { children: React.ReactNode }) => (
  <Suspense
    fallback={
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner size="lg" text="Loading..." />
      </div>
    }
  >
    {children}
  </Suspense>
);

function HomeLayoutOutlet() {
  return (
    <HomeLayout>
      <Outlet />
    </HomeLayout>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard" element={<LazyRoute><Dashboard /></LazyRoute>} />
      <Route path="/ai-detection" element={<LazyRoute><AIDetection /></LazyRoute>} />
      <Route element={<HomeLayoutOutlet />}>
        <Route path="/runs" element={<LazyRoute><Runs /></LazyRoute>} />
        <Route path="/runs/:id" element={<LazyRoute><RunDetail /></LazyRoute>} />
        <Route path="/map" element={<LazyRoute><CorridorMap /></LazyRoute>} />
        <Route path="/review-queue" element={<LazyRoute><ReviewQueue /></LazyRoute>} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/thermal-analysis" element={<Navigate to="/ai-detection?tab=thermal" replace />} />
        <Route path="/video-upload" element={<Navigate to="/ai-detection?tab=video" replace />} />
        <Route path="/videos" element={<Navigate to="/ai-detection?tab=video" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
