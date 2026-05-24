import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { lazy, Suspense } from 'react';
import { useGlobalWebSocket } from './hooks/useWebSocket';

const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Architecture = lazy(() => import('./pages/Architecture').then(m => ({ default: m.Architecture })));
const Pipeline = lazy(() => import('./pages/Pipeline').then(m => ({ default: m.Pipeline })));
const GraphView = lazy(() => import('./pages/GraphView').then(m => ({ default: m.GraphView })));
const OllamaModels = lazy(() => import('./pages/OllamaModels').then(m => ({ default: m.OllamaModels })));
const QueryConsole = lazy(() => import('./pages/QueryConsole').then(m => ({ default: m.QueryConsole })));

function PageLoading() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function AppContent() {
  // Global WebSocket connection for real-time updates
  useGlobalWebSocket();

  return (
    <Suspense fallback={<PageLoading />}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/graph" element={<GraphView />} />
          <Route path="/ollama" element={<OllamaModels />} />
          <Route path="/query" element={<QueryConsole />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
