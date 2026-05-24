"""Unit tests for GraphService - covers Neo4j, SQLite, and JSON fallback paths."""

import json
import os
import pytest
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

pytestmark = pytest.mark.asyncio


class TestGraphServiceInit:
    """Test GraphService initialization and helper methods."""

    async def test_singleton_exists(self):
        """GraphService singleton should be importable."""
        from app.services.graph_service import graph_service
        assert graph_service is not None
        assert hasattr(graph_service, "get_graph")
        assert hasattr(graph_service, "execute_cypher")
        assert hasattr(graph_service, "create_node")
        assert hasattr(graph_service, "get_graph_stats")


class TestGraphServiceConnection:
    """Test Neo4j connection handling with various scenarios."""

    async def test_verify_connection_no_driver(self, mock_neo4j_session):
        """verify_connection should attempt to connect when no driver exists."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._driver = None
        svc._neo4j_available = False

        # Create a driver class that properly supports async with
        class MockDriver:
            """A mock Neo4j driver that properly supports async with protocol."""

            def __init__(self, session):
                self._session = session

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def session(self):
                return self

            async def close(self):
                pass

        # Create proper session.run result
        class MockResult:
            def __init__(self):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                raise StopAsyncIteration

            async def single(self):
                return {"test": 1}

        # Make session.run return a MockResult
        mock_session = mock_neo4j_session
        mock_session.run = AsyncMock(return_value=MockResult())

        # Fix: MockDriver.session() must return the mock session, not self
        class FixedMockDriver(MockDriver):
            def session(self):
                return self._session

        mock_driver = FixedMockDriver(mock_session)

        with patch.object(svc, "_get_driver", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_driver
            result = await svc.verify_connection()
            assert result is True

    async def test_verify_connection_driver_exists(self):
        """verify_connection should return cached status when driver exists."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._driver = MagicMock()
        svc._neo4j_available = True

        result = await svc.verify_connection()
        assert result is True

    async def test_verify_connection_failure(self):
        """verify_connection should return False when Neo4j unavailable."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._driver = None
        svc._neo4j_available = False

        with patch.object(svc, "_get_driver", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await svc.verify_connection()
            assert result is False


class TestGraphServiceGetDriver:
    """Test the _get_driver lazy initialization."""

    async def test_get_driver_success(self):
        """_get_driver should return driver on successful connection."""
        class MockDriver:
            """A mock Neo4j driver that properly supports async with protocol."""

            def __init__(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def session(self):
                return self

            async def run(self, query, **kwargs):
                class MockResult:
                    async def single(self):
                        return {"test": 1}
                return MockResult()

            async def close(self):
                pass

        mock_driver = MockDriver()

        with patch("app.services.graph_service.AsyncGraphDatabase.driver") as mock_driver_class:
            mock_driver_class.return_value = mock_driver

            from app.services.graph_service import GraphService
            svc = GraphService()
            svc._driver = None
            svc._neo4j_available = False

            driver = await svc._get_driver()
            assert driver is not None
            assert svc._neo4j_available is True

    async def test_get_driver_failure(self):
        """_get_driver should set _neo4j_available to False on failure."""
        with patch("app.services.graph_service.AsyncGraphDatabase.driver") as mock_driver_class:
            mock_driver_class.side_effect = Exception("Connection refused")

            from app.services.graph_service import GraphService
            svc = GraphService()
            svc._driver = None
            svc._neo4j_available = False

            driver = await svc._get_driver()
            assert driver is None
            assert svc._neo4j_available is False


class TestGraphServiceGetGraph:
    """Test get_graph with Neo4j and fallback paths."""

    async def test_get_graph_neo4j_available(self):
        """get_graph should try Neo4j first when available."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        with patch.object(svc, "_get_graph_neo4j", new_callable=AsyncMock) as mock_neo4j:
            mock_neo4j.return_value = {"nodes": [{"id": "1"}], "edges": []}
            result = await svc.get_graph(limit=10)
            assert result["nodes"][0]["id"] == "1"
            mock_neo4j.assert_called_once_with(10)

    async def test_get_graph_neo4j_fallback_to_local(self):
        """get_graph should fallback to local when Neo4j fails."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        with patch.object(svc, "_get_graph_neo4j", new_callable=AsyncMock) as mock_neo4j, \
             patch.object(svc, "_get_graph_local") as mock_local:
            mock_neo4j.side_effect = Exception("Neo4j down")
            mock_local.return_value = {"nodes": [], "edges": []}

            result = await svc.get_graph(limit=10)
            assert svc._neo4j_available is False
            mock_local.assert_called_once_with(10)

    async def test_get_graph_neo4j_direct(self):
        """_get_graph_neo4j should handle empty results."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True

        # Create a proper async iterable result class (not using AsyncMock __aiter__)
        class AsyncResult:
            """Async iterable result that mimics Neo4j result with records."""
            def __init__(self):
                self.records = []
                self.index = 0
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self.index >= len(self.records):
                    raise StopAsyncIteration
                item = self.records[self.index]
                self.index += 1
                return item

        class MockDriver:
            """Mock driver that returns AsyncResult from session.run()."""
            def __init__(self):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def session(self):
                return self
            async def run(self, query, **kwargs):
                return AsyncResult()
            async def close(self):
                pass

        svc._driver = MockDriver()

        result = await svc._get_graph_neo4j(limit=100)
        assert "nodes" in result
        assert "edges" in result
        assert result["nodes"] == []
        assert result["edges"] == []

    async def test_get_graph_local_empty(self):
        """_get_graph_local should return empty graph when no data."""
        from app.services.graph_service import GraphService
        svc = GraphService()

        # Patch SessionLocal at the graph_service module level
        with patch("app.services.graph_service.SessionLocal") as mock_sl:
            session = MagicMock()
            query_mock = MagicMock()
            query_mock.limit.return_value = query_mock
            query_mock.all.return_value = []
            session.query.return_value = query_mock
            mock_sl.return_value = session

            result = await svc._get_graph_local(limit=100)
            assert result == {"nodes": [], "edges": []}


