import type {
  DataSource, Pipeline, GraphData, OllamaModel, OllamaBenchmark,
  QueryResult, SystemMetrics, HealthStatus, QueryHistoryItem, HistoricalMetric,
} from '../types';

const BASE_URL = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

// Health & Info
export const getHealth = () => request<{ status: string }>('/health');
export const getAppInfo = () => request<{ name: string; version: string; features: string[] }>('/info');

// Data Sources
export const listDataSources = () => request<DataSource[]>('/datasources');
export const createDataSource = (data: Partial<DataSource>) =>
  request<DataSource>('/datasources', { method: 'POST', body: JSON.stringify(data) });
export const deleteDataSource = (id: number) =>
  request<{ message: string }>(`/datasources/${id}`, { method: 'DELETE' });
export const updateDataSource = (id: number, data: Partial<DataSource>) =>
  request<DataSource>(`/datasources/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const disconnectDataSource = (id: number) =>
  request<{ message: string }>(`/datasources/${id}/disconnect`, { method: 'PUT' });

// File Upload & Browse
export async function uploadDataSourceFile(file: File, name?: string, sourceType = 'csv'): Promise<DataSource> {
  const formData = new FormData();
  formData.append('file', file);
  if (name) formData.append('name', name);
  formData.append('source_type', sourceType);
  const res = await fetch(`${BASE_URL}/datasources/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface DirEntry {
  name: string;
  path: string;
  type: 'file' | 'directory' | 'drive';
  size?: number;
  size_display?: string;
}

export interface BrowseResult {
  entries: DirEntry[];
  current_path: string;
  parent_path?: string;
}

export const browseDirectory = (path = '') =>
  request<BrowseResult>(`/datasources/browse?path=${encodeURIComponent(path)}`);

// Pipelines
export const listPipelines = () => request<Pipeline[]>('/pipelines');
export const createPipeline = (data: { data_source_id: number; name: string }) =>
  request<Pipeline>('/pipelines', { method: 'POST', body: JSON.stringify(data) });
export const runPipeline = (id: number) =>
  request<{ message: string; pipeline_id: number }>(`/pipelines/${id}/run`, { method: 'POST' });
export const updatePipeline = (id: number, data: Partial<Pipeline>) =>
  request<Pipeline>(`/pipelines/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deletePipeline = (id: number) =>
  request<{ message: string }>(`/pipelines/${id}`, { method: 'DELETE' });

// Graph
export const getGraph = (limit = 100) => request<GraphData>(`/graph?limit=${limit}`);
export const getGraphStats = () => request<GraphData['stats']>('/graph/stats');
export const executeCypher = (query: string) =>
  request<{ results: unknown[] }>('/graph/cypher', { method: 'POST', body: JSON.stringify({ query }) });
export const clearGraphData = () =>
  request<{ message: string }>('/graph', { method: 'DELETE' });

// Query
export const queryGraph = (data: { query: string; traversal_depth?: number; model?: string; retry?: boolean }) =>
  request<QueryResult>('/query', { method: 'POST', body: JSON.stringify(data) });
export const getQueryHistory = (limit = 20) =>
  request<QueryHistoryItem[]>(`/query/history?limit=${limit}`);

// Ollama
export const getOllamaStatus = () => request<{ available: boolean }>('/ollama/status');
export const listOllamaModels = () => request<OllamaModel[]>('/ollama/models');
export const selectOllamaModel = (modelName: string) =>
  request<{ message: string }>('/ollama/models/select', { method: 'POST', body: JSON.stringify({ model_name: modelName }) });
export const pullOllamaModel = (modelName: string) =>
  request<{ message: string }>('/ollama/pull', { method: 'POST', body: JSON.stringify({ model_name: modelName }) });
export const chatWithOllamaModel = (message: string, model?: string) =>
  request<{ response: string; model: string }>('/ollama/chat', { method: 'POST', body: JSON.stringify({ message, model }) });

// Dashboard
export const getDashboardMetrics = () => request<SystemMetrics>('/dashboard/metrics');
export const getDashboardHealth = () => request<HealthStatus>('/dashboard/health');
export const getHistoricalMetrics = (hours = 2) =>
  request<HistoricalMetric[]>(`/dashboard/metrics/history?hours=${hours}`);

// Ollama Benchmark
export const benchmarkOllamaModel = (modelName: string) =>
  request<OllamaBenchmark>(`/ollama/benchmark/${encodeURIComponent(modelName)}`);

// Seed
export const seedDemoData = () => request<{ message: string }>('/seed', { method: 'POST' });
