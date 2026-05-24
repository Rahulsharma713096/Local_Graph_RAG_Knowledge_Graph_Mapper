"""Unit tests for OllamaService - covers model listing, selection, generation, buffering."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

async_mark = pytest.mark.asyncio


@async_mark
class TestOllamaServiceInit:
    """Test OllamaService initialization."""

    async def test_singleton_exists(self):
        """ollama_service singleton should be importable."""
        from app.services.ollama_service import ollama_service
        assert ollama_service is not None
        assert ollama_service.base_url is not None
        assert ollama_service.default_model is not None


@async_mark
class TestOllamaServiceAvailability:
    """Test Ollama availability checking."""

    async def test_check_availability_true(self, patch_ollama_get_client):
        """check_availability should return True when Ollama responds."""
        from app.services.ollama_service import ollama_service
        result = await ollama_service.check_availability()
        assert result is True

    async def test_check_availability_false(self):
        """check_availability should return False when connection fails."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock.return_value = mock_client

            result = await ollama_service.check_availability()
            assert result is False


@async_mark
class TestOllamaServiceListModels:
    """Test model listing."""

    async def test_list_models_success(self, patch_ollama_get_client):
        """list_models should return parsed model list."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None
        ollama_service._available_models = []

        models = await ollama_service.list_models()
        assert len(models) > 0
        assert models[0]["name"] == "llama3.1:latest"
        assert "model_size" in models[0]

    async def test_list_models_empty_on_error(self):
        """list_models should return empty list on error."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("API error")
            mock.return_value = mock_client

            models = await ollama_service.list_models()
            assert models == []


