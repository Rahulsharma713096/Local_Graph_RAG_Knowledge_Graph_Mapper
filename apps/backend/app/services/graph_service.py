from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Optional
import logging
import json
import os
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.database_models import GraphNode

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(self):
        self._driver = None
        self._local_store_path = os.path.join(os.path.dirname(settings.FAISS_INDEX_PATH) or ".", "graph_store.json")
        self._neo4j_available = False

    async def _get_driver(self):
        """Lazy-init Neo4j driver with connection verification."""
        if self._driver is None:
            try:
                self._driver = AsyncGraphDatabase.driver(
                    settings.NEO4J_URI,
                    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                )
                # Test connection
                async with self._driver.session() as session:
                    result = await session.run("RETURN 1 as test")
                    await result.single()
                self._neo4j_available = True
                logger.info("Neo4j connection established successfully")
            except Exception as e:
                logger.warning(f"Neo4j unavailable, using local fallback storage: {e}")
                self._neo4j_available = False
                if self._driver:
                    try:
                        await self._driver.close()
                    except Exception:
                        pass
                    self._driver = None
        return self._driver

    async def verify_connection(self) -> bool:
        if self._driver is None:
            try:
                driver = await self._get_driver()
                if driver is None:
                    return False
                async with driver.session() as session:
                    result = await session.run("RETURN 1 as test")
                    record = await result.single()
                    return record is not None
            except Exception as e:
                logger.error(f"Neo4j connection failed: {e}")
                return False
        return self._neo4j_available

    # ── Local Fallback Storage ──────────────────────────────────────

    def _load_local_store(self) -> dict:
        """Load local graph store from JSON file."""
        try:
            if os.path.exists(self._local_store_path):
                with open(self._local_store_path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load local graph store: {e}")
        return {"nodes": [], "edges": []}

    def _save_local_store(self, data: dict) -> None:
        """Save local graph store to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._local_store_path) or ".", exist_ok=True)
            with open(self._local_store_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save local graph store: {e}")

    async def get_graph(self, limit: int = 100) -> Dict[str, List]:
        if self._neo4j_available:
            try:
                return await self._get_graph_neo4j(limit)
            except Exception as e:
                logger.warning(f"Neo4j graph fetch failed, falling back to local: {e}")
                self._neo4j_available = False
        return await self._get_graph_local(limit)

    async def _get_graph_neo4j(self, limit: int = 100) -> Dict[str, List]:
        driver = await self._get_driver()
        if driver is None:
            return await self._get_graph_local(limit)
        nodes = []
        edges = []
        try:
            async with driver.session() as session:
                result = await session.run(f"MATCH (n) RETURN n LIMIT {limit}")
                async for record in result:
                    node = record["n"]
                    nodes.append({
                        "id": node.element_id,
                        "label": list(node.labels)[0] if node.labels else "Node",
                        "name": node.get("name", str(node.element_id)),
                        "properties": dict(node.items()),
                    })

                result = await session.run(f"MATCH ()-[r]->() RETURN r LIMIT {limit * 2}")
                async for record in result:
                    rel = record["r"]
                    edges.append({
                        "source": rel.start_node.element_id,
                        "target": rel.end_node.element_id,
                        "relationship": rel.type,
                        "properties": dict(rel.items()),
                    })
        except Exception as e:
            logger.error(f"Failed to get graph from Neo4j: {e}")
            raise
        return {"nodes": nodes, "edges": edges}

    async def _get_graph_local(self, limit: int = 100) -> Dict[str, List]:
        """Get graph data from local SQLite/JSON fallback."""
        try:
            db = SessionLocal()
            try:
                nodes = db.query(GraphNode).limit(limit).all()
                if nodes:
                    result_nodes = [
                        {
                            "id": str(n.id),
                            "label": n.label,
                            "name": n.name,
                            "properties": n.properties or {},
                        }
                        for n in nodes
                    ]
                    return {"nodes": result_nodes, "edges": []}
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"SQLite graph query failed, trying JSON store: {e}")

        # Fallback to JSON file store
        store = self._load_local_store()
        if store.get("nodes") or store.get("edges"):
            return {
                "nodes": store.get("nodes", [])[:limit],
                "edges": store.get("edges", [])[:limit * 2],
            }

        # Return empty graph — NO hardcoded demo data
        return {"nodes": [], "edges": []}

    async def execute_cypher(self, query: str) -> List[Dict[str, Any]]:
        if not self._neo4j_available:
            logger.warning("Cypher execution unavailable - Neo4j not connected")
            return []
        driver = await self._get_driver()
        if driver is None:
            return []
        results = []
        try:
            async with driver.session() as session:
                result = await session.run(query)
                async for record in result:
                    results.append(dict(record))
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
            raise
        return results

    async def create_node(self, label: str, properties: Dict[str, Any]) -> Dict:
        """Create a node - tries Neo4j first, falls back to SQLite/JSON."""
        if self._neo4j_available:
            try:
                return await self._create_node_neo4j(label, properties)
            except Exception as e:
                logger.warning(f"Neo4j node creation failed, falling back: {e}")
                self._neo4j_available = False
        return await self._create_node_local(label, properties)

    async def _create_node_neo4j(self, label: str, properties: Dict[str, Any]) -> Dict:
        driver = await self._get_driver()
        if driver is None:
            return await self._create_node_local(label, properties)
        props_string = ", ".join([f"{k}: ${k}" for k in properties.keys()])
        query = f"CREATE (n:{label} {{{props_string}}}) RETURN n"
        try:
            async with driver.session() as session:
                result = await session.run(query, **properties)
                record = await result.single()
                if record:
                    node = record["n"]
                    return {
                        "id": node.element_id,
                        "label": list(node.labels)[0],
                        "properties": dict(node.items()),
                    }
        except Exception as e:
            logger.error(f"Failed to create Neo4j node: {e}")
            raise
        return {}

    async def _create_node_local(self, label: str, properties: Dict[str, Any]) -> Dict:
        """Create node in local SQLite fallback."""
        import time
        try:
            db = SessionLocal()
            try:
                name = properties.get("name", f"{label}_{int(time.time() * 1000)}")
                node = GraphNode(
                    label=label,
                    name=str(name),
                    properties=properties,
                )
                db.add(node)
                db.commit()
                db.refresh(node)
                return {
                    "id": str(node.id),
                    "label": node.label,
                    "name": node.name,
                    "properties": node.properties or {},
                }
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to create local node: {e}")
            # Fallback to JSON file
            store = self._load_local_store()
            node_id = f"local_{len(store['nodes'])}"
            node = {
                "id": node_id,
                "label": label,
                "name": properties.get("name", node_id),
                "properties": properties,
            }
            store["nodes"].append(node)
            self._save_local_store(store)
            return node

    async def get_graph_stats(self) -> Dict[str, Any]:
        stats = {"node_count": 0, "edge_count": 0, "node_labels": [], "relationship_types": []}
        
        if self._neo4j_available:
            try:
                driver = await self._get_driver()
                if driver:
                    async with driver.session() as session:
                        result = await session.run("MATCH (n) RETURN count(n) as count, collect(distinct labels(n)) as labels")
                        record = await result.single()
                        if record:
                            stats["node_count"] = record["count"]
                            stats["node_labels"] = [l for sublist in record["labels"] for l in sublist]

                        result = await session.run("MATCH ()-[r]->() RETURN count(r) as count, collect(distinct type(r)) as types")
                        record = await result.single()
                        if record:
                            stats["edge_count"] = record["count"]
                            stats["relationship_types"] = list(set(record["types"]))
                return stats
            except Exception as e:
                logger.warning(f"Neo4j stats failed, using local: {e}")
                self._neo4j_available = False

        # Local fallback
        try:
            db = SessionLocal()
            try:
                node_count = db.query(GraphNode).count()
                distinct_labels = [r[0] for r in db.query(GraphNode.label).distinct().all()]
                stats["node_count"] = node_count
                stats["node_labels"] = distinct_labels
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"SQLite stats failed, using JSON: {e}")
            store = self._load_local_store()
            stats["node_count"] = len(store.get("nodes", []))
            stats["node_labels"] = list(set(n.get("label", "Node") for n in store.get("nodes", [])))

        return stats

    async def close(self):
        if self._driver:
            try:
                await self._driver.close()
            except Exception:
                pass
            self._driver = None


graph_service = GraphService()
