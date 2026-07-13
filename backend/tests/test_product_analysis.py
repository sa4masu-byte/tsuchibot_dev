import json
from pathlib import Path

import pytest
from backend.app.domain.catalog import ProductAnalysis
from pydantic import ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "ai" / "product_analysis_valid.json"


def test_product_analysis_fixture_is_strictly_valid() -> None:
    analysis = ProductAnalysis.model_validate_json(FIXTURE.read_text())
    assert analysis.schema_version == "product-analysis-v1"
    assert analysis.character.value is None


def test_financial_decision_fields_are_rejected() -> None:
    value = json.loads(FIXTURE.read_text())
    value["expected_profit_jpy"] = 1000
    with pytest.raises(ValidationError, match="Extra inputs"):
        ProductAnalysis.model_validate(value)


def test_invalid_confidence_is_rejected() -> None:
    value = json.loads(FIXTURE.read_text())
    value["manufacturer"]["confidence"] = 1.1
    with pytest.raises(ValidationError):
        ProductAnalysis.model_validate(value)
