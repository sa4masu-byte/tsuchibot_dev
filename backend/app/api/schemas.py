from datetime import datetime
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
