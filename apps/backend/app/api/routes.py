from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import json
import logging
import asyncio

from datetime import datetime

from app.core.database import get_db, init_db
from app.core.websocket_manager import ws_manager
from app.schemas.api_schemas import (
    DataSourceCreate, DataSourceResponse,
    PipelineCreate, PipelineResponse,
    QueryRequest, QueryResponse,
    OllamaModelInfo, ModelSelectRequest,
    SystemMetricsResponse, GraphResponse,
)
from app.models.database_models import DataSource, Pipeline, QueryHistory, OllamaModel
from app.services.graph_service import graph_service
from app.services.ollama_service import ollama_service
from app.services.rag_service import rag_service
from app.services.etl_pipeline import etl_pipeline
from app.services.dashboard_service import dashboard_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.on_event("startup")
async def startup():
    init_db()


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


# ─── Data Sources ──────────────────────────────────────────────

@router.post("/api/datasources", response_model=DataSourceResponse)
async def create_datasource(ds: DataSourceCreate, db: Session = Depends(get_db)):
    db_ds = DataSource(**ds.model_dump())
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    return db_ds


@router.get("/api/datasources", response_model=List[DataSourceResponse])
async def list_datasources(db: Session = Depends(get_db)):
    return db.query(DataSource).all()


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
    db.delete(ds)
    db.commit()
    return {"message": "Data source deleted"}


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
    return db_pipeline


@router.post("/api/pipelines/{pipeline_id}/run")
async def run_pipeline(pipeline_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    pipeline.status = "running"
    db.commit()

    async def execute_pipeline():
        result = await etl_pipeline.run_pipeline(pipeline.data_source_id, db)
        pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
        pipeline.status = result["status"]
        pipeline.progress = result["progress"]
        pipeline.current_stage = result.get("current_stage")
        pipeline.error_message = result.get("error_message")
        pipeline.stages = result.get("stages")
        if result["status"] == "completed":
            pipeline.completed_at = datetime.utcnow()
        db.commit()
        await ws_manager.broadcast("pipeline_update", {
            "pipeline_id": pipeline_id,
            "status": pipeline.status,
            "progress": pipeline.progress,
            "current_stage": pipeline.current_stage,
        })

    background_tasks.add_task(execute_pipeline)
    return {"message": "Pipeline started", "pipeline_id": pipeline_id}


@router.get("/api/pipelines", response_model=List[PipelineResponse])
async def list_pipelines(db: Session = Depends(get_db)):
    return db.query(Pipeline).order_by(Pipeline.created_at.desc()).all()


@router.get("/api/pipelines/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: int, db: Session = Depends(get_db)):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


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
    if not cypher:
        raise HTTPException(status_code=400, detail="Cypher query is required")
    results = await graph_service.execute_cypher(cypher)
    return {"results": results}


# ─── Query ─────────────────────────────────────────────────────

@router.post("/api/query", response_model=QueryResponse)
async def query_graph(q: QueryRequest, db: Session = Depends(get_db)):
    result = await rag_service.query(
        natural_query=q.query,
        traversal_depth=q.traversal_depth,
        model=q.model,
    )

    # Save to history
    history = QueryHistory(
        natural_query=q.query,
        generated_cypher=result.get("generated_cypher", ""),
        retrieved_context=result.get("retrieved_context", []),
        answer=result.get("answer", ""),
        traversal_depth=q.traversal_depth,
        execution_time_ms=result.get("execution_time_ms", 0),
    )
    db.add(history)
    db.commit()

    return result


@router.post("/api/query/stream")
async def query_graph_stream(q: QueryRequest):
    """
    Streaming query endpoint that emits Server-Sent Events (SSE) for real-time
    buffering status updates while waiting for Ollama response.
    """
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
    return {"message": f"Model {req.model_name} selected", "model": req.model_name}


@router.post("/api/ollama/pull")
async def pull_model(req: ModelSelectRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(ollama_service.pull_model, req.model_name)
    return {"message": f"Pulling model {req.model_name}"}


# ─── Dashboard ─────────────────────────────────────────────────

@router.get("/api/dashboard/metrics")
async def get_metrics():
    return await dashboard_service.get_system_metrics()


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
                await ws_manager.send_personal(websocket, "pong", {"timestamp": __import__("time").time()})

            elif msg_type == "subscribe_metrics":
                import asyncio
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
    """Seed the database with demo data for testing."""
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
    ds = DataSource(
        name="Demo CSV Data",
        source_type="csv",
        config={"path": "data/sample_data.csv"},
    )
    db.add(ds)
    db.commit()

    # Create sample query history
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

    return {
        "message": "Demo data seeded successfully",
        "nodes_created": len(created),
        "sample_queries": len(sample_queries),
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
