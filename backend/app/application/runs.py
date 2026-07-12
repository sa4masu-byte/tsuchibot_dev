from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from backend.app.domain.runs import ExplorationRun, RunMode, RunStatus


class RunConflictError(RuntimeError):
    pass


class WorkflowDispatchError(RuntimeError):
    pass


class RunRepository(Protocol):
    async def add(self, run: ExplorationRun) -> None: ...

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

    async def add(self, run: ExplorationRun) -> None:
        self._runs[run.id] = run

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
    ) -> tuple[ExplorationRun, DispatchResult]:
        if await self.repository.has_active_run():
            raise RunConflictError("an exploration run is already active")
        run = ExplorationRun.pending(mode, requested_by, target_run_id)
        await self.repository.add(run)
        try:
            dispatch = await self.dispatcher.dispatch(run)
        except Exception as exc:
            await self.repository.update(run.fail("dispatch_failed"))
            raise WorkflowDispatchError("workflow dispatch was rejected") from exc
        return run, dispatch
