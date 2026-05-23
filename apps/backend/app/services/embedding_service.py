import os
import numpy as np
import logging
from typing import List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self._model = None
        self._index = None
        self._model_name = settings.EMBEDDING_MODEL
        self._model_available = True
        self._faiss_available = True

    def _load_model(self):
        if self._model is None and self._model_available:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name)
                logger.info(f"Loaded embedding model: {self._model_name}")
            except ImportError:
                logger.warning("sentence-transformers not installed. Embedding features disabled.")
                self._model_available = False
            except Exception as e:
                logger.warning(f"Failed to load embedding model '{self._model_name}': {e}")
                self._model_available = False

    def _load_faiss_index(self):
        if self._index is None and self._faiss_available:
            try:
                import faiss
                index_path = settings.FAISS_INDEX_PATH
                if os.path.exists(f"{index_path}.faiss"):
                    self._index = faiss.read_index(f"{index_path}.faiss")
                    logger.info("Loaded FAISS index from disk")
                else:
                    self._index = None
            except ImportError:
                logger.warning("faiss not installed. Vector search features disabled.")
                self._faiss_available = False
            except Exception as e:
                logger.warning(f"Failed to load FAISS index: {e}")
                self._faiss_available = False

    def encode(self, texts: List[str]) -> np.ndarray:
        self._load_model()
        if self._model is None:
            logger.warning("Embedding model not available, returning empty array")
            return np.array([])
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            return np.array([])

    def create_index(self, embeddings: np.ndarray):
        if embeddings.size == 0:
            return False
        try:
            import faiss
            dimension = embeddings.shape[1]
            self._index = faiss.IndexFlatL2(dimension)
            self._index.add(embeddings.astype(np.float32))
            return True
        except ImportError:
            logger.warning("faiss not installed. Cannot create index.")
            return False
        except Exception as e:
            logger.error(f"FAISS index creation failed: {e}")
            return False

    def save_index(self):
        if self._index is not None:
            try:
                import faiss
                import os
                os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH) or ".", exist_ok=True)
                faiss.write_index(self._index, f"{settings.FAISS_INDEX_PATH}.faiss")
                logger.info("Saved FAISS index to disk")
            except Exception as e:
                logger.error(f"Failed to save FAISS index: {e}")

    def search(self, query: str, k: int = 5) -> List[dict]:
        self._load_faiss_index()
        if self._index is None:
            return []

        query_embedding = self.encode([query])
        if query_embedding.size == 0:
            return []

        try:
            distances, indices = self._index.search(query_embedding.astype(np.float32), k)
            results = []
            for i, idx in enumerate(indices[0]):
                if idx >= 0:
                    results.append({"index": int(idx), "score": float(distances[0][i])})
            return results
        except Exception as e:
            logger.error(f"FAISS search failed: {e}")
            return []


embedding_service = EmbeddingService()
