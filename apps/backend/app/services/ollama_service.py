import httpx
import json
import logging
import time
from typing import Optional, List, Dict, Any, Callable, Awaitable
from app.core.config import settings

logger = logging.getLogger(__name__)


class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.default_model = settings.OLLAMA_DEFAULT_MODEL
        self._available_models = []
        self._client = None

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
                }
        except Exception as e:
            logger.error(f"Failed to get model info: {e}")
        return {"name": model_name, "error": str(e)}

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
