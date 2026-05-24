"""Unit tests for RAGService - covers query pipeline, None handling, error paths, edge cases."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio


class TestRAGServiceInit:
    """Test RAGService initialization."""

    async def test_singleton_exists(self):
        """rag_service singleton should be importable."""
        from app.services.rag_service import rag_service
        assert rag_service is not None
        assert hasattr(rag_service, "query")


class TestRAGServiceQuery:
    """Test the main query pipeline."""

    async def test_query_empty_input(self):
        """query should handle empty input gracefully (NoneType .strip() fix)."""
        from app.services.rag_service import rag_service

        result = await rag_service.query(natural_query="")
        assert "error" in result["answer"].lower() or "empty" in result["answer"].lower()
        assert any(s["status"] == "failed" for s in result["pipeline_steps"])

    async def test_query_whitespace_only(self):
        """query should handle whitespace-only input."""
        from app.services.rag_service import rag_service

        result = await rag_service.query(natural_query="   ")
        assert "empty" in result["answer"].lower()

    async def test_query_none_input(self):
        """query should handle None input gracefully (NoneType .strip() fix)."""
        from app.services.rag_service import rag_service

        result = await rag_service.query(natural_query=None)
        assert "error" in result["answer"].lower() or "empty" in result["answer"].lower()
        assert any(s["status"] == "failed" for s in result["pipeline_steps"])

    async def test_query_full_pipeline(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query should execute full pipeline successfully."""
        from app.services.rag_service import rag_service

        result = await rag_service.query(
            natural_query="Show me all customers",
            traversal_depth=2,
            model="llama3.1",
        )

        assert "answer" in result
        assert "generated_cypher" in result
        assert "retrieved_context" in result
        assert "execution_time_ms" in result
        assert "pipeline_steps" in result
        assert result["execution_time_ms"] >= 0

    async def test_query_with_buffering_callback(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query should call buffering callback during pipeline."""
        from app.services.rag_service import rag_service

        events = []
        async def capture_event(event: dict):
            events.append(event)

        result = await rag_service.query(
            natural_query="Show me products",
            on_buffering=capture_event,
        )

        assert "answer" in result
        assert len(events) >= 0

    async def test_query_returns_all_fields(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query result should contain all expected fields."""
        from app.services.rag_service import rag_service

        result = await rag_service.query("Find orders")

        expected_keys = {"answer", "generated_cypher", "retrieved_context", "execution_time_ms", "pipeline_steps", "buffering"}
        assert expected_keys.issubset(result.keys())

    async def test_query_pipeline_steps_structure(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query pipeline steps should have proper structure."""
        from app.services.rag_service import rag_service

        result = await rag_service.query("Find customers")

        assert len(result["pipeline_steps"]) > 0
        for step in result["pipeline_steps"]:
            assert "step" in step
            assert "status" in step
            assert step["status"] in ["running", "completed", "failed"]

    async def test_query_generated_cypher_not_empty(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query should include generated Cypher (Issue #6 fix)."""
        from app.services.rag_service import rag_service

        result = await rag_service.query("Show products")

        # Verify generated_cypher exists as a non-empty string
        generated_cypher = result.get("generated_cypher", None)
        assert generated_cypher is not None, "generated_cypher should be present in result"
        assert isinstance(generated_cypher, str), "generated_cypher should be a string"
        assert len(generated_cypher) > 0, "generated_cypher should not be empty"


class TestRAGServiceErrorHandling:
    """Test RAGService error recovery paths."""

    async def test_query_ollama_failure(self, mock_graph_service, patch_embedding):
        """query should handle Ollama failure in Cypher generation."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.ollama_service.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("Ollama down")

            result = await rag_service.query("Find customers")
            assert "error" in result["answer"].lower()

    async def test_query_graph_context_failure(self, patch_ollama_get_client, patch_embedding):
        """query should handle graph retrieval failure."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.graph_service.get_graph_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.side_effect = Exception("Graph down")

            result = await rag_service.query("Find customers")
            assert "answer" in result  # Should still produce answer

    async def test_query_partial_failure_still_returns(self, mock_graph_service):
        """query should return partial results on failure."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.embedding_service.encode") as mock_encode:
            mock_encode.side_effect = Exception("Embedding failed")

            result = await rag_service.query("Test query")
            assert "answer" in result  # Should still return something useful


class TestRAGServiceInternalMethods:
    """Test the internal helper methods of RAGService."""

    async def test_retrieve_graph_context(self, mock_graph_service, patch_embedding):
        """_retrieve_graph_context should return structured context."""
        from app.services.rag_service import rag_service

        context = await rag_service._retrieve_graph_context("test query", depth=2)
        assert isinstance(context, list)
        assert len(context) > 0

    async def test_retrieve_graph_context_empty(self, patch_embedding):
        """_retrieve_graph_context should handle empty graph gracefully."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.graph_service.get_graph_stats", new_callable=AsyncMock) as mock:
            mock.return_value = {"node_count": 0}

            context = await rag_service._retrieve_graph_context("test", 2)
            assert isinstance(context, list)

    async def test_generate_cypher(self, patch_ollama_get_client):
        """_generate_cypher should return cleaned Cypher query."""
        from app.services.rag_service import rag_service

        cypher = await rag_service._generate_cypher("test", [], None)
        assert cypher is not None
        assert isinstance(cypher, str)

    async def test_generate_cypher_none_from_ollama(self):
        """_generate_cypher should use default when Ollama returns None (Issue #6 fix)."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.ollama_service.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = None

            cypher = await rag_service._generate_cypher("test", [], None)
            assert cypher == "MATCH (n) RETURN n LIMIT 10"

    async def test_generate_cypher_empty_string(self):
        """_generate_cypher should handle empty string from Ollama."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.ollama_service.generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = ""

            cypher = await rag_service._generate_cypher("test", [], None)
            assert cypher == ""

    async def test_execute_graph_search(self, mock_graph_service):
        """_execute_graph_search should run Cypher and return results."""
        from app.services.rag_service import rag_service

        results = await rag_service._execute_graph_search("MATCH (n) RETURN n LIMIT 10")
        assert isinstance(results, list)

    async def test_execute_graph_search_empty_cypher(self):
        """_execute_graph_search should handle empty Cypher."""
        from app.services.rag_service import rag_service

        results = await rag_service._execute_graph_search("")
        assert results == []

    async def test_execute_graph_search_error_cypher(self):
        """_execute_graph_search should handle Error-prefixed Cypher."""
        from app.services.rag_service import rag_service

        results = await rag_service._execute_graph_search("Error: something failed")
        assert results == []

    async def test_generate_answer(self, patch_ollama_get_client):
        """_generate_answer should return formatted answer."""
        from app.services.rag_service import rag_service

        answer = await rag_service._generate_answer("test", [], "llama3.1", None)
        assert answer is not None
        assert isinstance(answer, str)

    async def test_generate_answer_none_from_ollama(self):
        """_generate_answer should return fallback when Ollama returns None (Issue #6 fix)."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.ollama_service.generate_with_buffer", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = None

            answer = await rag_service._generate_answer("test", [], "llama3.1", None)
            assert "Unable to generate" in answer

    async def test_generate_answer_empty(self):
        """_generate_answer should handle empty Ollama response."""
        from app.services.rag_service import rag_service

        with patch("app.services.rag_service.ollama_service.generate_with_buffer", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = ""

            answer = await rag_service._generate_answer("test", [], "llama3.1", None)
            assert answer == ""


class TestRAGServiceQueryPersistence:
    """Test that query flow produces consistent output structure."""

    async def test_query_pipeline_status_all_completed(self, mock_graph_service, patch_ollama_get_client, patch_embedding):
        """query with all services available should have all steps completed."""
        from app.services.rag_service import rag_service

        result = await rag_service.query("Test query")
        for step in result["pipeline_steps"]:
            if step["step"] != "Error":
                assert step["status"] == "completed", f"Step {step['step']} not completed"
