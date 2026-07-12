from collections.abc import Iterator

import pytest
from backend.app.main import create_app
from backend.app.shared.config import get_settings
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TSUCHIBOT_ENV", "test")
    monkeypatch.setenv("TSUCHIBOT_SHARED_PASSWORD", "correct-horse")
    monkeypatch.setenv("TSUCHIBOT_SESSION_SECRET", "a-test-session-secret-that-is-long-enough")
    monkeypatch.setenv("TSUCHIBOT_SESSION_SECURE", "false")
    monkeypatch.setenv("TSUCHIBOT_DATABASE_URL", "")
    monkeypatch.setenv("TSUCHIBOT_GITHUB_REPOSITORY", "")
    monkeypatch.setenv("TSUCHIBOT_GITHUB_TOKEN", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
