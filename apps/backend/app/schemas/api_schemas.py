from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime


class DataSourceCreate(BaseModel):
    name: str
    source_type: str
    connection_string: Optional[str] = None
    file_path: Optional[str] = None
    config: Optional[dict] = None


class DataSourceResponse(BaseModel):
    id: int
    name: str
    source_type: str
    is_connected: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PipelineCreate(BaseModel):
    data_source_id: int
    name: str


class PipelineResponse(BaseModel):
    id: int
    data_source_id: int
    name: str
    status: str
    progress: float
    stages: Optional[Any]
    current_stage: Optional[str]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    query: str
    traversal_depth: int = Field(default=2, ge=1, le=10)
    model: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    generated_cypher: Optional[str] = None
    retrieved_context: Optional[list] = None
    execution_time_ms: float
    pipeline_steps: list = []


class OllamaModelInfo(BaseModel):
    model_config = {'protected_namespaces': ()}
    name: str
    model_size: Optional[str] = None
    vram_estimate: Optional[str] = None
    context_size: Optional[int] = None
    speed_score: Optional[float] = None
    rag_suitability: Optional[float] = None
    is_active: bool = False


class ModelSelectRequest(BaseModel):
    model_config = {'protected_namespaces': ()}
    model_name: str


class SystemMetricsResponse(BaseModel):
    cpu_usage: float
    ram_usage: float
    ram_total: float
    gpu_usage: Optional[float] = None
    gpu_memory: Optional[float] = None
    neo4j_heap_usage: Optional[float] = None
    active_pipelines: int


class GraphNodeSchema(BaseModel):
    id: str
    label: str
    name: str
    properties: Optional[dict] = None


class GraphEdgeSchema(BaseModel):
    source: str
    target: str
    relationship: str
    properties: Optional[dict] = None


class GraphResponse(BaseModel):
    nodes: List[GraphNodeSchema]
    edges: List[GraphEdgeSchema]
    stats: dict = {}
