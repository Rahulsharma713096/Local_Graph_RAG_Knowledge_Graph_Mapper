import pandas as pd
import logging
import asyncio
import os
import csv
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.services.graph_service import graph_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)

# Upload directory for uploaded data source files
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
            # Stage 1: Extraction - read from actual data source
            pipeline_result["current_stage"] = "Extraction"
            data = await self._extract(data_source_id, db)
            rows_extracted = len(data) if data is not None else 0
            pipeline_result["progress"] = 14
            pipeline_result["stages"]["extraction"] = {"status": "completed" if data is not None else "failed", "rows": rows_extracted}

            if data is None or data.empty:
                raise ValueError("No data extracted from the data source")

            # Stage 2: Cleaning
            pipeline_result["current_stage"] = "Cleaning"
            cleaned_data = self._clean(data)
            pipeline_result["progress"] = 28
            pipeline_result["stages"]["cleaning"] = {"status": "completed", "rows": len(cleaned_data)}

            # Stage 3: NER (Entity Extraction)
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
            text_entities = [str(e) for e in entities[:100]]
            embeddings = embedding_service.encode(text_entities) if text_entities else []
            pipeline_result["progress"] = 71
            pipeline_result["stages"]["embeddings"] = {"status": "completed", "vectors": len(embeddings) if hasattr(embeddings, '__len__') else 0}

            # Stage 6-7: FAISS Indexing + Community Detection (parallel)
            pipeline_result["current_stage"] = "FAISS Indexing"
            faiss_task = self._run_faiss_indexing(embeddings)
            community_task = self._detect_communities()
            faiss_result, communities = await asyncio.gather(faiss_task, community_task, return_exceptions=True)
            pipeline_result["progress"] = 85
            pipeline_result["stages"]["faiss_indexing"] = {"status": "completed" if not isinstance(faiss_result, Exception) else "failed"}

            # Stage 7: Community Detection
            pipeline_result["current_stage"] = "Community Detection"
            if isinstance(communities, Exception):
                logger.warning(f"Community detection failed: {communities}")
                community_result = {"communities": 0, "method": "error", "modularity": 0.0, "error": str(communities)}
            else:
                community_result = communities if isinstance(communities, dict) else {"communities": int(communities or 0), "method": "heuristic"}
            num_communities = community_result.get("communities", 0)
            pipeline_result["progress"] = 100
            pipeline_result["stages"]["community_detection"] = {
                "status": "completed",
                "communities": num_communities,
                "community_details": community_result.get("details", []),
                "method": community_result.get("method", "unknown"),
                "modularity": community_result.get("modularity", 0.0),
            }

            pipeline_result["status"] = "completed"
            pipeline_result["completed_at"] = datetime.utcnow().isoformat()
            logger.info(f"Pipeline completed successfully - {len(entities)} entities, {num_communities} communities")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            pipeline_result["status"] = "failed"
            pipeline_result["error_message"] = str(e)

        return pipeline_result

    async def _run_faiss_indexing(self, embeddings):
        try:
            if hasattr(embeddings, '__len__') and len(embeddings) > 0:
                embedding_service.create_index(embeddings)
                embedding_service.save_index()
                return True
            return False
        except Exception as e:
            logger.warning(f"FAISS indexing failed: {e}")
            raise

    async def _extract(self, data_source_id: int, db=None) -> Optional[pd.DataFrame]:
        """Extract data from the actual data source (CSV file, etc.) instead of hardcoded data."""
        file_path = None
        source_type = "csv"

        # Look up the data source in the database
        if db is not None:
            from app.models.database_models import DataSource
            ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
            if ds:
                file_path = ds.file_path
                source_type = ds.source_type
                logger.info(f"Loaded data source: {ds.name} (type={source_type}, path={file_path})")

        if file_path and os.path.exists(file_path):
            logger.info(f"Reading data from file: {file_path}")
            try:
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                    logger.info(f"Read {len(df)} rows from CSV: {file_path}")
                    return df
                elif file_path.endswith('.json'):
                    df = pd.read_json(file_path)
                    logger.info(f"Read {len(df)} rows from JSON: {file_path}")
                    return df
                elif file_path.endswith('.tsv'):
                    df = pd.read_csv(file_path, sep='\t')
                    logger.info(f"Read {len(df)} rows from TSV: {file_path}")
                    return df
                elif file_path.endswith('.txt'):
                    # Try to read as delimited text
                    try:
                        df = pd.read_csv(file_path, sep='|')
                    except Exception:
                        df = pd.read_csv(file_path, sep=',')
                    logger.info(f"Read {len(df)} rows from TXT: {file_path}")
                    return df
                else:
                    logger.warning(f"Unsupported file type: {file_path}")
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                raise

        # If no file path or file doesn't exist, look for uploaded files in the upload directory
        upload_dir = UPLOAD_DIR
        if os.path.exists(upload_dir):
            files = [f for f in os.listdir(upload_dir) if f.endswith('.csv')]
            if files:
                file_path = os.path.join(upload_dir, files[0])
                logger.info(f"Reading from upload directory: {file_path}")
                df = pd.read_csv(file_path)
                logger.info(f"Read {len(df)} rows from uploaded CSV: {file_path}")
                return df

        # Check the sample data directory
        sample_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "data")
        sample_csv = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "..", "data", "multi_db_sample_data", "CSV", "sample-simple.csv")
        if os.path.exists(sample_csv):
            logger.info(f"Reading sample CSV: {sample_csv}")
            df = pd.read_csv(sample_csv)
            logger.info(f"Read {len(df)} rows from sample CSV")
            return df

        # Last resort: check the data directory in the project root
        alt_paths = [
            "data/sample_data.csv",
            "sample_data.csv",
            "apps/backend/data/sample_data.csv",
        ]
        for alt_path in alt_paths:
            abs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", alt_path)
            if os.path.exists(abs_path):
                logger.info(f"Reading data from: {abs_path}")
                df = pd.read_csv(abs_path)
                return df

        logger.warning(f"No data source files found for data_source_id={data_source_id}. Please upload a CSV file first.")
        return None

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize extracted data."""
        df = df.dropna()
        df = df.drop_duplicates()
        if "email" in df.columns:
            df["email"] = df["email"].str.lower().str.strip()
        if "name" in df.columns:
            df["name"] = df["name"].str.strip()
        # Normalize column names
        df.columns = [c.lower().replace(' ', '_').replace('-', '_') for c in df.columns]
        return df

    async def _extract_entities(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Extract entities from the actual data columns dynamically."""
        entities = []
        columns = df.columns.tolist()
        
        # Detect entity types from column names dynamically
        for _, row in df.iterrows():
            # Customer/Person detection
            if any(name_col in columns for name_col in ['name', 'customer_name', 'first_name', 'full_name', 'employee_name']):
                name_col = next(c for c in columns if c in ['name', 'customer_name', 'first_name', 'full_name', 'employee_name'])
                entity_type = 'Customer' if 'customer_id' in columns or 'customer' in str(row.get('customer_id', '') or '').lower() else 'Person'
                props = {}
                for col in columns:
                    val = row.get(col)
                    if pd.notna(val):
                        try:
                            props[col] = float(val) if isinstance(val, (int, float)) else str(val)
                        except (ValueError, TypeError):
                            props[col] = str(val)
                entities.append({
                    "type": entity_type,
                    "name": str(row[name_col]),
                    "properties": props,
                })
            
            # Product detection
            if any(prod_col in columns for prod_col in ['product', 'product_name', 'item', 'service']):
                prod_col = next(c for c in columns if c in ['product', 'product_name', 'item', 'service'])
                props = {}
                for col in columns:
                    if col != prod_col:
                        val = row.get(col)
                        if pd.notna(val):
                            try:
                                props[col] = float(val) if isinstance(val, (int, float)) else str(val)
                            except (ValueError, TypeError):
                                props[col] = str(val)
                entities.append({
                    "type": "Product",
                    "name": str(row[prod_col]),
                    "properties": props,
                })

            # If no specific entity columns found, create generic entities from all data
            if not entities:
                for col in columns:
                    val = row.get(col)
                    if pd.notna(val) and isinstance(val, str) and len(str(val)) > 2:
                        entities.append({
                            "type": "Entity",
                            "name": str(val)[:100],
                            "properties": {"column": col, "value": str(val)[:200]},
                        })
                        break  # One entity per row to avoid explosion

        return entities

    async def _build_graph(self, entities: List[Dict[str, Any]]):
        """Build Neo4j graph from extracted entities with fallback to SQLite."""
        for entity in entities[:50]:
            try:
                await graph_service.create_node(entity["type"], entity["properties"])
            except Exception as e:
                logger.warning(f"Failed to create node {entity.get('name', 'unknown')}: {e}")

    async def _detect_communities(self):
        """
        SRS: Community Detection — Detect communities in graph using NetworkX.
        Uses the Louvain algorithm on the knowledge graph to find clusters.
        """
        try:
            import networkx as nx
            from collections import defaultdict

            stats = await graph_service.get_graph_stats()
            node_count = stats.get("node_count", 0)

            if node_count == 0:
                return {"communities": 0, "method": "no_data", "modularity": 0.0, "details": []}

            # Build a NetworkX graph from stored entities
            G = nx.Graph()

            # Try to get actual graph edges
            graph_data = await graph_service.get_graph(limit=200)
            nodes_data = graph_data.get("nodes", [])
            edges_data = graph_data.get("edges", [])

            # Check if we have a JSON store or database records
            store_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "graph_store.json"
            )
            store_detected = False

            for node in nodes_data:
                G.add_node(node.get("id", node.get("name", "")),
                           label=node.get("label", "Entity"),
                           name=node.get("name", ""))

            for edge in edges_data:
                G.add_edge(edge.get("source", ""), edge.get("target", ""),
                          relationship=edge.get("relationship", "CONNECTED"))

            # Fallback: create a small graph based on node labels (different labels = different communities)
            if G.number_of_edges() == 0:
                labels = stats.get("node_labels", ["Entity"])
                if len(nodes_data) > 1:
                    # Create synthetic edges based on shared labels
                    label_groups = defaultdict(list)
                    for node in nodes_data:
                        label = node.get("label", "Entity")
                        label_groups[label].append(node.get("id", node.get("name", "")))

                    for label, node_ids in label_groups.items():
                        for i in range(len(node_ids) - 1):
                            G.add_edge(node_ids[i], node_ids[i + 1], relationship="SIMILAR_LABEL")

            if G.number_of_nodes() > 0:
                try:
                    from networkx.algorithms.community import louvain_communities
                    communities = louvain_communities(G, seed=42)
                    num_communities = len(communities)
                    # Calculate modularity as a quality metric
                    try:
                        from networkx.algorithms.community import modularity
                        mod = modularity(G, communities)
                    except Exception:
                        mod = 0.0

                    # Build community details
                    community_details = []
                    for i, comm in enumerate(communities):
                        members = [n for n in comm]
                        labels = [G.nodes[n].get("label", "Entity") for n in members if n in G.nodes]
                        community_details.append({
                            "id": i,
                            "size": len(members),
                            "top_labels": list(set(labels))[:3],
                            "members": members[:10],
                        })

                    logger.info(f"Community detection: {num_communities} communities found, modularity={mod:.3f}")
                    return {
                        "communities": num_communities,
                        "method": "louvain",
                        "modularity": round(mod, 3),
                        "details": community_details[:5],
                    }
                except ImportError:
                    logger.warning("networkx louvain not available, using heuristic")
                    num_communities = max(1, node_count // 5)
                    return {
                        "communities": num_communities,
                        "method": "heuristic",
                        "modularity": 0.0,
                        "details": [{"id": 0, "size": node_count, "top_labels": stats.get("node_labels", [])}],
                    }

            return {"communities": 0, "method": "no_graph", "modularity": 0.0, "details": []}

        except Exception as e:
            logger.warning(f"Community detection skipped: {e}")
            return {"communities": 0, "method": "error", "modularity": 0.0, "error": str(e)}


etl_pipeline = ETLPipeline()
