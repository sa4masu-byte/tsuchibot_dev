from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Condition(StrEnum):
    NEW_LIKE = "new_like"
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"


class SizeClass(StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    OVERSIZED = "oversized"
    UNKNOWN = "unknown"


class ApparentRecency(StrEnum):
    RECENT = "recent"
    OLDER = "older"
    UNKNOWN = "unknown"


class TextField(StrictModel):
    value: str | None
    confidence: float = Field(ge=0, le=1)


class BooleanField(StrictModel):
    value: bool | None
    confidence: float = Field(ge=0, le=1)


class ConditionField(StrictModel):
    value: Condition
    confidence: float = Field(ge=0, le=1)


class SizeField(StrictModel):
    value: SizeClass
    confidence: float = Field(ge=0, le=1)


class RecencyField(StrictModel):
    value: ApparentRecency
    confidence: float = Field(ge=0, le=1)


class ModelNumberCandidate(StrictModel):
    value: str
    confidence: float = Field(ge=0, le=1)
    evidence: str


class VisibleText(StrictModel):
    text: str
    location_hint: str | None = None


class ConditionObservation(StrictModel):
    code: str
    severity: float = Field(ge=0, le=1)
    evidence: str


class OriginalPriceBand(StrictModel):
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered(self) -> "OriginalPriceBand":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("original price minimum cannot exceed maximum")
        return self


class ProductAnalysis(StrictModel):
    schema_version: str = Field(pattern=r"^product-analysis-v1$")
    category: TextField
    manufacturer: TextField
    brand: TextField
    model_number_candidates: list[ModelNumberCandidate]
    visible_text: list[VisibleText]
    character: TextField
    is_new: BooleanField
    condition: ConditionField
    condition_observations: list[ConditionObservation]
    dirt_severity: float = Field(ge=0, le=1)
    size_class: SizeField
    apparent_recency: RecencyField
    original_price_band_jpy: OriginalPriceBand
    search_terms: list[str] = Field(max_length=10)
    uncertainties: list[str]
