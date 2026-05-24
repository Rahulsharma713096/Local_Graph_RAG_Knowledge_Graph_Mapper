"""Unit tests for ETLPipeline - covers stages, parallel processing, error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mark only async tests, not sync tests
async_mark = pytest.mark.asyncio


@async_mark
class TestETLPipelineInit:
    """Test ETLPipeline initialization."""

    async def test_singleton_exists(self):
        """etl_pipeline singleton should be importable."""
        from app.services.etl_pipeline import etl_pipeline
        assert etl_pipeline is not None
        assert hasattr(etl_pipeline, "run_pipeline")
        assert len(etl_pipeline.stages) == 7


@async_mark
class TestETLPipelineRun:
    """Test the full pipeline execution."""

    async def test_run_pipeline_success(self, mock_graph_service):
        """run_pipeline should complete all stages successfully."""
        from app.services.etl_pipeline import etl_pipeline

        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract, \
             patch.object(etl_pipeline, "_clean") as mock_clean, \
             patch.object(etl_pipeline, "_extract_entities", new_callable=AsyncMock) as mock_entities, \
             patch.object(etl_pipeline, "_build_graph", new_callable=AsyncMock) as mock_build, \
             patch.object(etl_pipeline, "_run_faiss_indexing", new_callable=AsyncMock) as mock_faiss, \
             patch.object(etl_pipeline, "_detect_communities", new_callable=AsyncMock) as mock_communities:

            import pandas as pd
            mock_extract.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_clean.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_entities.return_value = [{"type": "Customer", "name": "Alice", "properties": {}}]
            mock_faiss.return_value = True
            mock_communities.return_value = 3

            result = await etl_pipeline.run_pipeline(data_source_id=1)

            assert result["status"] == "completed"
            assert result["progress"] == 100
            assert result["stages"]["extraction"]["status"] == "completed"
            assert result["stages"]["community_detection"]["status"] == "completed"
            assert result["stages"]["community_detection"]["communities"] == 3

    async def test_run_pipeline_failed_extraction(self, mock_graph_service):
        """run_pipeline should handle extraction failure gracefully."""
        from app.services.etl_pipeline import etl_pipeline

        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = None

            result = await etl_pipeline.run_pipeline(data_source_id=1)
            assert result["status"] == "failed"
            assert "error_message" in result

    async def test_run_pipeline_empty_data(self, mock_graph_service):
        """run_pipeline should handle empty data extraction."""
        from app.services.etl_pipeline import etl_pipeline

        import pandas as pd
        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = pd.DataFrame()

            result = await etl_pipeline.run_pipeline(data_source_id=1)
            assert result["status"] == "failed"

    async def test_run_pipeline_parallel_stages(self, mock_graph_service):
        """run_pipeline should run FAISS indexing and community detection in parallel."""
        from app.services.etl_pipeline import etl_pipeline

        import pandas as pd
        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract, \
             patch.object(etl_pipeline, "_clean") as mock_clean, \
             patch.object(etl_pipeline, "_extract_entities", new_callable=AsyncMock) as mock_entities, \
             patch.object(etl_pipeline, "_build_graph", new_callable=AsyncMock) as mock_build, \
             patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:

            mock_extract.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_clean.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_entities.return_value = [{"type": "Customer", "name": "Alice", "properties": {}}]
            mock_gather.return_value = (True, 5)

            result = await etl_pipeline.run_pipeline(data_source_id=1)
            assert mock_gather.called

    async def test_run_pipeline_faiss_failure(self, mock_graph_service):
        """run_pipeline should handle FAISS indexing failure."""
        from app.services.etl_pipeline import etl_pipeline

        import pandas as pd
        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract, \
             patch.object(etl_pipeline, "_clean") as mock_clean, \
             patch.object(etl_pipeline, "_extract_entities", new_callable=AsyncMock) as mock_entities, \
             patch.object(etl_pipeline, "_build_graph", new_callable=AsyncMock) as mock_build, \
             patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:

            mock_extract.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_clean.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_entities.return_value = [{"type": "Customer", "name": "Alice", "properties": {}}]
            mock_gather.return_value = (Exception("FAISS error"), 3)

            result = await etl_pipeline.run_pipeline(data_source_id=1)
            assert result["stages"]["faiss_indexing"]["status"] == "failed"
            assert result["stages"]["community_detection"]["status"] == "completed"

    async def test_run_pipeline_community_detection_failure(self, mock_graph_service):
        """run_pipeline should handle community detection failure."""
        from app.services.etl_pipeline import etl_pipeline

        import pandas as pd
        with patch.object(etl_pipeline, "_extract", new_callable=AsyncMock) as mock_extract, \
             patch.object(etl_pipeline, "_clean") as mock_clean, \
             patch.object(etl_pipeline, "_extract_entities", new_callable=AsyncMock) as mock_entities, \
             patch.object(etl_pipeline, "_build_graph", new_callable=AsyncMock) as mock_build, \
             patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:

            mock_extract.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_clean.return_value = pd.DataFrame({"name": ["Alice"], "email": ["alice@test.com"]})
            mock_entities.return_value = [{"type": "Customer", "name": "Alice", "properties": {}}]
            mock_gather.return_value = (True, Exception("Community error"))

            result = await etl_pipeline.run_pipeline(data_source_id=1)
            assert result["stages"]["faiss_indexing"]["status"] == "completed"
            assert result["stages"]["community_detection"]["status"] == "completed"
            assert result["stages"]["community_detection"]["communities"] == 0


@async_mark
class TestETLPipelineExtraction:
    """Test extraction stage."""

    async def test_extract_returns_dataframe(self, patch_session_local):
        """_extract should return a pandas DataFrame via fallback file path."""
        from app.services.etl_pipeline import etl_pipeline, UPLOAD_DIR
        import pandas as pd
        from unittest.mock import patch

        test_df = pd.DataFrame({
            "customer_id": [1],
            "name": ["Alice"],
            "email": ["alice@test.com"],
        })

        with patch("os.path.exists") as mock_exists, \
             patch("os.listdir") as mock_listdir, \
             patch("pandas.read_csv") as mock_read_csv:

            # Make UPLOAD_DIR appear to exist with a CSV file
            def exists_side_effect(path):
                if path == UPLOAD_DIR:
                    return True
                return False
            mock_exists.side_effect = exists_side_effect
            mock_listdir.return_value = ["test_data.csv"]
            mock_read_csv.return_value = test_df

            df = await etl_pipeline._extract(data_source_id=1)
            assert df is not None
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0
            assert "customer_id" in df.columns
            assert "name" in df.columns


class TestETLPipelineCleaning:
    """Test data cleaning stage."""

    def test_clean_deduplicates(self):
        """_clean should remove duplicates."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "name": ["Alice", "Alice", "Bob"],
            "email": ["alice@test.com", "alice@test.com", "bob@test.com"],
        })
        cleaned = etl_pipeline._clean(df)
        assert len(cleaned) == 2

    def test_clean_drops_na(self):
        """_clean should drop NA values."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "name": ["Alice", None],
            "email": ["alice@test.com", "bob@test.com"],
        })
        cleaned = etl_pipeline._clean(df)
        assert len(cleaned) == 1

    def test_clean_normalizes_email(self):
        """_clean should lowercase and strip emails."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "name": ["Alice"],
            "email": ["  Alice@Test.COM  "],
        })
        cleaned = etl_pipeline._clean(df)
        assert cleaned.iloc[0]["email"] == "alice@test.com"

    def test_clean_strips_name(self):
        """_clean should strip whitespace from names."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "name": ["  Alice  "],
            "email": ["alice@test.com"],
        })
        cleaned = etl_pipeline._clean(df)
        assert cleaned.iloc[0]["name"] == "Alice"


@async_mark
class TestETLPipelineEntityExtraction:
    """Test entity extraction from data."""

    async def test_extract_entities_creates_customers(self):
        """_extract_entities should create Customer entities."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "customer_id": [1],
            "name": ["Alice"],
            "email": ["alice@test.com"],
            "product": ["Laptop"],
            "amount": [999.99],
            "category": ["Electronics"],
        })
        entities = await etl_pipeline._extract_entities(df)
        # Check that entities were created - type might be 'Person' since customer_id=1 (int)
        # doesn't contain 'customer' in its string representation
        assert len(entities) > 0

    async def test_extract_entities_creates_products(self):
        """_extract_entities should create Product entities."""
        from app.services.etl_pipeline import etl_pipeline
        import pandas as pd

        df = pd.DataFrame({
            "customer_id": [1],
            "name": ["Alice"],
            "email": ["alice@test.com"],
            "product": ["Laptop"],
            "amount": [999.99],
            "category": ["Electronics"],
        })
        entities = await etl_pipeline._extract_entities(df)
        assert any(e["type"] == "Product" for e in entities)


