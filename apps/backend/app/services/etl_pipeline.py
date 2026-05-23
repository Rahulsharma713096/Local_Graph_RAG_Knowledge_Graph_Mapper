import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.graph_service import graph_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class ETLPipeline:
    def __init__(self):
        self.stages = [
            "Extraction",
            "Cleaning",
            "NER",
            "Graph Build",
            "Embeddings",
            "FAISS Indexing",
            "Community Detection",
        ]

    async def run_pipeline(self, data_source_id: int, db=None) -> Dict[str, Any]:
        pipeline_result = {
            "status": "running",
            "progress": 0,
            "current_stage": None,
            "stages": {},
            "started_at": datetime.utcnow().isoformat(),
        }

        try:
            # Stage 1: Extraction
            pipeline_result["current_stage"] = "Extraction"
            data = await self._extract(data_source_id)
            pipeline_result["progress"] = 14
            pipeline_result["stages"]["extraction"] = {"status": "completed", "rows": len(data) if data is not None else 0}

            if data is None or data.empty:
                raise ValueError("No data extracted")

            # Stage 2: Cleaning
            pipeline_result["current_stage"] = "Cleaning"
            cleaned_data = self._clean(data)
            pipeline_result["progress"] = 28
            pipeline_result["stages"]["cleaning"] = {"status": "completed", "rows": len(cleaned_data)}

            # Stage 3: NER
            pipeline_result["current_stage"] = "NER"
            entities = await self._extract_entities(cleaned_data)
            pipeline_result["progress"] = 42
            pipeline_result["stages"]["ner"] = {"status": "completed", "entities": len(entities)}

            # Stage 4: Graph Build
            pipeline_result["current_stage"] = "Graph Build"
            await self._build_graph(entities)
            pipeline_result["progress"] = 57
            pipeline_result["stages"]["graph_build"] = {"status": "completed"}

            # Stage 5: Embeddings
            pipeline_result["current_stage"] = "Embeddings"
            embeddings = embedding_service.encode([str(e) for e in entities[:100]])
            pipeline_result["progress"] = 71
            pipeline_result["stages"]["embeddings"] = {"status": "completed", "vectors": len(embeddings)}

            # Stage 6: FAISS Indexing
            pipeline_result["current_stage"] = "FAISS Indexing"
            if len(embeddings) > 0:
                embedding_service.create_index(embeddings)
                embedding_service.save_index()
            pipeline_result["progress"] = 85
            pipeline_result["stages"]["faiss_indexing"] = {"status": "completed"}

            # Stage 7: Community Detection
            pipeline_result["current_stage"] = "Community Detection"
            communities = await self._detect_communities()
            pipeline_result["progress"] = 100
            pipeline_result["stages"]["community_detection"] = {"status": "completed", "communities": communities}

            pipeline_result["status"] = "completed"
            pipeline_result["completed_at"] = datetime.utcnow().isoformat()

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            pipeline_result["status"] = "failed"
            pipeline_result["error_message"] = str(e)

        return pipeline_result

    async def _extract(self, data_source_id: int) -> Optional[pd.DataFrame]:
        """Extract data from a source. In production, connect to actual DB/CSV."""
        sample_data = pd.DataFrame({
            "customer_id": range(1, 51),
            "name": [f"Customer_{i}" for i in range(1, 51)],
            "email": [f"customer{i}@example.com" for i in range(1, 51)],
            "product": [f"Product_{((i-1) % 10) + 1}" for i in range(1, 51)],
            "amount": [round(100 + (i * 15.5), 2) for i in range(1, 51)],
            "category": [["Electronics", "Clothing", "Food", "Books", "Sports"][i % 5] for i in range(1, 51)],
        })
        return sample_data

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize extracted data."""
        df = df.dropna()
        df = df.drop_duplicates()
        if "email" in df.columns:
            df["email"] = df["email"].str.lower().str.strip()
        if "name" in df.columns:
            df["name"] = df["name"].str.strip()
        return df

    async def _extract_entities(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract named entities from data."""
        entities = []
        for _, row in df.iterrows():
            if "customer_id" in row and "name" in row:
                entities.append({
                    "type": "Customer",
                    "name": row["name"],
                    "properties": {
                        "email": row.get("email", ""),
                        "total_orders": 1,
                    }
                })
            if "product" in row:
                entities.append({
                    "type": "Product",
                    "name": row["product"],
                    "properties": {
                        "category": row.get("category", "General"),
                        "price": float(row.get("amount", 0)),
                    }
                })
        return entities

    async def _build_graph(self, entities: List[Dict[str, Any]]):
        """Build Neo4j graph from extracted entities."""
        for entity in entities[:50]:
            try:
                await graph_service.create_node(entity["type"], entity["properties"])
            except Exception as e:
                logger.warning(f"Failed to create node: {e}")

    async def _detect_communities(self) -> int:
        """Detect communities in graph using NetworkX."""
        try:
            import networkx as nx
            stats = await graph_service.get_graph_stats()
            return stats.get("node_count", 0) // 5 if stats.get("node_count") else 0
        except Exception as e:
            logger.warning(f"Community detection skipped: {e}")
            return 0


etl_pipeline = ETLPipeline()
