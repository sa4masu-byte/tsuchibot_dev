from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.domain.runs import ExplorationRun, RunMode, RunStatus


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class SessionResponse(BaseModel):
    authenticated: bool
    expires_at: int | None = None


class RunDispatchRequest(BaseModel):
    mode: RunMode = RunMode.INCREMENTAL
    target_run_id: UUID | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "RunDispatchRequest":
        if self.mode is RunMode.RETRY_FAILED and self.target_run_id is None:
            raise ValueError("target_run_id is required for retry_failed mode")
        if self.mode is not RunMode.RETRY_FAILED and self.target_run_id is not None:
            raise ValueError("target_run_id is only valid for retry_failed mode")
        return self


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mode: RunMode
    trigger_source: str
    requested_by: str
    status: RunStatus
    current_stage: str
    progress_numerator: int
    progress_denominator: int
    target_run_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_domain(cls, run: ExplorationRun) -> "RunResponse":
        return cls.model_validate(run)


class DispatchResponse(BaseModel):
    run: RunResponse
    dispatch_accepted: bool
    external_run_id: str | None


class HealthResponse(BaseModel):
    status: str
    service: str


CorrectionField = Literal[
    "display_name",
    "category",
    "manufacturer",
    "brand",
    "model_number",
    "character_name",
    "size_text",
    "color",
    "condition",
    "is_new",
    "estimated_shipping_jpy",
    "estimated_sale_price_jpy",
]


class ProductCorrectionRequest(BaseModel):
    field_name: CorrectionField
    corrected_value: object
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_value(self) -> "ProductCorrectionRequest":
        if self.field_name in {"estimated_shipping_jpy", "estimated_sale_price_jpy"}:
            if (
                not isinstance(self.corrected_value, int)
                or isinstance(self.corrected_value, bool)
                or self.corrected_value < 0
            ):
                raise ValueError("money corrections must be non-negative integer yen")
        elif self.field_name == "is_new":
            if not isinstance(self.corrected_value, bool):
                raise ValueError("is_new must be boolean")
        elif not isinstance(self.corrected_value, str) or not self.corrected_value.strip():
            raise ValueError("text corrections cannot be empty")
        return self


class ComparableDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PurchaseRequest(BaseModel):
    purchased: bool = True
    purchased_at: datetime
    quantity: int | None = Field(default=None, ge=1, le=4)
    product_amount_jpy: int | None = Field(default=None, ge=0)
    sourcing_shipping_jpy: int | None = Field(default=None, ge=0)
    coupon_jpy: int | None = Field(default=None, ge=0)
    point_reference_jpy: int = Field(default=0, ge=0)
    actual_charged_amount_jpy: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_purchase_values(self) -> "PurchaseRequest":
        required = (
            self.quantity,
            self.product_amount_jpy,
            self.sourcing_shipping_jpy,
            self.coupon_jpy,
            self.actual_charged_amount_jpy,
        )
        if self.purchased and any(value is None for value in required):
            raise ValueError("purchase amounts and quantity are required when purchased")
        if not self.purchased and any(value is not None for value in required):
            raise ValueError("purchase amounts must be omitted when not purchased")
        return self


class ListingRequest(BaseModel):
    listed_at: datetime
    marketplace: str = Field(min_length=1, max_length=100)
    listing_price_jpy: int = Field(ge=0)
    quantity: int = Field(ge=1, le=4)
    listing_url: str | None = Field(default=None, max_length=2000)


class SaleRequest(BaseModel):
    sold_at: datetime
    sold_price_jpy: int = Field(ge=0)
    actual_fee_jpy: int = Field(ge=0)
    actual_shipping_jpy: int = Field(ge=0)
    quantity: int = Field(ge=1, le=4)


NegativeOutcome = Literal["returned", "cancelled", "unsold_90_days", "damaged", "lost", "other"]


class NegativeOutcomeRequest(BaseModel):
    outcome_type: NegativeOutcome
    quantity: int = Field(ge=1, le=4)
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=1000)


class PreferenceFeedbackRequest(BaseModel):
    signal: Literal["want", "slightly_interested", "do_not_want", "cannot_judge"]
    note: str | None = Field(default=None, max_length=500)


class ResearchValueFeedbackRequest(BaseModel):
    signal: Literal["worth_researching", "not_worth_researching"]
    note: str | None = Field(default=None, max_length=500)


class HypothesisEvidenceRequest(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=100)
    direction: Literal["supporting", "contradictory", "neutral"]
    strength: Decimal = Field(ge=0, le=1)
    source_reference_type: str = Field(min_length=1, max_length=100)
    source_reference_id: UUID | None = None
    summary: str = Field(min_length=1, max_length=1000)
