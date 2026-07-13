from pathlib import Path

import pytest
from backend.app.domain.research import ListingStatus, SearchQuery, SearchStage
from backend.app.infrastructure.sources import load_manual_research_document
from pydantic import ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "mercari" / "manual_research.json"


async def test_manual_document_normalizes_fixture_and_filters_by_stage() -> None:
    target, adapter = load_manual_research_document(FIXTURE)
    query = SearchQuery(1, "HAC-001", SearchStage.EXACT_MODEL, "hac-001")

    result = await adapter.search(query, sold_limit=50, active_limit=50)

    assert target.model_numbers == ("HAC-001",)
    assert len(result.listings) == 1
    assert result.listings[0].status is ListingStatus.SOLD
    assert result.parser_version == "mercari-manual-v1"
    assert result.raw_result_ref is not None
    assert str(FIXTURE) not in result.raw_result_ref


def test_manual_document_rejects_unexpected_fields(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        '{"schema_version":"mercari-manual-v1","target":'
        '{"source_title":"x","unexpected":true},"listings":[]}'
    )

    with pytest.raises(ValidationError):
        load_manual_research_document(invalid)
