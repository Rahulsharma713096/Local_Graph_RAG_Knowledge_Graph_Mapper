import logging
import time
import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
from app.services.graph_service import graph_service
from app.services.embedding_service import embedding_service
from app.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)


class RAGService:
    async def query(
        self,
        natural_query: str,
        traversal_depth: int = 2,
        model: Optional[str] = None,
        on_buffering: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        start_time = time.time()
        pipeline_steps = []
        result = {
            "answer": "",
            "generated_cypher": "",
            "retrieved_context": [],
            "execution_time_ms": 0,
            "pipeline_steps": [],
            "buffering": {"active": False, "events": []},
        }

        buffering_events = []

        async def _buffering_handler(event: Dict[str, Any]):
            """Collect buffering events and notify via callback."""
            buffering_events.append(event)
            if on_buffering:
                await on_buffering(event)

        try:
            # Step 1: Embed query
            pipeline_steps.append({"step": "Embed Query", "status": "running"})
            query_embedding = embedding_service.encode([natural_query])
            pipeline_steps[-1]["status"] = "completed"

            # Step 2: Retrieve graph context
            pipeline_steps.append({"step": "Retrieve Graph Context", "status": "running"})
            graph_context = await self._retrieve_graph_context(natural_query, traversal_depth)
            result["retrieved_context"] = graph_context
            pipeline_steps[-1]["status"] = "completed"

            # Step 3: Generate Cypher (may call Ollama)
            pipeline_steps.append({"step": "Generate Cypher", "status": "running"})
            cypher_query = await self._generate_cypher(natural_query, graph_context, _buffering_handler)
            result["generated_cypher"] = cypher_query
            pipeline_steps[-1]["status"] = "completed"

            # Step 4: Execute graph search
            pipeline_steps.append({"step": "Execute Graph Search", "status": "running"})
            graph_results = await self._execute_graph_search(cypher_query)
            pipeline_steps[-1]["status"] = "completed"

            # Step 5: Generate answer — THIS IS WHERE OLLAMA IS CALLED (slow part)
            pipeline_steps.append({
                "step": "Generate Answer",
                "status": "running",
                "buffering": True,
                "buffering_detail": "Waiting for Ollama response...",
            })
            result["buffering"]["active"] = True
            answer = await self._generate_answer(natural_query, graph_results, model, _buffering_handler)
            result["answer"] = answer
            pipeline_steps[-1]["status"] = "completed"
            pipeline_steps[-1]["buffering"] = False
            result["buffering"]["active"] = False

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            pipeline_steps.append({"step": "Error", "status": "failed", "error": str(e)})
            result["answer"] = f"Query processing error: {str(e)}"
            result["buffering"]["active"] = False

        result["execution_time_ms"] = (time.time() - start_time) * 1000
        result["pipeline_steps"] = pipeline_steps
        result["buffering"]["events"] = buffering_events
        return result

    async def _retrieve_graph_context(self, query: str, depth: int) -> List[Dict]:
        """Retrieve context from the knowledge graph."""
        context = []
        try:
            stats = await graph_service.get_graph_stats()
            if stats["node_count"] > 0:
                context.append({
                    "type": "graph_stats",
                    "data": stats,
                })

            # Search vector index for similar content
            vector_results = embedding_service.search(query, k=5)
            if vector_results:
                context.append({
                    "type": "vector_search",
                    "data": vector_results,
                })
        except Exception as e:
            logger.warning(f"Context retrieval partial failure: {e}")

        return context

    async def _generate_cypher(self, query: str, context: List[Dict],
                                on_buffering: Optional[Callable] = None) -> str:
        """Generate a Cypher query based on the natural language query."""
        prompt = f"""Given the following natural language query about a knowledge graph, generate a Cypher query.

Natural Query: {query}

Context: The graph contains nodes like Customer, Product, Order, Supplier, Employee.
Relationships include PURCHASED, SUPPLIES, WORKS_FOR, etc.

Generate only the Cypher query, no explanation:
"""
        cypher = await ollama_service.generate(prompt)
        return cypher.strip()

    async def _execute_graph_search(self, cypher_query: str) -> List[Dict]:
        """Execute the generated Cypher query."""
        try:
            if cypher_query and not cypher_query.startswith("Error"):
                results = await graph_service.execute_cypher(cypher_query)
                return results[:10]
        except Exception as e:
            logger.warning(f"Cypher execution failed, using fallback: {e}")

        return []

    async def _generate_answer(
        self, query: str, graph_results: List[Dict], model: Optional[str],
        on_buffering: Optional[Callable] = None,
    ) -> str:
        """Generate a natural language answer using the LLM."""
        context_str = str(graph_results[:5]) if graph_results else "No graph data found"

        prompt = f"""You are a Graph RAG assistant. Answer the user's question based on the knowledge graph context.

Question: {query}

Graph Context: {context_str}

Provide a concise, informative answer based on the available graph data:"""

        answer = await ollama_service.generate_with_buffer(prompt, model, on_status=on_buffering)
        return answer.strip()


rag_service = RAGService()
