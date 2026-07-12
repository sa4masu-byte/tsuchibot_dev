from uuid import uuid4

import pytest
from backend.app.application.runs import (
    InMemoryRunRepository,
    LocalWorkflowDispatcher,
    RunConflictError,
    StartExplorationRun,
)
from backend.app.domain.runs import ExplorationRun, RunMode, RunStatus
from fastapi.testclient import TestClient


def test_retry_requires_target() -> None:
    with pytest.raises(ValueError, match="target_run_id"):
        ExplorationRun.pending(RunMode.RETRY_FAILED, "tester")


def test_run_state_transition_is_immutable() -> None:
    pending = ExplorationRun.pending(RunMode.INCREMENTAL, "tester")
    running = pending.start()
    assert pending.status is RunStatus.PENDING
    assert running.status is RunStatus.RUNNING
    assert running.started_at is not None


@pytest.mark.asyncio
async def test_active_run_conflicts() -> None:
    repository = InMemoryRunRepository()
    use_case = StartExplorationRun(repository, LocalWorkflowDispatcher())
    await use_case.execute(RunMode.INCREMENTAL, "tester")
    with pytest.raises(RunConflictError):
        await use_case.execute(RunMode.FULL, "tester")


def test_dispatch_api_validates_and_prevents_overlap(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"password": "correct-horse"})

    invalid = client.post("/api/v1/runs/dispatch", json={"mode": "retry_failed"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    response = client.post("/api/v1/runs/dispatch", json={"mode": "incremental"})
    assert response.status_code == 200
    assert response.json()["run"]["status"] == "pending"

    conflict = client.post("/api/v1/runs/dispatch", json={"mode": "full"})
    assert conflict.status_code == 409


def test_retry_dispatch_accepts_target(client: TestClient) -> None:
    client.post("/api/v1/auth/login", json={"password": "correct-horse"})
    response = client.post(
        "/api/v1/runs/dispatch",
        json={"mode": "retry_failed", "target_run_id": str(uuid4())},
    )
    assert response.status_code == 200