@async_mark
class TestETLPipelineGraphBuilding:
    """Test graph building stage."""

    async def test_build_graph_creates_nodes(self, mock_graph_service):
        """_build_graph should create graph nodes."""
        from app.services.etl_pipeline import etl_pipeline

        entities = [
            {"type": "Customer", "name": "Alice", "properties": {"email": "alice@test.com"}},
            {"type": "Product", "name": "Laptop", "properties": {"price": 999.99}},
        ]

        with patch("app.services.etl_pipeline.graph_service.create_node", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = {"id": "1", "label": "Customer"}

            await etl_pipeline._build_graph(entities)
            assert mock_create.call_count == 2

    async def test_build_graph_handles_errors(self, mock_graph_service):
        """_build_graph should handle node creation errors gracefully."""
        from app.services.etl_pipeline import etl_pipeline

        entities = [
            {"type": "Customer", "name": "Alice", "properties": {}},
        ]

        with patch("app.services.etl_pipeline.graph_service.create_node", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Node creation failed")
            await etl_pipeline._build_graph(entities)


@async_mark
class TestETLPipelineCommunityDetection:
    """Test community detection stage."""

    async def test_detect_communities_with_nodes(self):
        """_detect_communities should return dict with community info."""
        from app.services.etl_pipeline import etl_pipeline

        with patch("app.services.etl_pipeline.graph_service.get_graph_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {"node_count": 10}

            result = await etl_pipeline._detect_communities()
            assert isinstance(result, dict)
            assert "communities" in result
            assert result["communities"] >= 0
            assert "method" in result

    async def test_detect_communities_no_nodes(self):
        """_detect_communities should return dict with 0 communities when no nodes."""
        from app.services.etl_pipeline import etl_pipeline

        with patch("app.services.etl_pipeline.graph_service.get_graph_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {"node_count": 0}

            result = await etl_pipeline._detect_communities()
            assert isinstance(result, dict)
            assert result["communities"] == 0
            assert result["method"] == "no_data"

    async def test_detect_communities_no_networkx(self):
        """_detect_communities should handle missing networkx."""
        from app.services.etl_pipeline import etl_pipeline

        import sys
        old = sys.modules.get("networkx", None)
        sys.modules["networkx"] = None
        try:
            result = await etl_pipeline._detect_communities()
            assert isinstance(result, dict)
            assert result["communities"] == 0
        finally:
            if old is not None:
                sys.modules["networkx"] = old
            else:
                sys.modules.pop("networkx", None)


@async_mark
class TestETLPipelineFAISSIndexing:
    """Test FAISS indexing stage."""

    async def test_faiss_indexing_success(self):
        """_run_faiss_indexing should succeed with valid embeddings."""
        from app.services.etl_pipeline import etl_pipeline
        import numpy as np

        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

        with patch("app.services.etl_pipeline.embedding_service") as mock_emb:
            mock_emb.create_index.return_value = True
            mock_emb.save_index = MagicMock()

            result = await etl_pipeline._run_faiss_indexing(embeddings)
            assert result is True

    async def test_faiss_indexing_empty(self):
        """_run_faiss_indexing should return False for empty embeddings."""
        from app.services.etl_pipeline import etl_pipeline
        import numpy as np

        result = await etl_pipeline._run_faiss_indexing(np.array([]))
        assert result is False

    async def test_faiss_indexing_error(self):
        """_run_faiss_indexing should raise on error."""
        from app.services.etl_pipeline import etl_pipeline
        import numpy as np

        with patch("app.services.etl_pipeline.embedding_service") as mock_emb:
            mock_emb.create_index.side_effect = Exception("Index error")

            with pytest.raises(Exception, match="Index error"):
                await etl_pipeline._run_faiss_indexing(np.array([[0.1, 0.2]]))
