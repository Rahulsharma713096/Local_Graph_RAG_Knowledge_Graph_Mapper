from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class PipelineStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False)  # postgresql, mysql, sqlite, csv
    connection_string = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    config = Column(JSON, nullable=True)
    is_connected = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pipelines = relationship("Pipeline", back_populates="data_source")


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))
    name = Column(String(255), nullable=False)
    status = Column(SAEnum(PipelineStatus), default=PipelineStatus.PENDING)
    progress = Column(Float, default=0.0)
    stages = Column(JSON, nullable=True)
    current_stage = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    data_source = relationship("DataSource", back_populates="pipelines")


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, index=True)
    neo4j_id = Column(String(255), unique=True, nullable=True)
    label = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    properties = Column(JSON, nullable=True)
    embedding_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    natural_query = Column(Text, nullable=False)
    generated_cypher = Column(Text, nullable=True)
    retrieved_context = Column(JSON, nullable=True)
    answer = Column(Text, nullable=True)
    traversal_depth = Column(Integer, default=2)
    execution_time_ms = Column(Float, nullable=True)
    status = Column(String(50), default="success")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OllamaModel(Base):
    __tablename__ = "ollama_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    model_size = Column(String(50), nullable=True)
    vram_estimate = Column(String(50), nullable=True)
    context_size = Column(Integer, nullable=True)
    speed_score = Column(Float, nullable=True)
    rag_suitability = Column(Float, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    cpu_usage = Column(Float, nullable=True)
    ram_usage = Column(Float, nullable=True)
    ram_total = Column(Float, nullable=True)
    gpu_usage = Column(Float, nullable=True)
    gpu_memory = Column(Float, nullable=True)
    neo4j_heap_usage = Column(Float, nullable=True)
    active_pipelines = Column(Integer, default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
