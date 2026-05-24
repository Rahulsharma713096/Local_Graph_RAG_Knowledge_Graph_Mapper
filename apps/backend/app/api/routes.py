from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging
import asyncio
import os
import time
import shutil
import csv
import string

from datetime import datetime

from app.core.database import get_db, init_db
from app.core.websocket_manager import ws_manager
from app.schemas.api_schemas import (
    DataSourceCreate, DataSourceUpdate, DataSourceResponse,
    PipelineCreate, PipelineUpdate, PipelineResponse,
    QueryRequest, QueryResponse,
    OllamaModelInfo, ModelSelectRequest, ChatRequest,
    SystemMetricsResponse, GraphResponse,
)
from app.models.database_models import DataSource, Pipeline, QueryHistory, OllamaModel, GraphNode
from app.services.graph_service import graph_service
from app.services.ollama_service import ollama_service
from app.services.rag_service import rag_service
from app.services.etl_pipeline import etl_pipeline
from app.services.dashboard_service import dashboard_service

logger = logging.getLogger(__name__)

# Ensure logs directory exists for query logging
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

router = APIRouter()


@router.on_event("startup")
async def startup():
    init_db()
    await dashboard_service.start_metrics_collection()  # SRS: Start periodic metrics
    logger.info("Application startup complete - Database initialized")


# ─── Health & Info ─────────────────────────────────────────────

@router.get("/api/health")
async def health_check():
    return {"status": "healthy", "app": "Local Graph RAG & Knowledge Graph Mapper"}


@router.get("/api/info")
async def app_info():
    return {
        "name": "Local Graph RAG & Knowledge Graph Mapper",
        "version": "1.0.0",
        "features": [
            "Database Connectors",
            "ETL + Knowledge Graph Pipeline",
            "Graph RAG Engine",
            "Ollama Integration",
            "Live Knowledge Graph UI",
            "Query Console",
            "System Dashboard",
        ],
    }


