from dataclasses import dataclass
from typing import Protocol

from backend.app.domain.catalog import ProductAnalysis


@dataclass(frozen=True, slots=True)
class ProductVisionRequest:
    source_product_id: str
    source_title: str | None
    source_category: str | None
    source_price_jpy: int | None
    image_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProductVisionResult:
    analysis: ProductAnalysis
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    raw_response: dict[str, object]
    input_tokens: int | None
    output_tokens: int | None


class VisionProvider(Protocol):
    async def analyse_product(self, request: ProductVisionRequest) -> ProductVisionResult: ...
