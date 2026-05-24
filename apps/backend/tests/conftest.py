"""Shared fixtures and mocks for all unit tests."""

import os
import sys
import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import AsyncGenerator, Generator

# Ensure the backend app is importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))


# ── Fixtures: Async Support ──────────────────────────────────────

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Fixtures: Database SessionLocal (patch at source) ────────────

@pytest.fixture
def mock_session():
    """Create a base mock SQLAlchemy session with query chain support."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.close = MagicMock()
    query_mock = MagicMock()
    query_mock.filter.return_value = query_mock
    query_mock.order_by.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.offset.return_value = query_mock
    query_mock.all.return_value = []
    query_mock.first.return_value = None
    query_mock.count.return_value = 0
    query_mock.distinct.return_value = query_mock
    session.query.return_value = query_mock
    return session


@pytest.fixture
def patch_session_local(mock_session):
    """Patch SessionLocal at the source (app.core.database) to return mock_session."""
    with patch("app.core.database.SessionLocal") as mock:
        mock.return_value = mock_session
        yield mock


# ── Fixtures: Neo4j Mocking ──────────────────────────────────────

@pytest.fixture
def mock_neo4j_session():
    """Create a mock Neo4j async session with proper async iteration protocol."""
    session = AsyncMock()

    # Create a proper async iterable for session.run results
    class AsyncRecordIterator:
        """Proper async iterator for Neo4j records supporting async for."""

        def __init__(self, records=None):
            self.records = records or []
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.records):
                raise StopAsyncIteration
            item = self.records[self.index]
            self.index += 1
            return item

    # Configure session.run to return an AsyncMock with proper async iteration
    async def mock_run(query, **kwargs):
        result = AsyncMock()
        records_list = []
        result.single.return_value = None
        # Support async for via __aiter__
        record_iter = AsyncRecordIterator(records_list)
        result.__aiter__.return_value = record_iter
        return result

    session.run = mock_run
    return session


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    """Create a mock Neo4j async driver."""
    driver = AsyncMock()
    driver.session.return_value.__aenter__.return_value = mock_neo4j_session
    driver.close = AsyncMock()
    return driver


# ── Fixtures: Ollama Mocking ─────────────────────────────────────

@pytest.fixture
def patch_ollama_get_client():
    """Patch OllamaService._get_client with a mock for general Ollama tests.

    POST /api/generate -> returns "Generated text response"
    POST /api/show      -> returns model info with context_length=8192
    POST /api/pull      -> streaming pull response
    """
    with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
        client = AsyncMock()

        # GET /api/tags
        mock_tags_resp = MagicMock()
        mock_tags_resp.status_code = 200
        mock_tags_resp.json.return_value = {
            "models": [
                {"name": "llama3.1:latest", "size": 4690000000},
                {"name": "mistral:latest", "size": 4100000000},
            ]
        }

        # POST /api/generate (non-streaming)
        mock_gen_resp = MagicMock()
        mock_gen_resp.status_code = 200
        mock_gen_resp.json.return_value = {
            "response": "Generated text response",
            "done": True,
        }

        # POST /api/show — returns model info
        mock_show_resp = MagicMock()
        mock_show_resp.status_code = 200
        mock_show_resp.json.return_value = {
            "size": 4690000000,
            "context_length": 8192,
            "parameters": "7B",
        }

        # POST /api/generate streaming — return a context-manager-able response
        class StreamResponse:
            """Simulates httpx streaming response with async context manager."""

            def __init__(self):
                self.status_code = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def aiter_lines(self):
                for line in [
                    '{"response": "Hello", "done": false}',
                    '{"response": " world", "done": false}',
                    '{"response": "!", "done": true}',
                ]:
                    yield line

        client.get = AsyncMock(return_value=mock_tags_resp)

        # Route POST by URL path
        async def post_side_effect(url, **kwargs):
            if "/api/show" in str(url):
                return mock_show_resp
            return mock_gen_resp

        client.post = AsyncMock(side_effect=post_side_effect)

        # stream() should return an object with __aenter__ directly, not wrapped in coroutine
        # Use a regular function (not async) that returns the StreamResponse
        client.stream = MagicMock(return_value=StreamResponse())
        client.aclose = AsyncMock()

        mock.return_value = client
        yield mock


# ── Fixtures: psutil Mocking ─────────────────────────────────────

@pytest.fixture
def patch_psutil():
    """Patch psutil to avoid system dependency."""
    with patch("app.services.dashboard_service.psutil") as mock:
        mock.cpu_percent.return_value = 45.2
        memory_mock = MagicMock()
        memory_mock.percent = 62.5
        memory_mock.total = 17000000000
        mock.virtual_memory.return_value = memory_mock
        yield mock


# ── Fixtures: pynvml Mocking ─────────────────────────────────────

@pytest.fixture
def patch_pynvml():
    """Patch pynvml by inserting a mock into sys.modules (imported inside function body)."""
    import sys
    mock = MagicMock(name="pynvml")
    mock.nvmlInit = MagicMock()
    handle = MagicMock()
    mock.nvmlDeviceGetHandleByIndex.return_value = handle
    util = MagicMock()
    util.gpu = 35.0
    mock.nvmlDeviceGetUtilizationRates.return_value = util
    mem = MagicMock()
    mem.used = 4000000000
    mock.nvmlDeviceGetMemoryInfo.return_value = mem
    mock.nvmlShutdown = MagicMock()

    old = sys.modules.get("pynvml", None)
    sys.modules["pynvml"] = mock
    yield mock
    if old is not None:
        sys.modules["pynvml"] = old
    else:
        sys.modules.pop("pynvml", None)


# ── Fixtures: Embedding Service Mocking ──────────────────────────

@pytest.fixture(autouse=True)
def patch_embedding():
    """Auto-patch embedding_service to avoid ML dependency."""
    import numpy as np
    with patch("app.services.rag_service.embedding_service") as mock:
        mock.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock.search.return_value = [
            {"index": 0, "score": 0.95},
            {"index": 1, "score": 0.87},
        ]
        yield mock


# ── Fixtures: Graph Service Mocking ──────────────────────────────

@pytest.fixture
def mock_graph_service():
    """Mock graph_service for services that depend on it (rag, etl, dashboard)."""
    with patch("app.services.rag_service.graph_service") as mock_rag, \
         patch("app.services.etl_pipeline.graph_service") as mock_etl, \
         patch("app.services.dashboard_service.graph_service") as mock_dash:

        mock_rag.get_graph_stats = AsyncMock(return_value={
            "node_count": 10,
            "edge_count": 5,
            "node_labels": ["Customer", "Product"],
            "relationship_types": ["PURCHASED"],
        })
        mock_rag.execute_cypher = AsyncMock(return_value=[
            {"n": {"name": "Alice", "label": "Customer"}}
        ])
        mock_etl.create_node = AsyncMock(return_value={
            "id": "node_1", "label": "Customer", "properties": {}
        })
        mock_dash.verify_connection = AsyncMock(return_value=True)
        yield mock_rag, mock_etl, mock_dash


# ── Fixtures: Settings Override ──────────────────────────────────

@pytest.fixture
def test_settings():
    """Return settings for test assertions."""
    from app.core.config import settings
    return settings


# ── Fixtures: Test Data ──────────────────────────────────────────

@pytest.fixture
def sample_data_source_dict():
    return {
        "name": "Test CSV Data",
        "source_type": "csv",
        "config": {"path": "/tmp/test.csv"},
    }


@pytest.fixture
def sample_pipeline_dict():
    return {
        "data_source_id": 1,
        "name": "Test Pipeline",
    }


@pytest.fixture
def sample_query_dict():
    return {
        "query": "Show me all customers",
        "traversal_depth": 2,
    }


@pytest.fixture
def sample_entity_list():
    return [
        {"type": "Customer", "name": "Alice", "properties": {"email": "alice@test.com"}},
        {"type": "Product", "name": "Laptop", "properties": {"price": 999.99}},
        {"type": "Order", "name": "ORD-001", "properties": {"amount": 999.99}},
    ]
