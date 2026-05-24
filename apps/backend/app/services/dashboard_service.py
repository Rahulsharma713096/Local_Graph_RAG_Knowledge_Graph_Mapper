import psutil
import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from app.services.graph_service import graph_service
from app.core.database import SessionLocal
from app.models.database_models import Pipeline, SystemMetric

logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(self):
        self._metrics_task: Optional[asyncio.Task] = None

    async def start_metrics_collection(self):
        """SRS: Start periodic metrics storage to SQLite for historical charts."""
        if self._metrics_task is None or self._metrics_task.done():
            self._metrics_task = asyncio.create_task(self._periodic_metrics_collect())
            logger.info("Periodic metrics collection started")

    async def _periodic_metrics_collect(self):
        """Collect and store system metrics every 30 seconds."""
        while True:
            try:
                metrics = await self._collect_metrics()
                await self._store_metrics(metrics)
            except Exception as e:
                logger.warning(f"Metrics collection error: {e}")
            await asyncio.sleep(30)

    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        metrics = {
            "cpu_usage": 0.0,
            "ram_usage": 0.0,
            "ram_total": 0.0,
            "gpu_usage": None,
            "gpu_memory": None,
            "neo4j_heap_usage": None,
            "active_pipelines": 0,
            "disk_usage": 0.0,
            "network_bytes_sent": 0,
            "network_bytes_recv": 0,
            "process_count": 0,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            metrics["cpu_usage"] = psutil.cpu_percent(interval=0.3)
            memory = psutil.virtual_memory()
            metrics["ram_usage"] = memory.percent
            metrics["ram_total"] = round(memory.total / (1024**3), 2)
            disk = psutil.disk_usage("/")
            metrics["disk_usage"] = disk.percent
            metrics["process_count"] = len(psutil.pids())

            net = psutil.net_io_counters()
            metrics["network_bytes_sent"] = net.bytes_sent
            metrics["network_bytes_recv"] = net.bytes_recv
        except Exception as e:
            logger.warning(f"Failed to get system metrics: {e}")

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
            db = SessionLocal()
            try:
                active = db.query(Pipeline).filter(Pipeline.status == "running").count()
                metrics["active_pipelines"] = active
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get active pipeline count: {e}")
            metrics["active_pipelines"] = 0

        return metrics

    async def _store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics snapshot to SQLite for historical queries."""
        try:
            db = SessionLocal()
            try:
                record = SystemMetric(
                    cpu_usage=metrics.get("cpu_usage"),
                    ram_usage=metrics.get("ram_usage"),
                    ram_total=metrics.get("ram_total"),
                    gpu_usage=metrics.get("gpu_usage"),
                    gpu_memory=metrics.get("gpu_memory"),
                    neo4j_heap_usage=metrics.get("neo4j_heap_usage"),
                    active_pipelines=metrics.get("active_pipelines", 0),
                )
                db.add(record)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to store metrics: {e}")

    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics (for real-time display)."""
        return await self._collect_metrics()

    async def get_historical_metrics(self, hours: int = 2) -> List[Dict[str, Any]]:
        """
        SRS: Dashboard — Get historical metrics for charts.
        Returns metrics recorded in the last N hours.
        """
        try:
            db = SessionLocal()
            try:
                since = datetime.utcnow() - timedelta(hours=hours)
                records = (
                    db.query(SystemMetric)
                    .filter(SystemMetric.recorded_at >= since)
                    .order_by(SystemMetric.recorded_at.asc())
                    .all()
                )
                return [
                    {
                        "cpu_usage": r.cpu_usage,
                        "ram_usage": r.ram_usage,
                        "gpu_usage": r.gpu_usage,
                        "active_pipelines": r.active_pipelines,
                        "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                    }
                    for r in records
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get historical metrics: {e}")
            return []

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
