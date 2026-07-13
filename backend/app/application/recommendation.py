from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID, uuid4

from backend.app.domain.recommendation import (
    RecommendationInput,
    RecommendationPolicy,
    RecommendationResult,
    calculate_recommendation,
    recommendation_input_hash,
)


@dataclass(frozen=True, slots=True)
class RecommendationRequest:
    canonical_product_id: UUID
    source_product_id: UUID
    research_session_id: UUID
    run_id: UUID
    inputs: RecommendationInput
    policy: RecommendationPolicy
    calculated_at: datetime

    def __post_init__(self) -> None:
        if self.calculated_at.tzinfo is None:
            raise ValueError("calculated_at must include a timezone")


@dataclass(frozen=True, slots=True)
class RecommendationRecord:
    id: UUID
    request: RecommendationRequest
    result: RecommendationResult
    evidence_snapshot_hash: str


class RecommendationRepository(Protocol):
    async def save(self, recommendation: RecommendationRecord) -> UUID: ...


class CalculateRecommendation:
    def __init__(self, repository: RecommendationRepository) -> None:
        self._repository = repository

    async def execute(self, request: RecommendationRequest) -> RecommendationRecord:
        record = RecommendationRecord(
            id=uuid4(),
            request=request,
            result=calculate_recommendation(request.inputs, request.policy),
            evidence_snapshot_hash=recommendation_input_hash(
                request.inputs,
                request.policy,
            ),
        )
        persisted_id = await self._repository.save(record)
        if persisted_id != record.id:
            return RecommendationRecord(
                id=persisted_id,
                request=record.request,
                result=record.result,
                evidence_snapshot_hash=record.evidence_snapshot_hash,
            )
        return record


class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self.records: list[RecommendationRecord] = []

    async def save(self, recommendation: RecommendationRecord) -> UUID:
        existing = next(
            (
                item
                for item in self.records
                if item.request.source_product_id
                == recommendation.request.source_product_id
                and item.evidence_snapshot_hash == recommendation.evidence_snapshot_hash
                and item.result.policy.scoring_version
                == recommendation.result.policy.scoring_version
            ),
            None,
        )
        if existing is not None:
            return existing.id
        self.records.append(recommendation)
        return recommendation.id
