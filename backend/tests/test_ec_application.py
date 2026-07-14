from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from backend.app.application.ec import (
    ConductECExploration,
    ECExplorationRecord,
    ECExplorationRequest,
)
from backend.app.domain.ec import SOURCE_ORDER, ECEligibility
from backend.app.infrastructure.sources import load_manual_ec_document

FIXTURE = Path(__file__).parent / "fixtures" / "ec" / "manual_exploration.json"


class MemoryECRepository:
    def __init__(self) -> None:
        self.records: list[ECExplorationRecord] = []

    async def save(self, record: ECExplorationRecord) -> None:
        self.records.append(record)


@pytest.mark.asyncio
async def test_manual_fallback_runs_all_sources_in_required_order() -> None:
    document, providers = load_manual_ec_document(FIXTURE)
    repository = MemoryECRepository()
    record = await ConductECExploration(providers, repository).execute(
        ECExplorationRequest(
            run_id=uuid4(),
            observed_at=datetime.now(UTC),
            useful_jimoty_candidates=document.useful_jimoty_candidates,
            profit_pattern_keywords=tuple(document.profit_pattern_keywords),
            mercari_demand_keywords=tuple(document.mercari_demand_keywords),
            sale_discount_keywords=tuple(document.sale_discount_keywords),
        )
    )
    assert tuple(item.source for item in record.collections) == SOURCE_ORDER
    assert record.trigger_reason == "insufficient_jimoty_candidates"
    assert record.status == "completed"
    assert len(record.keywords) == 4
    assert len(record.evaluations) == 4
    assert sum(
        item.eligibility is ECEligibility.ELIGIBLE for item in record.evaluations
    ) == 3
    rejected = next(
        item for item in record.evaluations if item.eligibility is ECEligibility.REJECTED
    )
    assert rejected.offer.source.value == "shein"
    assert repository.records == [record]


@pytest.mark.asyncio
async def test_sufficient_jimoty_candidates_skip_alternative_sources() -> None:
    _, providers = load_manual_ec_document(FIXTURE)
    repository = MemoryECRepository()
    record = await ConductECExploration(providers, repository).execute(
        ECExplorationRequest(
            run_id=uuid4(),
            observed_at=datetime.now(UTC),
            useful_jimoty_candidates=3,
        )
    )
    assert record.status == "not_required"
    assert record.collections == ()


def test_manual_document_rejects_unknown_fields(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        '{"schema_version":"ec-manual-v1","offers":[],"invented":true}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_manual_ec_document(bad)
