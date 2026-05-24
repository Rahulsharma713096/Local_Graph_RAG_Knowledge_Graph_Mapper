import logging
import time
import asyncio
import os
from typing import List, Dict, Any, Optional, Callable, Awaitable
from app.services.graph_service import graph_service
from app.services.embedding_service import embedding_service
from app.services.ollama_service import ollama_service

# Ensure logs directory exists - use current working directory for portability
log_dir = os.path.join(os.getcwd(), "logs")
os.makedirs(log_dir, exist_ok=True)

# Set up file handler for query logs
query_logger = logging.getLogger("rag_service")
query_logger.setLevel(logging.DEBUG)
if not query_logger.handlers:
    fh = logging.FileHandler(os.path.join(log_dir, "rag_queries.log"))
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    query_logger.addHandler(fh)

logger = logging.getLogger(__name__)


class RAGService:
    async def query(
        self,
        natural_query: str,
        traversal_depth: int = 2,
        model: Optional[str] = None,
        on_buffering: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        retry: bool = False,
    ) -> Dict[str, Any]:
        start_time = time.time()
        pipeline_steps = []
        timeline = []  # SRS Query Timeline tracking

        result = {
            "answer": "",
            "generated_cypher": "",
            "retrieved_context": [],
            "execution_time_ms": 0,
            "pipeline_steps": [],
            "buffering": {"active": False, "events": []},
            "timeline": [],  # SRS: Per-step timing
        }

        buffering_events = []
        last_timeline_time = start_time

        def _record_timeline(step_name: str, status: str = "running", detail: str = ""):
            nonlocal last_timeline_time
            now = time.time()
            elapsed = now - last_timeline_time
            entry = {
                "step": step_name,
                "status": status,
                "duration_ms": round(elapsed * 1000, 1),
                "timestamp": now,
            }
            if detail:
                entry["detail"] = detail
            timeline.append(entry)
            last_timeline_time = now
            return entry

        async def _buffering_handler(event: Dict[str, Any]):
            """Collect buffering events and notify via callback."""
            buffering_events.append(event)
            if on_buffering:
                await on_buffering(event)

        try:
            # Step 1: Validate input
            if not natural_query or (isinstance(natural_query, str) and not natural_query.strip()):
                error_msg = "Query cannot be empty"
                query_logger.warning(f"Query validation failed: {error_msg}")
                pipeline_steps.append({"step": "Validation", "status": "failed", "error": error_msg})
                _record_timeline("Validation", "failed", error_msg)
                result["answer"] = f"Query processing error: {error_msg}"
                result["execution_time_ms"] = (time.time() - start_time) * 1000
                result["pipeline_steps"] = pipeline_steps
                result["timeline"] = timeline
                result["graph_found"] = False
                return result

            query_safe = natural_query if natural_query else ""
            query_logger.info(f"RAG query started - query='{query_safe[:100]}' depth={traversal_depth} model={model} retry={retry}")

            # Step 1: Embed query
            pipeline_steps.append({"step": "Embed Query", "status": "running"})
            _record_timeline("Embed Query", "running")
            query_embedding = embedding_service.encode([natural_query])
            pipeline_steps[-1]["status"] = "completed"
            _record_timeline("Embed Query", "completed", f"shape={query_embedding.shape if hasattr(query_embedding, 'shape') else 'N/A'}")
            query_logger.debug(f"Embedding completed - shape={query_embedding.shape if hasattr(query_embedding, 'shape') else 'N/A'}")

            # Step 2: Retrieve graph context
            pipeline_steps.append({"step": "Retrieve Graph Context", "status": "running"})
            _record_timeline("Retrieve Graph Context", "running")
            graph_context = await self._retrieve_graph_context(natural_query, traversal_depth)
            result["retrieved_context"] = graph_context
            pipeline_steps[-1]["status"] = "completed"
            _record_timeline("Retrieve Graph Context", "completed", f"{len(graph_context)} items")
            query_logger.debug(f"Graph context retrieved - {len(graph_context)} items")

            # Step 3: Generate Cypher (may call Ollama)
            pipeline_steps.append({"step": "Generate Cypher", "status": "running"})
            _record_timeline("Generate Cypher", "running")
            cypher_query = await self._generate_cypher(natural_query, graph_context, _buffering_handler, retry=retry)
            result["generated_cypher"] = cypher_query or ""
            pipeline_steps[-1]["status"] = "completed"
            _record_timeline("Generate Cypher", "completed", f"len={len(cypher_query or '')}")
            query_logger.debug(f"Cypher generated - length={len(cypher_query or '')}")

            # Step 4: Execute graph search
            pipeline_steps.append({"step": "Execute Graph Search", "status": "running"})
            _record_timeline("Execute Graph Search", "running")
            graph_results = await self._execute_graph_search(cypher_query)
            pipeline_steps[-1]["status"] = "completed"
            _record_timeline("Execute Graph Search", "completed", f"{len(graph_results)} results")
            query_logger.debug(f"Graph search executed - {len(graph_results)} results")

            # Determine if graph data was found
            has_graph_data = bool(graph_results)
            result["graph_found"] = has_graph_data

            # Step 5: Generate answer
            pipeline_steps.append({
                "step": "Generate Answer",
                "status": "running",
                "buffering": True,
                "buffering_detail": "Waiting for Ollama response...",
            })
            _record_timeline("Generate Answer", "running", "calling Ollama")
            result["buffering"]["active"] = True

            if not has_graph_data and not retry:
                result["followup_suggestion"] = (
                    "No matching graph data was found for your query. "
                    "Would you like me to perform a broader search on the graph database to find relevant information? "
                    "I'll search all available nodes and relationships to help answer your question."
                )
                answer = await self._generate_answer(natural_query, [], model, _buffering_handler)
            else:
                result["followup_suggestion"] = None
                answer = await self._generate_answer(natural_query, graph_results, model, _buffering_handler)

            result["answer"] = answer or ""
            pipeline_steps[-1]["status"] = "completed"
            pipeline_steps[-1]["buffering"] = False
            _record_timeline("Generate Answer", "completed", f"{len(answer or '')} chars")
            result["buffering"]["active"] = False
            query_logger.info(f"Answer generated - {len(answer or '')} chars")

        except Exception as e:
            logger.error(f"RAG query failed: {e}", exc_info=True)
            query_logger.error(f"RAG query failed: {e}", exc_info=True)
            pipeline_steps.append({"step": "Error", "status": "failed", "error": str(e)})
            _record_timeline("Error", "failed", str(e))
            result["answer"] = f"Query processing error: {str(e)}"
            result["buffering"]["active"] = False
            result["graph_found"] = False

        result["execution_time_ms"] = (time.time() - start_time) * 1000
        result["pipeline_steps"] = pipeline_steps
        result["timeline"] = timeline
        result["buffering"]["events"] = buffering_events
        query_logger.info(f"RAG query completed - {result['execution_time_ms']:.1f}ms - {len(timeline)} timeline steps - status={'success' if not any(s.get('status') == 'failed' for s in pipeline_steps) else 'failed'}")
        return result

    async def _retrieve_graph_context(self, query: str, depth: int) -> List[Dict]:
        """Retrieve context from the knowledge graph."""
        context = []
        try:
            stats = await graph_service.get_graph_stats()
            if stats and stats.get("node_count", 0) > 0:
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
                                on_buffering: Optional[Callable] = None,
                                retry: bool = False) -> str:
        """Generate a Cypher query based on the natural language query.
        When retry=True, use a broader MATCH to find all relevant nodes."""
        if retry:
            # Broader search — find all nodes related to the query topic
            prompt = f"""Given the following natural language query, generate a broad Cypher query to search the knowledge graph for relevant information.

Query: {query}

The graph contains nodes like Customer, Product, Order, Supplier, Employee with various relationships.

Generate a Cypher query that finds ALL nodes related to this topic. Use MATCH with OPTIONAL MATCH to get connected nodes.
Make the query BROAD to capture as much relevant data as possible. Include LIMIT 50 at the end.

Generate only the Cypher query, no explanation:
"""
        else:
            prompt = f"""Given the following natural language query about a knowledge graph, generate a Cypher query.

Natural Query: {query}

Context: The graph contains nodes like Customer, Product, Order, Supplier, Employee.
Relationships include PURCHASED, SUPPLIES, WORKS_FOR, etc.

Generate only the Cypher query, no explanation:
"""
        cypher = await ollama_service.generate(prompt)
        # Handle None case - Issue #6 fix
        if cypher is None:
            logger.warning("Ollama returned None for cypher generation, using default")
            if retry:
                return "MATCH (n) OPTIONAL MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 50"
            return "MATCH (n) RETURN n LIMIT 10"
        return cypher.strip() if isinstance(cypher, str) else str(cypher)

    async def _execute_graph_search(self, cypher_query: str) -> List[Dict]:
        """Execute the generated Cypher query."""
        try:
            if cypher_query and not cypher_query.startswith("Error"):
                results = await graph_service.execute_cypher(cypher_query)
                return results[:10] if results else []
        except Exception as e:
            logger.warning(f"Cypher execution failed, using fallback: {e}")

        return []

    async def _generate_answer(
        self, query: str, graph_results: List[Dict], model: Optional[str],
        on_buffering: Optional[Callable] = None,
    ) -> str:
        """
        Generate a natural language answer using the LLM.
        Fix Issues #5-8: Always uses Ollama LLM even when graph data is empty.
        The LLM provides informative responses even without graph data.
        """
        has_graph_data = bool(graph_results)
        context_str = str(graph_results[:5]) if has_graph_data else "No graph data was found in the knowledge graph for this query."

        if has_graph_data:
            prompt = f"""You are a Graph RAG assistant. Answer the user's question based on the knowledge graph context.

Question: {query}

Graph Context: {context_str}

Provide a concise, informative answer based on the available graph data. If the graph data does not fully answer the question, supplement with general knowledge:"""
        else:
            prompt = f"""You are a helpful AI assistant integrated with a Local Graph RAG system.

The knowledge graph did not contain data matching the query. However, please answer the user's question using your general knowledge.

Question: {query}

Provide a helpful, informative answer. If you're unsure about something, say so clearly rather than making up information:"""

        answer = await ollama_service.generate_with_buffer(prompt, model, on_status=on_buffering)
        # Handle None case - Issue #6 fix
        if answer is None:
            logger.warning("Ollama returned None for answer generation")
            return "Unable to generate an answer at this time. The Ollama service may not be running. Please ensure Ollama is started."
        return answer.strip() if isinstance(answer, str) else str(answer)


rag_service = RAGService()
