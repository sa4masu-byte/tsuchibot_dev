from uuid import uuid4

import httpx
import pytest
from backend.app.domain.runs import ExplorationRun, RunMode
from backend.app.infrastructure.github import GitHubActionsDispatcher


@pytest.mark.asyncio
async def test_github_dispatcher_keeps_token_server_side() -> None:
    captured: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured
        captured = request
        return httpx.Response(204)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        dispatcher = GitHubActionsDispatcher("owner/repository", "explore.yml", "secret", client)
        run = ExplorationRun.pending(RunMode.RETRY_FAILED, "tester", uuid4())
        result = await dispatcher.dispatch(run)

    assert result.accepted is True
    assert captured is not None
    assert captured.headers["Authorization"] == "Bearer secret"
    assert b"secret" not in captured.content
    assert b"retry_failed" in captured.content
