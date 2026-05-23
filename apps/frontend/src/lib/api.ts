import type {
  DataSource, Pipeline, GraphData, OllamaModel,
  QueryResult, SystemMetrics, HealthStatus, QueryHistoryItem,
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

// Pipelines
export const listPipelines = () => request<Pipeline[]>('/pipelines');
export const createPipeline = (data: { data_source_id: number; name: string }) =>
  request<Pipeline>('/pipelines', { method: 'POST', body: JSON.stringify(data) });
export const runPipeline = (id: number) =>
  request<{ message: string; pipeline_id: number }>(`/pipelines/${id}/run`, { method: 'POST' });

// Graph
export const getGraph = (limit = 100) => request<GraphData>(`/graph?limit=${limit}`);
export const getGraphStats = () => request<GraphData['stats']>('/graph/stats');
export const executeCypher = (query: string) =>
  request<{ results: unknown[] }>('/graph/cypher', { method: 'POST', body: JSON.stringify({ query }) });

// Query
export const queryGraph = (data: { query: string; traversal_depth?: number; model?: string }) =>
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

// Dashboard
export const getDashboardMetrics = () => request<SystemMetrics>('/dashboard/metrics');
export const getDashboardHealth = () => request<HealthStatus>('/dashboard/health');

// Seed
export const seedDemoData = () => request<{ message: string }>('/seed', { method: 'POST' });
