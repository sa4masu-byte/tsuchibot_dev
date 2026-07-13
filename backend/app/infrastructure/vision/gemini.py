import base64
import json
from pathlib import Path

import httpx
from pydantic import ValidationError

from backend.app.application.vision import (
    ProductVisionRequest,
    ProductVisionResult,
)
from backend.app.domain.catalog import ProductAnalysis


class VisionProviderError(RuntimeError):
    pass


class GeminiVisionAdapter:
    provider = "gemini"
    prompt_version = "product-analysis-v1"
    schema_version = "product-analysis-v1"

    def __init__(
        self,
        api_key: str,
        model: str,
        prompt_path: Path,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60,
        max_images: int = 5,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._prompt = prompt_path.read_text()
        self._client = client
        self._timeout = timeout_seconds
        self._max_images = max_images

    async def analyse_product(self, request: ProductVisionRequest) -> ProductVisionResult:
        parts: list[dict[str, object]] = [
            {"text": self._context_prompt(request)},
        ]
        for image_url in request.image_urls[: self._max_images]:
            parts.append(await self._image_part(image_url))
        if len(parts) == 1:
            raise VisionProviderError("product analysis requires at least one image")

        payload: dict[str, object] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": ProductAnalysis.model_json_schema(),
                "temperature": 0,
            },
        }
        response = await self._post(payload)
        raw = response.json()
        try:
            text = raw["candidates"][0]["content"]["parts"][0]["text"]
            analysis = ProductAnalysis.model_validate_json(text)
        except (KeyError, IndexError, TypeError, ValidationError, json.JSONDecodeError) as exc:
            raise VisionProviderError(
                "Gemini returned invalid structured product analysis"
            ) from exc
        usage = raw.get("usageMetadata", {})
        return ProductVisionResult(
            analysis=analysis,
            provider=self.provider,
            model=self._model,
            prompt_version=self.prompt_version,
            schema_version=self.schema_version,
            raw_response=raw,
            input_tokens=self._integer(usage.get("promptTokenCount")),
            output_tokens=self._integer(usage.get("candidatesTokenCount")),
        )

    def _context_prompt(self, request: ProductVisionRequest) -> str:
        context = json.dumps(
            {
                "source_title": request.source_title,
                "source_category": request.source_category,
                "source_price_jpy": request.source_price_jpy,
            },
            ensure_ascii=False,
        )
        return f"{self._prompt}\n\nSource context:\n{context}"

    async def _image_part(self, image_url: str) -> dict[str, object]:
        response = await self._get(image_url)
        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise VisionProviderError(f"unsupported image type: {content_type or 'unknown'}")
        if len(response.content) > 8 * 1024 * 1024:
            raise VisionProviderError("image exceeds the 8MB per-image limit")
        return {
            "inlineData": {
                "mimeType": content_type,
                "data": base64.b64encode(response.content).decode(),
            }
        }

    async def _get(self, url: str) -> httpx.Response:
        if self._client is not None:
            response = await self._client.get(url, timeout=self._timeout, follow_redirects=True)
        else:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=self._timeout, follow_redirects=True)
        response.raise_for_status()
        return response

    async def _post(self, payload: dict[str, object]) -> httpx.Response:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent"
        )
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        if self._client is not None:
            response = await self._client.post(
                url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
        response.raise_for_status()
        return response

    @staticmethod
    def _integer(value: object) -> int | None:
        return value if isinstance(value, int) else None