class TestGraphServiceLocalStorage:
    """Test JSON file-based local storage fallback."""

    async def test_load_local_store_not_exists(self):
        """_load_local_store should return empty structure when file missing."""
        from app.services.graph_service import GraphService
        svc = GraphService()

        with patch("os.path.exists", return_value=False):
            result = svc._load_local_store()
            assert result == {"nodes": [], "edges": []}

    async def test_load_local_store_exists(self):
        """_load_local_store should load data from file."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        test_data = {"nodes": [{"id": "1"}], "edges": []}

        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            result = svc._load_local_store()
            assert result == test_data

    async def test_save_local_store(self):
        """_save_local_store should write data to file."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        test_data = {"nodes": [{"id": "1"}], "edges": []}

        with patch("builtins.open", mock_open()) as m, \
             patch("os.makedirs") as mock_makedirs:
            svc._save_local_store(test_data)
            mock_makedirs.assert_called_once()
            handle = m()
            written = "".join(call[0][0] for call in handle.write.call_args_list)
            assert "nodes" in written

    async def test_save_local_store_error(self):
        """_save_local_store should handle write errors gracefully."""
        from app.services.graph_service import GraphService
        svc = GraphService()

        with patch("builtins.open", mock_open()) as m:
            m.side_effect = PermissionError("Access denied")
            # Should not raise
            svc._save_local_store({"nodes": []})


class TestGraphServiceExecuteCypher:
    """Test Cypher query execution."""

    async def test_execute_cypher_not_available(self):
        """execute_cypher should return empty list when Neo4j unavailable."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = False

        result = await svc.execute_cypher("MATCH (n) RETURN n")
        assert result == []

    async def test_execute_cypher_available_empty(self):
        """execute_cypher should return empty list when no results."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True

        # Create a proper async iterable result class
        class AsyncResult:
            """Async iterable result that mimics Neo4j empty result."""
            def __aiter__(self):
                return self
            async def __anext__(self):
                raise StopAsyncIteration

        class MockDriver:
            """Mock driver that returns AsyncResult from session.run()."""
            def __init__(self):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            def session(self):
                return self
            async def run(self, query, **kwargs):
                return AsyncResult()
            async def close(self):
                pass

        svc._driver = MockDriver()

        result_list = await svc.execute_cypher("MATCH (n) RETURN n")
        assert isinstance(result_list, list)

    async def test_execute_cypher_driver_none(self):
        """execute_cypher should return empty list if driver is None."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = None

        with patch.object(svc, "_get_driver", new_callable=AsyncMock, return_value=None):
            result = await svc.execute_cypher("MATCH (n) RETURN n")
            assert result == []

    async def test_execute_cypher_error(self):
        """execute_cypher should raise on Neo4j errors."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()
        svc._driver.session.return_value.__aenter__.return_value.run.side_effect = Exception("Query error")

        with pytest.raises(Exception, match="Query error"):
            await svc.execute_cypher("MATCH (n) RETURN n")


