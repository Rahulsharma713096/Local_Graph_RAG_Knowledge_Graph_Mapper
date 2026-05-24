import httpx
import json
import logging
import time
import asyncio
from typing import Optional, List, Dict, Any, Callable, Awaitable
from app.core.config import settings

logger = logging.getLogger(__name__)

# Benchmark cache to avoid re-running benchmarks frequently
_benchmark_cache: Dict[str, Dict[str, Any]] = {}
_benchmark_cache_time: float = 0
BENCHMARK_CACHE_TTL = 300  # 5 minutes


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.default_model = settings.OLLAMA_DEFAULT_MODEL
        self._available_models = []
        self._client = None
        self._benchmarking = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the httpx client to avoid event loop issues on Windows."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def check_availability(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                self._available_models = [
                    {
                        "name": model["name"],
                        "model_size": self._format_size(model.get("size", 0)),
                    }
                    for model in data.get("models", [])
                ]
                return self._available_models
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
        return []

    async def pull_model(self, model_name: str) -> bool:
        try:
            client = await self._get_client()
            async with client.stream("POST", f"{self.base_url}/api/pull", json={"name": model_name}) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if data.get("status") == "success":
                            return True
            return False
        except Exception as e:
            logger.error(f"Failed to pull model {model_name}: {e}")
            return False

    async def generate(self, prompt: str, model: Optional[str] = None, stream: bool = False) -> str:
        model_name = model or self.default_model
        try:
            client = await self._get_client()
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            }
            if stream:
                full_response = []
                async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            full_response.append(data.get("response", ""))
                            if data.get("done", False):
                                break
                return "".join(full_response)
            else:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return f"Error: Unable to generate response - {str(e)}"

    async def generate_with_buffer(
        self,
        prompt: str,
        model: Optional[str] = None,
        on_status: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> str:
        """
        Streaming generation with buffering for slow Ollama responses.
        Calls on_status callback with buffering progress updates (start, chunk, done, error).
        """
        model_name = model or self.default_model
        buffer = []
        total_chars = 0
        start_time = time.time()
        try:
            client = await self._get_client()
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                },
            }

            # Notify: buffering started
            if on_status:
                await on_status({
                    "event": "buffering_start",
                    "model": model_name,
                    "prompt_length": len(prompt),
                    "timestamp": start_time,
                })

            async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        buffer.append(chunk)
                        total_chars += len(chunk)

                        # Notify: chunk received (buffer progress)
                        if on_status and chunk:
                            elapsed = time.time() - start_time
                            await on_status({
                                "event": "buffer_chunk",
                                "model": model_name,
                                "chars_buffered": total_chars,
                                "elapsed_seconds": round(elapsed, 1),
                                "latest_chunk": chunk[:50],
                            })

                        if data.get("done", False):
                            break

            full_text = "".join(buffer)
            elapsed = time.time() - start_time

            # Notify: buffering complete
            if on_status:
                await on_status({
                    "event": "buffering_done",
                    "model": model_name,
                    "total_chars": len(full_text),
                    "elapsed_seconds": round(elapsed, 1),
                })

            return full_text

        except Exception as e:
            logger.error(f"Buffered generation failed: {e}")
            if on_status:
                await on_status({
                    "event": "buffering_error",
                    "error": str(e),
                    "model": model_name,
                })
            return f"Error: {str(e)}"

    async def is_model_available(self, model_name: str) -> bool:
        """Check if a specific model exists in the available models list."""
        if not self._available_models:
            await self.list_models()
        return any(m["name"] == model_name or m["name"].startswith(model_name) for m in self._available_models)

    async def get_model_info(self, model_name: str) -> Dict[str, Any]:
        try:
            client = await self._get_client()
            response = await client.post(f"{self.base_url}/api/show", json={"name": model_name})
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": model_name,
                    "model_size": self._format_size(data.get("size", 0)),
                    "context_size": data.get("context_length", 4096),
                    "parameters": data.get("parameters", ""),
                    "details": data.get("details", {}),
                }
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
            return {"name": model_name, "error": str(e)}
        return {"name": model_name, "error": "Unknown error"}

    async def benchmark_model(self, model_name: str) -> Dict[str, Any]:
        """
        SRS: Benchmark Engine — Run a real-time benchmark on a model to measure:
        - Tokens per second (speed)
        - Context window utilization
        - VRAM estimation
        - RAG suitability score
        Results are cached for BENCHMARK_CACHE_TTL seconds.
        """
        global _benchmark_cache, _benchmark_cache_time
        now = time.time()

        # Return cached results if fresh
        if model_name in _benchmark_cache and (now - _benchmark_cache_time) < BENCHMARK_CACHE_TTL:
            return _benchmark_cache[model_name]

        if self._benchmarking:
            # Return estimated values while a benchmark is in progress
            return self._estimate_benchmark(model_name)

        self._benchmarking = True
        try:
            benchmark = self._estimate_benchmark(model_name)

            # Run real benchmark if model is available
            is_available = await self.check_availability()
            if is_available:
                try:
                    client = await self._get_client()

                    # 1. Measure tokens/sec with a short generation
                    test_prompt = "Write a brief overview of knowledge graphs in 2-3 sentences."
                    start_time = time.time()
                    total_chars = 0

                    payload = {
                        "model": model_name,
                        "prompt": test_prompt,
                        "stream": True,
                        "options": {"temperature": 0.1},
                    }

                    async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                        async for line in response.aiter_lines():
                            if line:
                                data = json.loads(line)
                                chunk = data.get("response", "")
                                total_chars += len(chunk)
                                if data.get("done", False):
                                    eval_count = data.get("eval_count", 0)
                                    eval_duration = data.get("eval_duration", 0)
                                    if eval_duration > 0:
                                        benchmark["speed_score"] = round(eval_count / (eval_duration / 1e9), 1)
                                    benchmark["eval_count"] = eval_count
                                    benchmark["total_duration_ns"] = data.get("total_duration", 0)
                                    break

                    elapsed = time.time() - start_time
                    if benchmark["speed_score"] == 0 and elapsed > 0:
                        benchmark["speed_score"] = round(total_chars / elapsed, 1)

                    # 2. Get model details for context window
                    info = await self.get_model_info(model_name)
                    if info.get("context_size"):
                        benchmark["context_size"] = info["context_size"]

                    logger.info(f"Benchmarked {model_name}: {benchmark['speed_score']} tok/s, context={benchmark['context_size']}")
                except Exception as e:
                    logger.warning(f"Real-time benchmark failed for {model_name}, using estimates: {e}")

            # Calculate RAG suitability based on benchmark data
            benchmark["rag_suitability"] = self._calc_rag_suitability(benchmark)

            # Cache results
            _benchmark_cache[model_name] = benchmark
            _benchmark_cache_time = now

            return benchmark
        finally:
            self._benchmarking = False

    def _estimate_benchmark(self, model_name: str) -> Dict[str, Any]:
        """Return estimated benchmark values based on model name heuristics."""
        name_lower = model_name.lower()

        # Speed estimates (tokens/sec) based on model size
        speed_estimates = {
            "llama3.1": 7.5, "llama3": 7.0, "llama": 6.5,
            "mistral": 8.0, "mixtral": 6.0,
            "phi3": 9.0, "phi": 8.5,
            "codellama": 6.5, "codegemma": 7.0,
            "gemma": 8.5, "gemma2": 7.5,
            "deepseek": 5.5, "deepseek-coder": 5.0,
            "qwen": 6.0, "qwen2": 5.5,
            "nomic-embed": 15.0, "mxbai-embed": 14.0,
        }

        # Context window estimates
        context_estimates = {
            "llama3.1": 8192, "llama3": 8192, "llama": 4096,
            "mistral": 8192, "mixtral": 32768,
            "phi3": 4096, "phi": 2048,
            "codellama": 16384, "codegemma": 8192,
            "gemma": 8192, "gemma2": 8192,
            "deepseek": 32768, "deepseek-coder": 16384,
            "qwen": 32768, "qwen2": 131072,
            "nomic-embed": 2048, "mxbai-embed": 512,
        }

        # VRAM estimates (GB)
        vram_estimates = {
            "llama3.1": "8GB", "llama3": "8GB", "llama": "4GB",
            "mistral": "6GB", "mixtral": "24GB",
            "phi3": "4GB", "phi": "2GB",
            "codellama": "8GB", "codegemma": "6GB",
            "gemma": "4GB", "gemma2": "4GB",
            "deepseek": "12GB", "deepseek-coder": "8GB",
            "qwen": "12GB", "qwen2": "16GB",
            "nomic-embed": "2GB", "mxbai-embed": "2GB",
        }

        speed = 7.0
        context = 4096
        vram = "8GB"

        for key, val in speed_estimates.items():
            if key in name_lower:
                speed = val
                break

        for key, val in context_estimates.items():
            if key in name_lower:
                context = val
                break

        for key, val in vram_estimates.items():
            if key in name_lower:
                vram = val
                break

        return {
            "name": model_name,
            "speed_score": speed,
            "context_size": context,
            "vram_estimate": vram,
            "eval_count": 0,
            "total_duration_ns": 0,
        }

    def _calc_rag_suitability(self, benchmark: Dict[str, Any]) -> float:
        """Calculate RAG suitability score (0-10) based on benchmark metrics."""
        score = 7.5  # baseline

        # Higher context = better for RAG
        context = benchmark.get("context_size", 4096)
        if context >= 32768:
            score += 1.5
        elif context >= 16384:
            score += 1.0
        elif context >= 8192:
            score += 0.5

        # Faster speed = slightly better
        speed = benchmark.get("speed_score", 7.0)
        if speed >= 10:
            score += 0.5
        elif speed >= 8:
            score += 0.3

        # Cap at 10
        return min(round(score, 1), 10.0)

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / 1024**2:.1f} MB"
        else:
            return f"{size_bytes / 1024**3:.2f} GB"

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


ollama_service = OllamaService()