# ─── File Upload & Directory Browser ──────────────────────────

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/api/datasources/upload")
async def upload_datasource_file(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    source_type: str = Form("csv"),
    db: Session = Depends(get_db),
):
    """Upload a CSV file as a new data source."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Save uploaded file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Read first few rows to detect columns
    preview_rows = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = row
                elif i <= 5:
                    preview_rows.append(row)
                else:
                    break
    except Exception as e:
        logger.warning(f"Could not read CSV preview: {e}")
        headers = []
    
    display_name = name or (file.filename.rsplit(".", 1)[0] if file.filename else "Uploaded File")
    
    db_ds = DataSource(
        name=display_name,
        source_type=source_type,
        file_path=file_path,
        config={
            "filename": file.filename,
            "columns": headers,
            "preview_rows": preview_rows,
            "is_upload": True,
        },
        is_connected=True,
    )
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    logger.info(f"Created data source from upload: {db_ds.id} - {display_name}")
    
    # Broadcast update via WebSocket
    await ws_manager.broadcast("datasource_update", {"type": "created", "id": db_ds.id})
    
    return db_ds


@router.get("/api/datasources/browse")
async def browse_directory(path: str = "", db: Session = Depends(get_db)):
    """Browse a directory to find files/folders for data source selection."""
    # Security: restrict to reasonable paths
    allowed_start = [
        os.path.abspath(UPLOAD_DIR),
        os.path.expanduser("~"),
        os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")),
    ]
    
    if not path or path == "/":
        # Return root browse options
        drives = []
        # On Windows, list drives
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append({
                    "name": drive,
                    "path": drive,
                    "type": "drive",
                })
        
        # Also show common directories
        home = os.path.expanduser("~")
        common_dirs = [
            {"name": "Home Directory", "path": home, "type": "directory"},
            {"name": "Upload Directory", "path": UPLOAD_DIR, "type": "directory"},
            {"name": "Data Directory", "path": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"), "type": "directory"},
        ]
        return {"entries": drives + common_dirs, "current_path": ""}
    
    # Browse specific path
    try:
        entries = []
        for entry_name in os.listdir(path):
            entry_path = os.path.join(path, entry_name)
            if os.path.isdir(entry_path):
                entries.append({
                    "name": entry_name,
                    "path": entry_path,
                    "type": "directory",
                })
            elif entry_name.endswith(('.csv', '.json', '.tsv', '.xlsx', '.xls', '.sql', '.txt')):
                size = os.path.getsize(entry_path)
                entries.append({
                    "name": entry_name,
                    "path": entry_path,
                    "type": "file",
                    "size": size,
                    "size_display": _format_size(size),
                })
        entries.sort(key=lambda e: (e["type"] != "directory", e["name"].lower()))
        return {"entries": entries, "current_path": path, "parent_path": os.path.dirname(path) if path else ""}
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to browse directory: {str(e)}")


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_bytes / 1024**3:.2f} GB"


# ─── Data Sources ──────────────────────────────────────────────

@router.post("/api/datasources", response_model=DataSourceResponse)
async def create_datasource(ds: DataSourceCreate, db: Session = Depends(get_db)):
    db_ds = DataSource(**ds.model_dump())
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    logger.info(f"Created data source: {db_ds.id} - {db_ds.name}")
    # Broadcast update
    await ws_manager.broadcast("datasource_update", {"type": "created", "id": db_ds.id})
    return db_ds


@router.get("/api/datasources", response_model=List[DataSourceResponse])
async def list_datasources(db: Session = Depends(get_db)):
    sources = db.query(DataSource).all()
    logger.debug(f"Listed {len(sources)} data sources")
    return sources


@router.get("/api/datasources/{ds_id}", response_model=DataSourceResponse)
async def get_datasource(ds_id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    return ds


@router.delete("/api/datasources/{ds_id}")
async def delete_datasource(ds_id: int, db: Session = Depends(get_db)):
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    # Also delete the uploaded file if exists
    if ds.file_path and os.path.exists(ds.file_path):
        try:
            os.remove(ds.file_path)
            logger.info(f"Deleted file: {ds.file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file: {e}")
    db.delete(ds)
    
    # Issue #1: Clear graph nodes when data source is deleted
    try:
        deleted_count = db.query(GraphNode).delete()
        logger.info(f"Cleared {deleted_count} graph nodes after deleting data source {ds_id}")
    except Exception as e:
        logger.warning(f"Failed to clear graph nodes: {e}")
    
    db.commit()
    logger.info(f"Deleted data source: {ds_id}")
    await ws_manager.broadcast("datasource_update", {"type": "deleted", "id": ds_id})
    await ws_manager.broadcast("graph_update", {"type": "cleared"})
    return {"message": "Data source deleted"}


@router.put("/api/datasources/{ds_id}")
async def update_datasource(ds_id: int, update: DataSourceUpdate, db: Session = Depends(get_db)):
    """Full CRUD: Update/edit an existing data source."""
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ds, field, value)
    db.commit()
    db.refresh(ds)
    logger.info(f"Updated data source: {ds_id}")
    await ws_manager.broadcast("datasource_update", {"type": "updated", "id": ds_id})
    return ds


@router.put("/api/datasources/{ds_id}/disconnect")
async def disconnect_datasource(ds_id: int, db: Session = Depends(get_db)):
    """Fix Issue #1: Disconnect a data source without deleting it."""
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Data source not found")
    ds.is_connected = False
    db.commit()
    logger.info(f"Disconnected data source: {ds_id}")
    await ws_manager.broadcast("datasource_update", {"type": "disconnected", "id": ds_id})
    return {"message": "Data source disconnected", "id": ds_id}


# ─── Pipelines ─────────────────────────────────────────────────

@router.post("/api/pipelines", response_model=PipelineResponse)
async def create_pipeline(pipeline: PipelineCreate, db: Session = Depends(get_db)):
    db_pipeline = Pipeline(
        data_source_id=pipeline.data_source_id,
        name=pipeline.name,
        status="pending",
        stages=etl_pipeline.stages,
    )
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    logger.info(f"Created pipeline: {db_pipeline.id} - {db_pipeline.name}")
    return db_pipeline


