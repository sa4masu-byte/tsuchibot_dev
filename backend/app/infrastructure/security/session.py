import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionIdentity:
    subject: str
    expires_at: int


class SessionManager:
    """Small signed-cookie implementation with expiry and constant-time verification."""

    def __init__(self, secret: str, ttl_seconds: int) -> None:
        self._key = secret.encode()
        self._ttl_seconds = ttl_seconds

    def password_matches(self, supplied: str, expected: str) -> bool:
        return hmac.compare_digest(supplied.encode(), expected.encode())

    def create(self, subject: str = "shared-user") -> str:
        payload = json.dumps(
            {"sub": subject, "exp": int(time.time()) + self._ttl_seconds},
            separators=(",", ":"),
        ).encode()
        encoded = self._encode(payload)
        signature = self._sign(encoded)
        return f"{encoded}.{signature}"

    def verify(self, token: str | None) -> SessionIdentity | None:
        if not token:
            return None
        try:
            encoded, supplied_signature = token.split(".", maxsplit=1)
            if not hmac.compare_digest(supplied_signature, self._sign(encoded)):
                return None
            raw = self._decode(encoded)
            data = json.loads(raw)
            subject = data["sub"]
            expires_at = data["exp"]
            if not isinstance(subject, str) or not isinstance(expires_at, int):
                return None
            if expires_at <= int(time.time()):
                return None
            return SessionIdentity(subject=subject, expires_at=expires_at)
        except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _sign(self, payload: str) -> str:
        digest = hmac.new(self._key, payload.encode(), hashlib.sha256).digest()
        return self._encode(digest)

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _decode(value: str) -> str:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding).decode()
