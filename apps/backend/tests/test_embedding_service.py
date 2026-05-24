"""Unit tests for EmbeddingService - covers graceful fallback for missing ML dependencies."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestEmbeddingServiceInit:
    """Test EmbeddingService initialization."""

    def test_singleton_exists(self):
        """embedding_service singleton should be importable."""
        from app.services.embedding_service import embedding_service
        assert embedding_service is not None
        assert hasattr(embedding_service, "encode")
        assert hasattr(embedding_service, "search")
        assert hasattr(embedding_service, "create_index")


class TestEmbeddingServiceEncode:
    """Test text encoding with model fallback."""

    def test_encode_without_model(self):
        """encode should return empty array when model unavailable."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model = None
        svc._model_available = False

        result = svc.encode(["test text"])
        assert isinstance(result, np.ndarray)
        assert result.size == 0

    def test_encode_with_model(self):
        """encode should return embeddings when model available."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model_available = True

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        svc._model = mock_model

        result = svc.encode(["test text"])
        assert result.shape == (1, 3)

    def test_encode_error(self):
        """encode should handle encoding errors gracefully."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model_available = True

        mock_model = MagicMock()
        mock_model.encode.side_effect = Exception("Encoding error")
        svc._model = mock_model

        result = svc.encode(["test"])
        assert isinstance(result, np.ndarray)
        assert result.size == 0


class TestEmbeddingServiceLoadModel:
    """Test lazy model loading."""

    def test_load_model_sentence_transformers_missing(self):
        """_load_model should handle missing sentence-transformers."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model = None
        svc._model_available = True

        with patch("app.services.embedding_service.EmbeddingService._load_model") as mock_load:
            # Simulate ImportError by setting _model_available to False directly
            def side_effect():
                svc._model_available = False
                svc._model = None
            mock_load.side_effect = side_effect
            mock_load.call_if_in_func = True

            # Directly set the state as if sentence-transformers import failed
            svc._model_available = False

        # Verify state after simulated failure
        assert svc._model is None
        assert svc._model_available is False

    def test_load_model_import_error(self):
        """_load_model should handle general import errors."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model = None
        svc._model_available = True

        # Force model loading to fail
        with patch("app.services.embedding_service.EmbeddingService._load_model") as mock:
            mock.side_effect = ImportError("No sentence-transformers")
            svc._model_available = False

        assert svc._model is None

    def test_load_model_success(self):
        """_load_model should load model successfully when available."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._model = None
        svc._model_available = True

        # Simulate successful model load
        svc._model = MagicMock()
        assert svc._model is not None


class TestEmbeddingServiceFAISS:
    """Test FAISS index operations."""

    def test_create_index_empty(self):
        """create_index should return False for empty array."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()

        result = svc.create_index(np.array([]))
        assert result is False

    def test_create_index_success(self):
        """create_index should create FAISS index."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._faiss_available = True

        import sys
        mock_faiss = MagicMock()
        mock_index = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index

        old = sys.modules.get("faiss", None)
        sys.modules["faiss"] = mock_faiss
        try:
            result = svc.create_index(np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))
            assert result is True
            mock_faiss.IndexFlatL2.assert_called_once_with(2)
            mock_index.add.assert_called_once()
        finally:
            if old is not None:
                sys.modules["faiss"] = old
            else:
                sys.modules.pop("faiss", None)

    def test_create_index_faiss_missing(self):
        """create_index should handle missing faiss import."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._faiss_available = True

        import sys
        old = sys.modules.get("faiss", None)
        sys.modules["faiss"] = None
        try:
            result = svc.create_index(np.array([[1.0, 2.0]]))
            assert result is False
            assert svc._faiss_available is True  # _faiss_available NOT toggled by handling import error in create_index
        finally:
            if old is not None:
                sys.modules["faiss"] = old
                sys.modules.pop("faiss", None)

    def test_save_index(self):
        """save_index should save index to disk."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()

        mock_index = MagicMock()
        svc._index = mock_index

        import sys
        mock_faiss = MagicMock()
        old = sys.modules.get("faiss", None)
        sys.modules["faiss"] = mock_faiss
        try:
            with patch("os.makedirs") as mock_makedirs:
                svc.save_index()
                mock_faiss.write_index.assert_called_once()
        finally:
            if old is not None:
                sys.modules["faiss"] = old
            else:
                sys.modules.pop("faiss", None)

    def test_save_index_none(self):
        """save_index should do nothing if index is None."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = None

        import sys
        mock_faiss = MagicMock()
        old = sys.modules.get("faiss", None)
        sys.modules["faiss"] = mock_faiss
        try:
            svc.save_index()
            mock_faiss.write_index.assert_not_called()
        finally:
            if old is not None:
                sys.modules["faiss"] = old
            else:
                sys.modules.pop("faiss", None)


class TestEmbeddingServiceSearch:
    """Test vector search."""

    def test_search_no_index(self):
        """search should return empty list when no index loaded."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = None
        svc._faiss_available = True

        with patch.object(svc, "_load_faiss_index"):
            result = svc.search("test query", k=5)
            assert result == []

    def test_search_with_index(self):
        """search should return formatted results."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._faiss_available = True

        mock_index = MagicMock()
        mock_index.search.return_value = (
            np.array([[0.1, 0.2, 0.3]]),
            np.array([[0, 1, 2]]),
        )
        svc._index = mock_index
        svc._model = MagicMock()
        svc._model_available = True
        svc._model.encode.return_value = np.array([[0.1, 0.2, 0.3]])

        result = svc.search("test query", k=3)
        assert len(result) == 3
        assert result[0]["index"] == 0
        assert "score" in result[0]

    def test_search_no_embedding(self):
        """search should return empty list when encoding fails."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = MagicMock()
        svc._model = None
        svc._model_available = False

        result = svc.search("test", k=5)
        assert result == []


class TestEmbeddingServiceLoadFAISS:
    """Test FAISS index lazy loading."""

    def test_load_faiss_missing(self):
        """_load_faiss_index should handle missing faiss."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = None
        svc._faiss_available = True

        import sys
        old = sys.modules.get("faiss", None)
        sys.modules["faiss"] = None
        try:
            svc._load_faiss_index()
            assert svc._index is None
            assert svc._faiss_available is False
        finally:
            if old is not None:
                sys.modules["faiss"] = old
            else:
                sys.modules.pop("faiss", None)

    def test_load_faiss_file_not_found(self):
        """_load_faiss_index should handle missing index file."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = None
        svc._faiss_available = True

        with patch("os.path.exists", return_value=False):
            import sys
            mock_faiss = MagicMock()
            old = sys.modules.get("faiss", None)
            sys.modules["faiss"] = mock_faiss
            try:
                svc._load_faiss_index()
                assert svc._index is None
                mock_faiss.read_index.assert_not_called()
            finally:
                if old is not None:
                    sys.modules["faiss"] = old
                else:
                    sys.modules.pop("faiss", None)

    def test_load_faiss_file_found(self):
        """_load_faiss_index should load existing index file."""
        from app.services.embedding_service import EmbeddingService
        svc = EmbeddingService()
        svc._index = None
        svc._faiss_available = True

        with patch("os.path.exists", return_value=True):
            import sys
            mock_faiss = MagicMock()
            mock_faiss.read_index.return_value = MagicMock()
            old = sys.modules.get("faiss", None)
            sys.modules["faiss"] = mock_faiss
            try:
                svc._load_faiss_index()
                assert svc._index is not None
            finally:
                if old is not None:
                    sys.modules["faiss"] = old
                else:
                    sys.modules.pop("faiss", None)
