from neo4j import AsyncGraphDatabase, GraphDatabase
from typing import List, Dict, Any, Optional
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class GraphService:
    def __init__(self):
        self._driver = None

    async def _get_driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    async def verify_connection(self) -> bool:
        try:
            driver = await self._get_driver()
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                return record is not None
        except Exception as e:
            logger.error(f"Neo4j connection failed: {e}")
            return False

    async def get_graph(self, limit: int = 100) -> Dict[str, List]:
        driver = await self._get_driver()
        nodes = []
        edges = []

        try:
            async with driver.session() as session:
                result = await session.run(
                    f"MATCH (n) RETURN n LIMIT {limit}"
                )
                async for record in result:
                    node = record["n"]
                    nodes.append({
                        "id": node.element_id,
                        "label": list(node.labels)[0] if node.labels else "Node",
                        "name": node.get("name", str(node.element_id)),
                        "properties": dict(node.items()),
                    })

                result = await session.run(
                    f"MATCH ()-[r]->() RETURN r LIMIT {limit * 2}"
                )
                async for record in result:
                    rel = record["r"]
                    edges.append({
                        "source": rel.start_node.element_id,
                        "target": rel.end_node.element_id,
                        "relationship": rel.type,
                        "properties": dict(rel.items()),
                    })
        except Exception as e:
            logger.error(f"Failed to get graph: {e}")

        return {"nodes": nodes, "edges": edges}

    async def execute_cypher(self, query: str) -> List[Dict[str, Any]]:
        driver = await self._get_driver()
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
        driver = await self._get_driver()
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
            logger.error(f"Failed to create node: {e}")
            raise
        return {}

    async def get_graph_stats(self) -> Dict[str, Any]:
        driver = await self._get_driver()
        stats = {"node_count": 0, "edge_count": 0, "node_labels": [], "relationship_types": []}
        try:
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
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
        return stats

    async def close(self):
        if self._driver:
            await self._driver.close()
            self._driver = None


graph_service = GraphService()