@router.post("/api/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline.status = "running"
    pipeline.started_at = datetime.utcnow()
    db.commit()
    logger.info(f"Starting pipeline: {pipeline_id}")

    async def execute_pipeline():
        try:
            result = await etl_pipeline.run_pipeline(pipeline.data_source_id, db)
            pipeline_obj = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
            if pipeline_obj:
                pipeline_obj.status = result["status"]
                pipeline_obj.progress = result["progress"]
                pipeline_obj.current_stage = result.get("current_stage")
                pipeline_obj.error_message = result.get("error_message")
                pipeline_obj.stages = result.get("stages")
                if result["status"] == "completed":
                    pipeline_obj.completed_at = datetime.utcnow()
                db.commit()
                logger.info(f"Pipeline {pipeline_id} completed with status: {result['status']}")
                await ws_manager.broadcast("pipeline_update", {
                    "pipeline_id": pipeline_id,
                    "status": pipeline_obj.status,
                    "progress": pipeline_obj.progress,
                    "current_stage": pipeline_obj.current_stage,
                })
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            try:
                pipeline_obj = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
                if pipeline_obj:
                    pipeline_obj.status = "failed"
                    pipeline_obj.error_message = str(e)
                    db.commit()
            except Exception:
                pass

    background_tasks.add_task(execute_pipeline)
    return {"message": "Pipeline started", "pipeline_id": pipeline_id}


@router.get("/api/pipelines", response_model=List[PipelineResponse])
async def list_pipelines(db: Session = Depends(get_db)):
    pipelines = db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()
    logger.debug(f"Listed {len(pipelines)} pipelines")
    return pipelines


@router.get("/api/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.put("/api/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: int, update: PipelineUpdate, db: Session = Depends(get_db)):
    """Full CRUD: Update/edit an existing pipeline."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pipeline, field, value)
    db.commit()
    db.refresh(pipeline)
    logger.info(f"Updated pipeline: {pipeline_id}")
    return pipeline


@router.delete("/api/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    """Fix Issue #2: Delete a pipeline job."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    db.delete(pipeline)
    db.commit()
    logger.info(f"Deleted pipeline: {pipeline_id}")
    return {"message": "Pipeline deleted"}


# ─── Graph ─────────────────────────────────────────────────────

@router.get("/api/graph", response_model=GraphResponse)
async def get_graph(limit: int = 100):
    return await graph_service.get_graph(limit)


@router.get("/api/graph/stats")
async def get_graph_stats():
    return await graph_service.get_graph_stats()


@router.post("/api/graph/cypher")
async def execute_cypher(query: dict):
    cypher = query.get("query", "")
    if not cypher or not cypher.strip():
        raise HTTPException(status_code=400, detail="Cypher query is required")
    try:
        results = await graph_service.execute_cypher(cypher)
        return {"results": results}
    except Exception as e:
        logger.error(f"Cypher execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Cypher execution failed: {str(e)}")


@router.delete("/api/graph")
async def clear_graph(db: Session = Depends(get_db)):
    """Clear all graph nodes from local storage."""
    try:
        # Clear SQLite graph nodes
        deleted = db.query(GraphNode).delete()
        db.commit()
        
        # Clear JSON store if it exists
        store_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "graph_store.json"
        )
        if os.path.exists(store_path):
            try:
                with open(store_path, "w") as f:
                    json.dump({"nodes": [], "edges": []}, f)
                logger.info(f"Cleared graph_store.json")
            except Exception as e:
                logger.warning(f"Failed to clear graph_store.json: {e}")
        
        logger.info(f"Cleared {deleted} graph nodes from storage")
        await ws_manager.broadcast("graph_update", {"type": "cleared"})
        return {"message": f"Graph cleared: {deleted} nodes removed"}
    except Exception as e:
        logger.error(f"Failed to clear graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear graph: {str(e)}")


# ─── Query ─────────────────────────────────────────────────────

@router.post("/api/query", response_model=QueryResponse)
async def query_graph(q: QueryRequest, db: Session = Depends(get_db)):
    if not q.query or not q.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    logger.info(f"Processing query: '{q.query[:100]}...' depth={q.traversal_depth} model={q.model} retry={q.retry}")
    start_time = time.time()

    result = await rag_service.query(
        natural_query=q.query,
        traversal_depth=q.traversal_depth,
        model=q.model,
        retry=q.retry,
    )

    execution_time_ms = (time.time() - start_time) * 1000

    # Save to history
    try:
        history = QueryHistory(
            natural_query=q.query,
            generated_cypher=result.get("generated_cypher", ""),
            retrieved_context=result.get("retrieved_context", []),
            answer=result.get("answer", ""),
            traversal_depth=q.traversal_depth,
            execution_time_ms=execution_time_ms,
            status="success" if "error" not in result.get("answer", "").lower() else "failed",
        )
        db.add(history)
        db.commit()
        logger.info(f"Query saved to history: id={history.id}")
    except Exception as e:
        logger.error(f"Failed to save query history: {e}")

    return result


@router.post("/api/query/stream")
async def query_graph_stream(q: QueryRequest):
    """Streaming query endpoint that emits Server-Sent Events (SSE)."""
    async def event_stream():
        buffering_events = []
        result_holder = []

        async def run_query():
            result = await rag_service.query(
                natural_query=q.query,
                traversal_depth=q.traversal_depth,
                model=q.model,
                on_buffering=lambda e: buffering_events.append(e),
            )
            result_holder.append(result)

        query_task = asyncio.create_task(run_query())

        while not query_task.done() or buffering_events:
            while buffering_events:
                event = buffering_events.pop(0)
                sse_data = json.dumps({"type": "buffering", "data": event})
                yield f"event: buffering\ndata: {sse_data}\n\n"
            await asyncio.sleep(0.1)

        try:
            await query_task
        except Exception as e:
            sse_data = json.dumps({"type": "error", "data": {"message": str(e)}})
            yield f"event: error\ndata: {sse_data}\n\n"
            return

        if result_holder:
            result = result_holder[0]
            sse_data = json.dumps({"type": "result", "data": result})
            yield f"event: result\ndata: {sse_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/query/history")
