from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class RunMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"
    RETRY_FAILED = "retry_failed"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL_FAILURE = "partial_failure"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            RunStatus.PARTIAL_FAILURE,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }


@dataclass(frozen=True, slots=True)
class ExplorationRun:
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
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def pending(
        cls,
        mode: RunMode,
        requested_by: str,
        target_run_id: UUID | None = None,
        trigger_source: str = "web",
    ) -> "ExplorationRun":
        if mode is RunMode.RETRY_FAILED and target_run_id is None:
            raise ValueError("target_run_id is required for retry_failed mode")
        if mode is not RunMode.RETRY_FAILED and target_run_id is not None:
            raise ValueError("target_run_id is only valid for retry_failed mode")
        return cls(
            id=uuid4(),
            mode=mode,
            trigger_source=trigger_source,
            requested_by=requested_by,
            status=RunStatus.PENDING,
            current_stage="queued",
            progress_numerator=0,
            progress_denominator=0,
            target_run_id=target_run_id,
            created_at=datetime.now(UTC),
        )

    def start(self) -> "ExplorationRun":
        if self.status is not RunStatus.PENDING:
            raise ValueError("only a pending run can start")
        return replace(
            self,
            status=RunStatus.RUNNING,
            current_stage="initializing",
            started_at=datetime.now(UTC),
        )

    def advance(self, stage: str, numerator: int, denominator: int) -> "ExplorationRun":
        if self.status is not RunStatus.RUNNING:
            raise ValueError("only a running run can advance")
        if denominator < 0 or numerator < self.progress_numerator or numerator > denominator:
            raise ValueError("run progress must be non-negative and monotonic")
        return replace(
            self,
            current_stage=stage,
            progress_numerator=numerator,
            progress_denominator=denominator,
        )

    def complete(self, *, with_errors: bool = False) -> "ExplorationRun":
        if self.status is not RunStatus.RUNNING:
            raise ValueError("only a running run can complete")
        return replace(
            self,
            status=RunStatus.PARTIAL_FAILURE if with_errors else RunStatus.COMPLETED,
            current_stage="completed",
            progress_numerator=self.progress_denominator,
            finished_at=datetime.now(UTC),
        )

    def fail(self, stage: str) -> "ExplorationRun":
        if self.status.terminal:
            raise ValueError("a terminal run cannot fail again")
        return replace(
            self,
            status=RunStatus.FAILED,
            current_stage=stage,
            finished_at=datetime.now(UTC),
        )
