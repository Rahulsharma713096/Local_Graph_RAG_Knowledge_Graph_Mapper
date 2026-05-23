export interface DataSource {
  id: number;
  name: string;
  source_type: string;
  connection_string?: string;
  file_path?: string;
  config?: Record<string, unknown>;
  is_connected: boolean;
  created_at: string;
}

export interface Pipeline {
  id: number;
  data_source_id: number;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  stages?: Record<string, unknown>;
  current_stage?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface GraphNode {
  id: string;
  label: string;
  name: string;
  properties?: Record<string, unknown>;
}

export interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  properties?: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    node_count?: number;
    edge_count?: number;
    node_labels?: string[];
    relationship_types?: string[];
  };
}

export interface OllamaModel {
  name: string;
  model_size?: string;
  vram_estimate?: string;
  context_size?: number;
  speed_score?: number;
  rag_suitability?: number;
  is_active: boolean;
}

export interface QueryResult {
  answer: string;
  generated_cypher?: string;
  retrieved_context?: unknown[];
  execution_time_ms: number;
  pipeline_steps: PipelineStep[];
}

export interface PipelineStep {
  step: string;
  status: 'running' | 'completed' | 'failed';
  error?: string;
}

export interface SystemMetrics {
  cpu_usage: number;
  ram_usage: number;
  ram_total: number;
  gpu_usage?: number;
  gpu_memory?: number;
  neo4j_heap_usage?: number;
  active_pipelines: number;
}

export interface HealthStatus {
  backend: string;
  neo4j: string;
  ollama: string;
}

export interface QueryHistoryItem {
  id: number;
  natural_query: string;
  generated_cypher?: string;
  answer?: string;
  execution_time_ms?: number;
  status: string;
  created_at: string;
}

export type TabId = 'architecture' | 'pipeline' | 'graph' | 'ollama' | 'query' | 'dashboard';

// ─── Buffering Types ────────────────────────────────────────────

export interface BufferingEvent {
  event: 'buffering_start' | 'buffer_chunk' | 'buffering_done' | 'buffering_error';
  model?: string;
  prompt_length?: number;
  chars_buffered?: number;
  elapsed_seconds?: number;
  latest_chunk?: string;
  total_chars?: number;
  error?: string;
  timestamp?: number;
}

export interface BufferingState {
  active: boolean;
  model: string;
  charsBuffered: number;
  elapsedSeconds: number;
  statusText: string;
  events: BufferingEvent[];
}