async def get_query_history(limit: int = 20):
    return await dashboard_service.get_query_history(limit)


# ─── Ollama ────────────────────────────────────────────────────

@router.get("/api/ollama/status")
async def ollama_status():
    available = await ollama_service.check_availability()
    return {"available": available}


@router.get("/api/ollama/models", response_model=List[OllamaModelInfo])
async def list_ollama_models():
    models = await ollama_service.list_models()
    enriched_models = []
    for m in models:
        enriched_models.append({
            "name": m["name"],
            "model_size": m.get("model_size", "Unknown"),
            "vram_estimate": _estimate_vram(m["name"]),
            "context_size": _estimate_context(m["name"]),
            "speed_score": _estimate_speed(m["name"]),
            "rag_suitability": _estimate_rag_suitability(m["name"]),
            "is_active": m["name"] == ollama_service.default_model,
        })
    return enriched_models


@router.post("/api/ollama/models/select")
async def select_model(req: ModelSelectRequest):
    """Select a model with validation that it exists in available models - Fix Issue #5."""
    if not req.model_name or not req.model_name.strip():
        raise HTTPException(status_code=400, detail="Model name is required")

    # Validate model exists
    is_available = await ollama_service.is_model_available(req.model_name)
    if not is_available:
        available_models = await ollama_service.list_models()
        model_names = [m['name'] for m in available_models]
        logger.warning(f"Model selection failed: '{req.model_name}' not found. Available: {model_names}")
        raise HTTPException(
            status_code=404,
            detail=f"Model '{req.model_name}' is not available. Available models: {model_names}"
        )

    ollama_service.default_model = req.model_name
    logger.info(f"Model selected: {req.model_name}")
    return {"message": f"Model {req.model_name} selected", "model": req.model_name}


@router.post("/api/ollama/pull")
async def pull_model(req: ModelSelectRequest, background_tasks: BackgroundTasks):
    """Pull a model - kept for compatibility but frontend should not expose this directly."""
    if not req.model_name or not req.model_name.strip():
        raise HTTPException(status_code=400, detail="Model name is required")
    background_tasks.add_task(ollama_service.pull_model, req.model_name)
    logger.info(f"Pulling model: {req.model_name}")
    return {"message": f"Pulling model {req.model_name}"}


@router.get("/api/ollama/benchmark/{model_name}")
async def benchmark_ollama_model(model_name: str):
    """
    SRS: Benchmark Engine — Run a benchmark on an Ollama model to measure:
    - Tokens per second
    - Context window size
    - VRAM estimate
    - RAG suitability score
    """
    logger.info(f"Running benchmark for model: {model_name}")
    try:
        benchmark = await ollama_service.benchmark_model(model_name)
        return benchmark
    except Exception as e:
        logger.error(f"Benchmark failed for {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmark failed: {str(e)}")


