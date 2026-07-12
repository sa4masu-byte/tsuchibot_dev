import time

from backend.app.infrastructure.security import SessionManager


def test_session_rejects_tampering() -> None:
    manager = SessionManager("secret", ttl_seconds=60)
    token = manager.create()
    assert manager.verify(token) is not None
    assert manager.verify(token + "tampered") is None


def test_session_rejects_expired_token(monkeypatch) -> None:
    manager = SessionManager("secret", ttl_seconds=1)
    monkeypatch.setattr(time, "time", lambda: 100)
    token = manager.create()
    monkeypatch.setattr(time, "time", lambda: 102)
    assert manager.verify(token) is None
