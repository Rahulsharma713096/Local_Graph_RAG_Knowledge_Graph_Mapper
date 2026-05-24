"""Unit tests for DashboardService - covers metrics, health, query history, active pipelines."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


class TestDashboardServiceInit:
    """Test DashboardService initialization."""

    async def test_singleton_exists(self):
        """dashboard_service singleton should be importable."""
        from app.services.dashboard_service import dashboard_service
        assert dashboard_service is not None
        assert hasattr(dashboard_service, "get_system_metrics")
        assert hasattr(dashboard_service, "get_health_status")
        assert hasattr(dashboard_service, "get_query_history")


class TestDashboardServiceSystemMetrics:
    """Test system metrics gathering."""

    async def test_get_system_metrics_basic(self, patch_psutil, patch_pynvml):
        """get_system_metrics should return all expected keys."""
        from app.services.dashboard_service import dashboard_service

        metrics = await dashboard_service.get_system_metrics()

        expected_keys = {"cpu_usage", "ram_usage", "ram_total", "gpu_usage", "gpu_memory", "neo4j_heap_usage", "active_pipelines"}
        assert expected_keys.issubset(metrics.keys())

    async def test_get_system_metrics_cpu_ram(self, patch_psutil, patch_pynvml):
        """get_system_metrics should return CPU and RAM values from psutil."""
        from app.services.dashboard_service import dashboard_service

        metrics = await dashboard_service.get_system_metrics()
        assert metrics["cpu_usage"] == 45.2
        assert metrics["ram_usage"] == 62.5
        assert metrics["ram_total"] > 0

    async def test_get_system_metrics_gpu(self, patch_psutil, patch_pynvml):
        """get_system_metrics should return GPU metrics."""
        from app.services.dashboard_service import dashboard_service

        metrics = await dashboard_service.get_system_metrics()
        assert metrics["gpu_usage"] == 35.0
        assert metrics["gpu_memory"] > 0

    async def test_get_system_metrics_gpu_import_fail(self, patch_psutil):
        """get_system_metrics should handle pynvml import failure by inserting None into sys.modules."""
        import sys
        old = sys.modules.get("pynvml", None)
        sys.modules["pynvml"] = None
        try:
            # Clear the module-level reference; the function body will see sys.modules["pynvml"] = None
            from app.services.dashboard_service import dashboard_service
            metrics = await dashboard_service.get_system_metrics()
            assert metrics["gpu_usage"] is None
            assert metrics["gpu_memory"] is None
        finally:
            if old is not None:
                sys.modules["pynvml"] = old
            else:
                sys.modules.pop("pynvml", None)

    async def test_get_system_metrics_active_pipelines(self, patch_psutil, patch_pynvml):
        """get_system_metrics should query SQLite for active pipelines (Issue #4 fix)."""
        from app.services.dashboard_service import dashboard_service

        # SessionLocal is imported at module level in dashboard_service, so patch at that level
        with patch("app.services.dashboard_service.SessionLocal") as mock_session:
            session = MagicMock()
            query_mock = MagicMock()
            query_mock.filter.return_value = query_mock
            query_mock.count.return_value = 3
            session.query.return_value = query_mock
            mock_session.return_value = session

            metrics = await dashboard_service.get_system_metrics()
            assert metrics["active_pipelines"] == 3

    async def test_get_system_metrics_active_pipelines_error(self, patch_psutil, patch_pynvml):
        """get_system_metrics should default to 0 on pipeline query error."""
        from app.services.dashboard_service import dashboard_service

        with patch("app.services.dashboard_service.SessionLocal") as mock_session:
            mock_session.side_effect = Exception("DB error")

            metrics = await dashboard_service.get_system_metrics()
            assert metrics["active_pipelines"] == 0

    async def test_get_system_metrics_psutil_error(self, patch_pynvml):
        """get_system_metrics should handle psutil errors gracefully."""
        from app.services.dashboard_service import dashboard_service

        with patch("app.services.dashboard_service.psutil") as mock_psutil:
            mock_psutil.cpu_percent.side_effect = Exception("CPU error")
            mock_psutil.virtual_memory.side_effect = Exception("Memory error")

            metrics = await dashboard_service.get_system_metrics()
            assert metrics["cpu_usage"] == 0.0
            assert metrics["ram_usage"] == 0.0
            assert metrics["ram_total"] == 0.0


class TestDashboardServiceHealth:
    """Test health status gathering."""

    async def test_get_health_status(self):
        """get_health_status should return status for all services."""
        from app.services.dashboard_service import dashboard_service

        # Patch ollama_service at the source (app.services.ollama_service module)
        with patch("app.services.dashboard_service.graph_service.verify_connection", new_callable=AsyncMock) as mock_neo4j, \
             patch("app.services.ollama_service.ollama_service.check_availability", new_callable=AsyncMock) as mock_ollama:
            mock_neo4j.return_value = True
            mock_ollama.return_value = True

            status = await dashboard_service.get_health_status()
            assert status["backend"] == "healthy"
            assert status["neo4j"] == "healthy"
            assert status["ollama"] == "healthy"

    async def test_get_health_status_unhealthy(self):
        """get_health_status should report unhealthy services."""
        from app.services.dashboard_service import dashboard_service

        with patch("app.services.dashboard_service.graph_service.verify_connection", new_callable=AsyncMock) as mock_neo4j, \
             patch("app.services.ollama_service.ollama_service.check_availability", new_callable=AsyncMock) as mock_ollama:
            mock_neo4j.return_value = False
            mock_ollama.return_value = False

            status = await dashboard_service.get_health_status()
            assert status["neo4j"] == "unhealthy"
            assert status["ollama"] == "unhealthy"

    async def test_get_health_status_unhealthy_on_error(self):
        """get_health_status should report unhealthy on connection error."""
        from app.services.dashboard_service import dashboard_service

        with patch("app.services.dashboard_service.graph_service.verify_connection", new_callable=AsyncMock) as mock_neo4j:
            mock_neo4j.side_effect = Exception("Connection failed")

            status = await dashboard_service.get_health_status()
            assert status["neo4j"] == "unhealthy"


class TestDashboardServiceQueryHistory:
    """Test query history retrieval."""

    async def test_get_query_history_empty(self, patch_session_local):
        """get_query_history should return empty list when no queries."""
        from app.services.dashboard_service import dashboard_service

        history = await dashboard_service.get_query_history(limit=10)
        assert history == []

    async def test_get_query_history_with_data(self, patch_session_local):
        """get_query_history should return formatted query records."""
        from app.services.dashboard_service import dashboard_service
        from datetime import datetime

        mock_query = MagicMock()
        mock_query.id = 1
        mock_query.natural_query = "test query"
        mock_query.generated_cypher = "MATCH (n) RETURN n"
        mock_query.answer = "Here are the results"
        mock_query.execution_time_ms = 150.5
        mock_query.status = "success"
        mock_query.created_at = datetime(2024, 1, 1, 12, 0, 0)

        session = MagicMock()
        query_mock = MagicMock()
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = [mock_query]
        session.query.return_value = query_mock

        with patch("app.core.database.SessionLocal") as mock_session:
            mock_session.return_value = session

            history = await dashboard_service.get_query_history(limit=20)
            assert len(history) == 1
            assert history[0]["id"] == 1
            assert history[0]["natural_query"] == "test query"
            assert history[0]["execution_time_ms"] == 150.5

    async def test_get_query_history_default_limit(self, patch_session_local):
        """get_query_history should default to 20."""
        from app.services.dashboard_service import dashboard_service

        session = MagicMock()
        query_mock = MagicMock()
        query_mock.order_by.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.all.return_value = []
        session.query.return_value = query_mock

        with patch("app.core.database.SessionLocal") as mock_session:
            mock_session.return_value = session

            await dashboard_service.get_query_history()
            query_mock.limit.assert_called_with(20)


class TestDashboardServiceEdgeCases:
    """Test edge cases for DashboardService."""

    async def test_health_status_ollama_error(self):
        """get_health_status should handle ollama_service import error."""
        from app.services.dashboard_service import dashboard_service

        with patch("app.services.dashboard_service.graph_service.verify_connection", new_callable=AsyncMock) as mock_neo4j, \
             patch("app.services.ollama_service.ollama_service.check_availability", new_callable=AsyncMock) as mock_ollama:
            mock_neo4j.return_value = True
            mock_ollama.side_effect = Exception("Ollama error")

            status = await dashboard_service.get_health_status()
            assert status["ollama"] == "unhealthy"
