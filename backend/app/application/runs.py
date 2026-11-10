import hashlib
import json
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.app.domain.runs import ExplorationRun, RunMode, RunStatus


class RunConflictError(RuntimeError):
    pass


class WorkflowDispatchError(RuntimeError):
    pass


class RunRepository(Protocol):
    async def add(
        self,
        run: ExplorationRun,
        idempotency_key: str | None = None,
        payload_hash: str | None = None,
    ) -> None: ...

    async def get_dispatch_request(self, key: str) -> tuple[ExplorationRun, str] | None: ...

    async def get(self, run_id: UUID) -> ExplorationRun | None: ...

    async def list(self, limit: int = 50) -> list[ExplorationRun]: ...

    async def has_active_run(self) -> bool: ...

    async def update(self, run: ExplorationRun) -> None: ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    accepted: bool
    external_run_id: str | None = None


class WorkflowDispatcher(Protocol):
    async def dispatch(self, run: ExplorationRun) -> DispatchResult: ...


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: dict[UUID, ExplorationRun] = {}
        self._dispatch_requests: dict[str, tuple[UUID, str]] = {}

    async def add(
        self,
        run: ExplorationRun,
        idempotency_key: str | None = None,
        payload_hash: str | None = None,
    ) -> None:
        if idempotency_key is not None:
            if payload_hash is None:
                raise ValueError("payload hash is required with an idempotency key")
            if idempotency_key in self._dispatch_requests:
                raise RunConflictError("idempotency key was already used")
            self._dispatch_requests[idempotency_key] = (run.id, payload_hash)
        self._runs[run.id] = run

    async def get_dispatch_request(self, key: str) -> tuple[ExplorationRun, str] | None:
        entry = self._dispatch_requests.get(key)
        if entry is None:
            return None
        run_id, payload_hash = entry
        return self._runs[run_id], payload_hash

    async def get(self, run_id: UUID) -> ExplorationRun | None:
        return self._runs.get(run_id)

    async def list(self, limit: int = 50) -> list[ExplorationRun]:
        return sorted(self._runs.values(), key=lambda run: run.created_at, reverse=True)[:limit]

    async def has_active_run(self) -> bool:
        active_statuses = {RunStatus.PENDING, RunStatus.RUNNING}
        return any(run.status in active_statuses for run in self._runs.values())

    async def update(self, run: ExplorationRun) -> None:
        if run.id not in self._runs:
            raise KeyError(run.id)
        self._runs[run.id] = run


class LocalWorkflowDispatcher:
    """Safe development dispatcher; it records intent without external side effects."""

    async def dispatch(self, run: ExplorationRun) -> DispatchResult:
        return DispatchResult(accepted=True, external_run_id=f"local-{run.id}")


class StartExplorationRun:
    def __init__(self, repository: RunRepository, dispatcher: WorkflowDispatcher) -> None:
        self.repository = repository
        self.dispatcher = dispatcher

    async def execute(
        self,
        mode: RunMode,
        requested_by: str,
        target_run_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[ExplorationRun, DispatchResult]:
        payload_hash = None
        if idempotency_key is not None:
            payload_hash = hashlib.sha256(
                json.dumps(
                    {
                        "mode": mode.value,
                        "requested_by": requested_by,
                        "target_run_id": str(target_run_id) if target_run_id else None,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            previous = await self.repository.get_dispatch_request(idempotency_key)
            if previous is not None:
                previous_run, previous_hash = previous
                if previous_hash != payload_hash:
                    raise RunConflictError("idempotency key was already used for a different run")
                if previous_run.current_stage == "dispatch_failed":
                    raise WorkflowDispatchError("workflow dispatch was rejected")
                return previous_run, DispatchResult(accepted=True)
        if await self.repository.has_active_run():
            raise RunConflictError("an exploration run is already active")
        run = ExplorationRun.pending(mode, requested_by, target_run_id)
        await self.repository.add(run, idempotency_key, payload_hash)
        try:
            dispatch = await self.dispatcher.dispatch(run)
        except Exception as exc:
            await self.repository.update(run.fail("dispatch_failed"))
            raise WorkflowDispatchError("workflow dispatch was rejected") from exc
        return run, dispatch