class TestGraphServiceCreateNode:
    """Test node creation with Neo4j and fallback paths."""

    async def test_create_node_neo4j(self):
        """create_node should try Neo4j first."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        with patch.object(svc, "_create_node_neo4j", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {"id": "new_node", "label": "Customer", "properties": {}}
            result = await svc.create_node("Customer", {"name": "Test"})
            assert result["id"] == "new_node"

    async def test_create_node_neo4j_fallback(self):
        """create_node should fallback to local when Neo4j fails."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        with patch.object(svc, "_create_node_neo4j", new_callable=AsyncMock) as mock_neo4j, \
             patch.object(svc, "_create_node_local", new_callable=AsyncMock) as mock_local:
            mock_neo4j.side_effect = Exception("Neo4j down")
            mock_local.return_value = {"id": "local_0", "label": "Customer"}

            result = await svc.create_node("Customer", {"name": "Test"})
            assert svc._neo4j_available is False
            mock_local.assert_called_once_with("Customer", {"name": "Test"})

    async def test_create_node_neo4j_direct(self):
        """_create_node_neo4j should create node via Cypher."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        session = AsyncMock()
        result = AsyncMock()
        result.single.return_value = None  # No record returned
        session.run = AsyncMock(return_value=result)
        svc._driver.session.return_value.__aenter__.return_value = session

        result = await svc._create_node_neo4j("Customer", {"name": "Test"})
        assert isinstance(result, dict)
        assert result == {}  # Returns {} when no record


class TestGraphServiceGetGraphStats:
    """Test graph statistics with Neo4j and fallback paths."""

    async def test_get_graph_stats_neo4j(self):
        """get_graph_stats should query Neo4j when available."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        # First call: node count query
        node_result = AsyncMock()
        node_result.single.return_value = {"count": 10, "labels": [["Customer", "Product"]]}

        # Second call: edge count query
        edge_result = AsyncMock()
        edge_result.single.return_value = {"count": 5, "types": ["PURCHASED"]}

        session = AsyncMock()
        session.run = AsyncMock(side_effect=[node_result, edge_result])
        svc._driver.session.return_value.__aenter__.return_value = session

        stats = await svc.get_graph_stats()
        assert stats["node_count"] == 10
        assert stats["edge_count"] == 5

    async def test_get_graph_stats_fallback(self):
        """get_graph_stats should fallback to SQLite/JSON when Neo4j fails."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = False

        # Patch SessionLocal at the graph_service module level
        with patch("app.services.graph_service.SessionLocal") as mock_sl:
            session = MagicMock()
            query_mock = MagicMock()
            query_mock.count.return_value = 0
            q2 = MagicMock()
            q2.all.return_value = []
            query_mock.distinct.return_value = q2
            session.query.return_value = query_mock
            mock_sl.return_value = session

            stats = await svc.get_graph_stats()
            assert stats["node_count"] == 0
            assert stats["edge_count"] == 0
            assert stats["node_labels"] == []
            assert stats["relationship_types"] == []

    async def test_get_graph_stats_neo4j_to_sqlite_fallback(self):
        """get_graph_stats should fallback from Neo4j to SQLite on failure."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._neo4j_available = True
        svc._driver = MagicMock()

        with patch.object(svc, "_get_driver", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection lost")

            stats = await svc.get_graph_stats()
            assert svc._neo4j_available is False
            assert isinstance(stats, dict)


class TestGraphServiceClose:
    """Test cleanup methods."""

    async def test_close_with_driver(self):
        """close should close the Neo4j driver if it exists."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        mock_driver = AsyncMock()
        svc._driver = mock_driver

        await svc.close()
        mock_driver.close.assert_awaited_once()
        assert svc._driver is None

    async def test_close_no_driver(self):
        """close should handle case when no driver exists."""
        from app.services.graph_service import GraphService
        svc = GraphService()
        svc._driver = None

        await svc.close()  # Should not raise
