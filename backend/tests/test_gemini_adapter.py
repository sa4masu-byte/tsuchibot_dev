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


def test_image_type_detection_supports_generic_cdn_content_type() -> None:
    assert GeminiVisionAdapter._detected_image_type(b"\xff\xd8\xffdata") == "image/jpeg"
    assert GeminiVisionAdapter._detected_image_type(b"\x89PNG\r\n\x1a\ndata") == "image/png"
    assert GeminiVisionAdapter._detected_image_type(b"RIFF1234WEBPdata") == "image/webp"
    assert GeminiVisionAdapter._detected_image_type(b"unknown") is None


@pytest.mark.asyncio
async def test_gemini_adapter_retries_transient_provider_failure() -> None:
    analysis = json.loads((FIXTURES / "product_analysis_valid.json").read_text())
    post_calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_calls
        if request.method == "GET":
            return httpx.Response(
                200,
                content=b"\xff\xd8\xffdata",
                headers={"content-type": "application/octet-stream"},
            )
        post_calls += 1
        if post_calls == 1:
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(analysis)}]}}]},
        )

    async def record_delay(delay: float) -> None:
        delays.append(delay)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = GeminiVisionAdapter(
            "secret",
            "gemini-test",
            PROMPT,
            client,
            max_retries=1,
            sleep=record_delay,
        )
        await adapter.analyse_product(
            ProductVisionRequest("id", None, None, None, ("https://example.com/image.jpg",))
        )
    assert post_calls == 2
    assert delays == [1]
