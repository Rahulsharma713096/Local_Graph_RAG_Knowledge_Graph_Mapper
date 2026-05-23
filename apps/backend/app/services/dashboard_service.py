import psutil
import logging
from typing import Dict, Any, Optional
from app.services.graph_service import graph_service

logger = logging.getLogger(__name__)


class DashboardService:
    async def get_system_metrics(self) -> Dict[str, Any]:
        metrics = {
            "cpu_usage": 0.0,
            "ram_usage": 0.0,
            "ram_total": 0.0,
            "gpu_usage": None,
            "gpu_memory": None,
            "neo4j_heap_usage": None,
            "active_pipelines": 0,
        }

        try:
            metrics["cpu_usage"] = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            metrics["ram_usage"] = memory.percent
            metrics["ram_total"] = round(memory.total / (1024**3), 2)  # GB
        except Exception as e:
            logger.warning(f"Failed to get CPU/RAM metrics: {e}")

        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            metrics["gpu_usage"] = util.gpu
            metrics["gpu_memory"] = round(mem_info.used / (1024**3), 2)
            pynvml.nvmlShutdown()
        except Exception:
            pass  # GPU metrics optional

        try:
            stats = await graph_service.get_graph_stats()
            metrics["active_pipelines"] = stats.get("node_count", 0) if stats else 0
        except Exception:
            pass

        return metrics

    async def get_health_status(self) -> Dict[str, str]:
        status = {
            "backend": "healthy",
            "neo4j": "unknown",
            "ollama": "unknown",
        }

        try:
            neo4j_ok = await graph_service.verify_connection()
            status["neo4j"] = "healthy" if neo4j_ok else "unhealthy"
        except Exception:
            status["neo4j"] = "unhealthy"

        try:
            from app.services.ollama_service import ollama_service
            ollama_ok = await ollama_service.check_availability()
            status["ollama"] = "healthy" if ollama_ok else "unhealthy"
        except Exception:
            status["ollama"] = "unhealthy"

        return status

    async def get_query_history(self, limit: int = 20) -> list:
        from app.core.database import SessionLocal
        from app.models.database_models import QueryHistory

        db = SessionLocal()
        try:
            queries = (
                db.query(QueryHistory)
                .order_by(QueryHistory.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": q.id,
                    "natural_query": q.natural_query,
                    "generated_cypher": q.generated_cypher,
                    "answer": q.answer[:200] if q.answer else "",
                    "execution_time_ms": q.execution_time_ms,
                    "status": q.status,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
                for q in queries
            ]
        finally:
            db.close()


dashboard_service = DashboardService()
