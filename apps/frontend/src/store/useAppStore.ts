import { create } from 'zustand';
import type {
  TabId, GraphData, OllamaModel, SystemMetrics,
  HealthStatus, DataSource, Pipeline, QueryHistoryItem,
} from '../types';

interface AppState {
  // UI
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;

  // Data
  dataSources: DataSource[];
  setDataSources: (sources: DataSource[]) => void;
  pipelines: Pipeline[];
  setPipelines: (pipelines: Pipeline[]) => void;
  graphData: GraphData | null;
  setGraphData: (data: GraphData | null) => void;
  ollamaModels: OllamaModel[];
  setOllamaModels: (models: OllamaModel[]) => void;
  metrics: SystemMetrics | null;
  setMetrics: (metrics: SystemMetrics | null) => void;
  healthStatus: HealthStatus | null;
  setHealthStatus: (status: HealthStatus | null) => void;
  queryHistory: QueryHistoryItem[];
  setQueryHistory: (history: QueryHistoryItem[]) => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;

  // Streaming
  streamBuffer: string;
  appendStream: (chunk: string) => void;
  clearStream: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeTab: 'dashboard',
  setActiveTab: (tab) => set({ activeTab: tab }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  isLoading: false,
  setIsLoading: (loading) => set({ isLoading: loading }),

  dataSources: [],
  setDataSources: (sources) => set({ dataSources: sources }),
  pipelines: [],
  setPipelines: (pipelines) => set({ pipelines }),
  graphData: null,
  setGraphData: (data) => set({ graphData: data }),
  ollamaModels: [],
  setOllamaModels: (models) => set({ ollamaModels: models }),
  metrics: null,
  setMetrics: (metrics) => set({ metrics }),
  healthStatus: null,
  setHealthStatus: (status) => set({ healthStatus: status }),
  queryHistory: [],
  setQueryHistory: (history) => set({ queryHistory: history }),
  selectedModel: 'llama3.1',
  setSelectedModel: (model) => set({ selectedModel: model }),

  streamBuffer: '',
  appendStream: (chunk) => set((s) => ({ streamBuffer: s.streamBuffer + chunk })),
  clearStream: () => set({ streamBuffer: '' }),
}));
