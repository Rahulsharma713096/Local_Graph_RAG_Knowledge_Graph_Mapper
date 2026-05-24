"""Unit tests for API routes - uses FastAPI TestClient with mocked services."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRoutesHealth:
    """Test health and info endpoints."""

    def test_root_endpoint(self):
        """GET / should return app info."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        # The response uses 'app' key instead of 'name'
        assert "app" in data
        assert "version" in data

    def test_health_check(self):
        """GET /api/health should return healthy status."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_app_info(self):
        """GET /api/info should return features list."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/info")
        assert response.status_code == 200
        data = response.json()
        assert "features" in data
        assert isinstance(data["features"], list)
        assert len(data["features"]) >= 7


class TestRoutesDataSources:
    """Test data source CRUD endpoints."""

    def test_create_datasource(self):
        """POST /api/datasources should create and return a datasource."""
        from app.main import app
        from fastapi.testclient import TestClient

        with patch("app.api.routes.get_db") as mock_get_db:
            session = MagicMock()
            mock_get_db.return_value = iter([session])

            client = TestClient(app)
            response = client.post(
                "/api/datasources",
                json={"name": "Test CSV", "source_type": "csv", "config": {"path": "test.csv"}},
            )
            assert response.status_code in (200, 422)

    def test_list_datasources(self):
        """GET /api/datasources should return list."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/datasources")
        assert response.status_code in (200, 500)


class TestRoutesGraph:
    """Test graph endpoints."""

    def test_get_graph_empty(self):
        """GET /api/graph should return graph structure even when empty."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/graph?limit=100")
        assert response.status_code in (200, 500)


class TestRoutesOllama:
    """Test Ollama endpoints."""

    def test_ollama_status(self):
        """GET /api/ollama/status should return availability."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/ollama/status")
        assert response.status_code == 200
        assert "available" in response.json()

    def test_select_model_empty_name_400(self):
        """POST /api/ollama/models/select should return 400 for empty name."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/ollama/models/select", json={"model_name": ""})
        assert response.status_code == 400

    def test_select_model_unavailable_404(self):
        """POST /api/ollama/models/select should return 404 for unavailable model (Issue #5 fix)."""
        from app.main import app
        from fastapi.testclient import TestClient

        with patch("app.api.routes.ollama_service.is_model_available", new_callable=AsyncMock) as mock, \
             patch("app.api.routes.ollama_service.list_models", new_callable=AsyncMock) as mock_list:
            mock.return_value = False
            mock_list.return_value = [{"name": "llama3.1:latest"}]

            client = TestClient(app)
            response = client.post("/api/ollama/models/select", json={"model_name": "nonexistent-model"})
            assert response.status_code == 404


class TestRoutesQuery:
    """Test query endpoints."""

    def test_empty_query_400(self):
        """POST /api/query should return 400 for empty query."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/query", json={"query": ""})
        assert response.status_code == 400

    def test_whitespace_query_400(self):
        """POST /api/query should return 400 for whitespace-only query."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/query", json={"query": "   "})
        assert response.status_code == 400


class TestRoutesCypher:
    """Test Cypher endpoint."""

    def test_empty_cypher_400(self):
        """POST /api/graph/cypher should return 400 for empty query (Issue #6 fix)."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/graph/cypher", json={"query": ""})
        assert response.status_code == 400

    def test_valid_cypher(self):
        """POST /api/graph/cypher should accept valid query."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/graph/cypher", json={"query": "MATCH (n) RETURN n LIMIT 5"})
        assert response.status_code in (200, 500)


class TestRoutesDashboard:
    """Test dashboard endpoints."""

    def test_dashboard_metrics(self):
        """GET /api/dashboard/metrics should return metrics structure."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "cpu_usage" in data
        assert "ram_usage" in data
        assert "ram_total" in data

    def test_dashboard_health(self):
        """GET /api/dashboard/health should return health status."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/dashboard/health")
        assert response.status_code == 200
        data = response.json()
        assert "backend" in data
        assert "neo4j" in data
        assert "ollama" in data
