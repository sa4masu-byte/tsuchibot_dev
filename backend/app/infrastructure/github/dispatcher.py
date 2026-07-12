import httpx

from backend.app.application.runs import DispatchResult
from backend.app.domain.runs import ExplorationRun


class GitHubActionsDispatcher:
    """Server-only adapter for GitHub Actions workflow_dispatch."""

    def __init__(
        self,
        repository: str,
        workflow: str,
        token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if repository.count("/") != 1:
            raise ValueError("GitHub repository must use owner/name format")
        self._url = (
            f"https://api.github.com/repos/{repository}/actions/workflows/{workflow}/dispatches"
        )
        self._token = token
        self._client = client

    async def dispatch(self, run: ExplorationRun) -> DispatchResult:
        payload: dict[str, object] = {
            "ref": "main",
            "inputs": {
                "mode": run.mode.value,
                "target_run_id": str(run.target_run_id) if run.target_run_id else "",
                "public_run_id": str(run.id),
            },
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._client is not None:
            response = await self._client.post(self._url, headers=headers, json=payload)
        else:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(self._url, headers=headers, json=payload)
        response.raise_for_status()
        return DispatchResult(accepted=True)