@async_mark
class TestOllamaServiceModelAvailability:
    """Test is_model_available validation (Issue #5 fix)."""

    async def test_model_available_exact_match(self, patch_ollama_get_client):
        """is_model_available should find exact name match."""
        from app.services.ollama_service import ollama_service
        ollama_service._available_models = [
            {"name": "llama3.1:latest", "model_size": "4.37 GB"},
            {"name": "mistral:latest", "model_size": "3.82 GB"},
        ]

        result = await ollama_service.is_model_available("llama3.1:latest")
        assert result is True

    async def test_model_available_prefix_match(self, patch_ollama_get_client):
        """is_model_available should find prefix match."""
        from app.services.ollama_service import ollama_service
        ollama_service._available_models = [
            {"name": "llama3.1:latest", "model_size": "4.37 GB"},
        ]

        result = await ollama_service.is_model_available("llama3.1")
        assert result is True

    async def test_model_not_available(self, patch_ollama_get_client):
        """is_model_available should return False for unavailable model."""
        from app.services.ollama_service import ollama_service
        ollama_service._available_models = [
            {"name": "llama3.1:latest", "model_size": "4.37 GB"},
        ]

        result = await ollama_service.is_model_available("nonexistent-model")
        assert result is False

    async def test_model_available_empty_list(self, patch_ollama_get_client):
        """is_model_available should fetch models if list is empty."""
        from app.services.ollama_service import ollama_service
        ollama_service._available_models = []

        async def list_models_side_effect():
            ollama_service._available_models = [{"name": "llama3.1:latest"}]
            return ollama_service._available_models

        with patch.object(ollama_service, "list_models", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = list_models_side_effect
            result = await ollama_service.is_model_available("llama3.1:latest")
            assert result is True


@async_mark
class TestOllamaServiceGenerate:
    """Test text generation."""

    async def test_generate_non_stream(self, patch_ollama_get_client):
        """generate should return text for non-streaming."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None
        result = await ollama_service.generate("Test prompt", stream=False)
        assert "Generated text response" in result

    async def test_generate_stream(self, patch_ollama_get_client):
        """generate should concatenate streaming responses."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None
        result = await ollama_service.generate("Test prompt", stream=True)
        assert "Hello world!" in result

    async def test_generate_custom_model(self, patch_ollama_get_client):
        """generate should accept custom model parameter."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None
        result = await ollama_service.generate("Test", model="mistral:latest")
        assert result is not None

    async def test_generate_error(self):
        """generate should handle errors gracefully."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("API error")
            mock.return_value = mock_client

            result = await ollama_service.generate("Test", stream=False)
            assert "Error" in result


@async_mark
class TestOllamaServiceGenerateWithBuffer:
    """Test buffered/streaming generation."""

    async def test_generate_with_buffer_success(self, patch_ollama_get_client):
        """generate_with_buffer should return full text."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        result = await ollama_service.generate_with_buffer("Test prompt")
        assert "Hello world!" in result

    async def test_generate_with_buffer_callback(self, patch_ollama_get_client):
        """generate_with_buffer should call status callback."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        events = []
        async def capture_event(event: dict):
            events.append(event)

        result = await ollama_service.generate_with_buffer("Test", on_status=capture_event)

        # Should have called start, chunks, and done
        assert len(events) >= 3
        assert events[0]["event"] == "buffering_start"
        assert events[-1]["event"] == "buffering_done"

    async def test_generate_with_buffer_error(self):
        """generate_with_buffer should handle errors and notify callback."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        events = []
        async def capture_event(event: dict):
            events.append(event)

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = MagicMock()
            mock_client.stream.side_effect = Exception("Stream failed")
            mock.return_value = mock_client

            result = await ollama_service.generate_with_buffer("Test", on_status=capture_event)

            assert "Error" in result
            assert any(e["event"] == "buffering_error" for e in events)


@async_mark
class TestOllamaServiceGetModelInfo:
    """Test model information retrieval."""

    async def test_get_model_info_success(self, patch_ollama_get_client):
        """get_model_info should return parsed model details."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        info = await ollama_service.get_model_info("llama3.1:latest")
        assert info["name"] == "llama3.1:latest"
        assert info["context_size"] == 8192

    async def test_get_model_info_error(self):
        """get_model_info should handle errors gracefully."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("API error")
            mock.return_value = mock_client

            info = await ollama_service.get_model_info("test-model")
            assert "error" in info


class TestOllamaServiceFormatSize:
    """Test size formatting utility."""

    def test_format_size_bytes(self):
        from app.services.ollama_service import OllamaService
        svc = OllamaService()
        assert svc._format_size(500) == "500 B"

    def test_format_size_kb(self):
        from app.services.ollama_service import OllamaService
        svc = OllamaService()
        assert "KB" in svc._format_size(2048)

    def test_format_size_mb(self):
        from app.services.ollama_service import OllamaService
        svc = OllamaService()
        assert "MB" in svc._format_size(5 * 1024 * 1024)

    def test_format_size_gb(self):
        from app.services.ollama_service import OllamaService
        svc = OllamaService()
        assert "GB" in svc._format_size(4 * 1024 * 1024 * 1024)


@async_mark
class TestOllamaServicePullModel:
    """Test model pulling."""

    async def test_pull_model_success(self, patch_ollama_get_client):
        """pull_model should return True on success."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        # Override the stream mock to return a proper response
        with patch.object(ollama_service, "_get_client", new_callable=AsyncMock) as mock:
            mock_client = MagicMock()

            class PullStreamResponse:
                def __init__(self):
                    self.status_code = 200

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def aiter_lines(self):
                    for line in [
                        '{"status": "downloading", "completed": 50}',
                        '{"status": "success"}',
                    ]:
                        yield line

            mock_client.stream.return_value = PullStreamResponse()
            mock.return_value = mock_client

            result = await ollama_service.pull_model("llama3.1:latest")
            assert result is True

    async def test_pull_model_error(self):
        """pull_model should return False on error."""
        from app.services.ollama_service import ollama_service
        ollama_service._client = None

        with patch("app.services.ollama_service.OllamaService._get_client", new_callable=AsyncMock) as mock:
            mock_client = MagicMock()
            mock_client.stream.side_effect = Exception("Pull failed")
            mock.return_value = mock_client

            result = await ollama_service.pull_model("test-model")
            assert result is False


@async_mark
class TestOllamaServiceClose:
    """Test cleanup."""

    async def test_close(self, patch_ollama_get_client):
        """close should cleanup httpx client."""
        from app.services.ollama_service import ollama_service
        mock_client = AsyncMock()
        ollama_service._client = mock_client

        await ollama_service.close()
        mock_client.aclose.assert_awaited_once()
        assert ollama_service._client is None
