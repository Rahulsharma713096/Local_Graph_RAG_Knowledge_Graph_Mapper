import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Architecture } from './pages/Architecture';
import { Pipeline } from './pages/Pipeline';
import { GraphView } from './pages/GraphView';
import { OllamaModels } from './pages/OllamaModels';
import { QueryConsole } from './pages/QueryConsole';

export default function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}
