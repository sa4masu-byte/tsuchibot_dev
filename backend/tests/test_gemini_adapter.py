import json
from pathlib import Path

import httpx
import pytest
from backend.app.application.vision import ProductVisionRequest
from backend.app.infrastructure.vision import GeminiVisionAdapter, VisionProviderError

FIXTURES = Path(__file__).parent / "fixtures" / "ai"
PROMPT = Path(__file__).parents[2] / "prompts" / "product_analysis" / "v1.md"


@pytest.mark.asyncio
async def test_gemini_adapter_validates_structured_output_and_usage() -> None:
    analysis = json.loads((FIXTURES / "product_analysis_valid.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})
        assert request.headers["x-goog-api-key"] == "secret"
        assert b"expected_profit_jpy" not in request.content
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}],
                "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 80},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GeminiVisionAdapter("secret", "gemini-test", PROMPT, client)
        result = await adapter.analyse_product(
            ProductVisionRequest("id", "Puzzle", "toy", 100, ("https://example.com/image.jpg",))
        )
    assert result.analysis.category.value == "jigsaw_puzzle"
    assert result.input_tokens == 120
    assert result.output_tokens == 80


@pytest.mark.asyncio
async def test_gemini_adapter_rejects_invalid_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=b"image", headers={"content-type": "image/jpeg"})
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GeminiVisionAdapter("secret", "gemini-test", PROMPT, client)
        with pytest.raises(VisionProviderError):
            await adapter.analyse_product(
                ProductVisionRequest("id", None, None, None, ("https://example.com/image.jpg",))
            )