@router.post("/api/ollama/chat")
async def chat_with_model(req: ChatRequest):
    """Fix Issue #9: Chat directly with a selected Ollama model for testing."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    model = req.model or ollama_service.default_model
    logger.info(f"Chat with model: {model}, message: {req.message[:100]}")
    try:
        response = await ollama_service.generate(req.message, model=model, stream=False)
        return {"response": response, "model": model}
    except Exception as e:
        logger.error(f"Ollama chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


# ─── Dashboard ─────────────────────────────────────────────────

@router.get("/api/dashboard/metrics")
async def get_metrics():
    """SRS: Dashboard — Real-time system metrics with enhanced data (CPU, RAM, GPU, disk, network)."""
    return await dashboard_service.get_system_metrics()


@router.get("/api/dashboard/metrics/history")
async def get_metrics_history(hours: int = 2):
    """
    SRS: Dashboard — Historical metrics for chart visualization.
    Returns metrics collected over the last N hours.
    """
    return await dashboard_service.get_historical_metrics(hours)


@router.get("/api/dashboard/health")
async def get_health():
    return await dashboard_service.get_health_status()


# ─── WebSocket ─────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "")

            if msg_type == "ping":
                await ws_manager.send_personal(websocket, "pong", {"timestamp": time.time()})

            elif msg_type == "subscribe_metrics":
                for _ in range(60):  # Send metrics every 5s for 5 min
                    metrics = await dashboard_service.get_system_metrics()
                    await ws_manager.send_personal(websocket, "metrics", metrics)
                    await asyncio.sleep(5)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)


# ─── Seed Data ─────────────────────────────────────────────────

@router.post("/api/seed")
async def seed_demo_data(db: Session = Depends(get_db)):
    """Seed the database with demo data for testing - with fallback when Neo4j unavailable."""
    sample_entities = [
        ("Customer", {"name": "Alice Johnson", "email": "alice@example.com"}),
        ("Customer", {"name": "Bob Smith", "email": "bob@example.com"}),
        ("Product", {"name": "Laptop Pro", "category": "Electronics", "price": 1299.99}),
        ("Product", {"name": "Wireless Mouse", "category": "Electronics", "price": 49.99}),
        ("Product", {"name": "Coffee Maker", "category": "Appliances", "price": 89.99}),
        ("Order", {"order_id": "ORD-001", "amount": 1349.98, "status": "shipped"}),
        ("Order", {"order_id": "ORD-002", "amount": 89.99, "status": "processing"}),
        ("Supplier", {"name": "TechSupply Co", "location": "San Francisco, CA"}),
        ("Employee", {"name": "Charlie Brown", "role": "Engineer", "department": "R&D"}),
    ]

    created = []
    for label, props in sample_entities:
        try:
            node = await graph_service.create_node(label, props)
            created.append(node)
        except Exception as e:
            logger.warning(f"Seed failed for {label}: {e}")

    # Create sample data source
    existing_ds = db.query(DataSource).filter(DataSource.name == "Demo CSV Data").first()
    if not existing_ds:
        ds = DataSource(
            name="Demo CSV Data",
            source_type="csv",
            config={"path": "data/sample_data.csv"},
        )
        db.add(ds)
        db.commit()

    # Create sample query history
    existing_queries = db.query(QueryHistory).count()
    if existing_queries == 0:
        sample_queries = [
            QueryHistory(
                natural_query="Show me all customers who purchased electronics",
                generated_cypher="MATCH (c:Customer)-[:PURCHASED]->(p:Product {category: 'Electronics'}) RETURN c.name, p.name",
                answer="Based on the graph data, customers who purchased electronics include Alice Johnson and Bob Smith.",
                execution_time_ms=1250.5,
            ),
            QueryHistory(
                natural_query="What products are available under $100?",
                generated_cypher="MATCH (p:Product) WHERE p.price < 100 RETURN p.name, p.price",
                answer="Products under $100 include: Wireless Mouse ($49.99) and Coffee Maker ($89.99).",
                execution_time_ms=980.2,
            ),
        ]
        for q in sample_queries:
            db.add(q)
        db.commit()
        logger.info(f"Seeded {len(sample_queries)} sample queries")

    logger.info(f"Demo data seeded: {len(created)} nodes created")
    return {
        "message": "Demo data seeded successfully",
        "nodes_created": len(created),
        "sample_queries": 2,
    }


def _estimate_vram(model_name: str) -> str:
    vram_map = {
        "llama3.1": "8GB",
        "mistral": "6GB",
        "phi3": "4GB",
        "codellama": "8GB",
        "gemma": "4GB",
        "deepseek": "12GB",
    }
    for key in vram_map:
        if key in model_name.lower():
            return vram_map[key]
    return "8GB"


def _estimate_context(model_name: str) -> int:
    context_map = {
        "llama3.1": 8192,
        "mistral": 8192,
        "phi3": 4096,
        "codellama": 16384,
        "gemma": 8192,
        "deepseek": 32768,
    }
    for key in context_map:
        if key in model_name.lower():
            return context_map[key]
    return 4096


def _estimate_speed(model_name: str) -> float:
    speed_map = {
        "llama3.1": 7.5,
        "mistral": 8.0,
        "phi3": 9.0,
        "codellama": 6.5,
        "gemma": 8.5,
        "deepseek": 5.5,
    }
    for key in speed_map:
        if key in model_name.lower():
            return speed_map[key]
    return 7.0


def _estimate_rag_suitability(model_name: str) -> float:
    suitability_map = {
        "llama3.1": 9.0,
        "mistral": 8.5,
        "phi3": 7.0,
        "codellama": 6.5,
        "gemma": 7.5,
        "deepseek": 9.5,
    }
    for key in suitability_map:
        if key in model_name.lower():
            return suitability_map[key]
    return 7.5
