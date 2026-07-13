from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from backend.app.application.recommendation import (
    CalculateRecommendation,
    RecommendationRecord,
    RecommendationRequest,
)
from backend.app.infrastructure.database.postgres_recommendation import (
    RecommendationCandidate,
)


class RecommendationCandidateProvider(Protocol):
    async def get(
        self,
        source_product_id: UUID,
        run_id: UUID,
        research_session_id: UUID | None = None,
    ) -> RecommendationCandidate | None: ...


class RecalculateReviewedProduct:
    def __init__(
        self,
        candidates: RecommendationCandidateProvider,
        calculator: CalculateRecommendation,
    ) -> None:
        self._candidates = candidates
        self._calculator = calculator

    async def execute(self, context: dict[str, UUID]) -> RecommendationRecord:
        candidate = await self._candidates.get(
            context["source_product_id"],
            context["run_id"],
            context["research_session_id"],
        )
        if candidate is None:
            raise LookupError("Recommendation inputs were not found")
        return await self._calculator.execute(
            RecommendationRequest(
                canonical_product_id=candidate.canonical_product_id,
                source_product_id=candidate.source_product_id,
                research_session_id=candidate.research_session_id,
                run_id=candidate.run_id,
                inputs=candidate.inputs,
                policy=candidate.policy,
                calculated_at=datetime.now(UTC),
            )
        )
