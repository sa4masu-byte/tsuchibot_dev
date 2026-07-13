from dataclasses import dataclass
from typing import Protocol

from backend.app.domain.research.identification import (
    ModelIdentityCandidate,
    VisualSearchHit,
    extract_visual_model_candidates,
    merge_model_candidates,
    needs_visual_search,
)


class VisualIdentityProvider(Protocol):
    provider_name: str

    async def identify(self, image_url: str) -> tuple[VisualSearchHit, ...]: ...


@dataclass(frozen=True, slots=True)
class ModelIdentificationResult:
    candidates: tuple[ModelIdentityCandidate, ...]
    visual_hits: tuple[VisualSearchHit, ...]
    visual_search_used: bool
    provider: str | None
    status: str
    error_category: str | None = None
    error_message: str | None = None


class ResolveModelIdentity:
    def __init__(
        self,
        visual_provider: VisualIdentityProvider,
        threshold: float = 0.7,
    ) -> None:
        self._visual_provider = visual_provider
        self._threshold = threshold

    async def execute(
        self,
        primary_candidates: tuple[ModelIdentityCandidate, ...],
        image_urls: tuple[str, ...],
    ) -> ModelIdentificationResult:
        if not needs_visual_search(primary_candidates, self._threshold) or not image_urls:
            return ModelIdentificationResult(
                candidates=primary_candidates,
                visual_hits=(),
                visual_search_used=False,
                provider=None,
                status="skipped",
            )
        try:
            hits = await self._visual_provider.identify(image_urls[0])
        except Exception as exc:
            return ModelIdentificationResult(
                candidates=primary_candidates,
                visual_hits=(),
                visual_search_used=True,
                provider=self._visual_provider.provider_name,
                status="failed",
                error_category=type(exc).__name__,
                error_message="Visual identity provider was unavailable.",
            )
        visual_candidates = extract_visual_model_candidates(hits)
        return ModelIdentificationResult(
            candidates=merge_model_candidates(primary_candidates, visual_candidates),
            visual_hits=hits,
            visual_search_used=True,
            provider=self._visual_provider.provider_name,
            status="completed",
        )
