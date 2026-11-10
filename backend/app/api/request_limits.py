from uuid import uuid4

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.api.errors import error_payload


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, maximum_bytes: int) -> None:
        self.app = app
        self.maximum_bytes = maximum_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in {"POST", "PUT", "PATCH"}
            or not scope["path"].startswith("/api/v1/")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.maximum_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        chunks: list[bytes] = []
        received_bytes = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self.maximum_bytes:
                    await self._reject(scope, receive, send)
                    return
                chunks.append(body)
                if not message.get("more_body", False):
                    break

        delivered = False

        async def replay_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay_receive, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        request_id = str(uuid4())
        response = JSONResponse(
            status_code=413,
            content=error_payload("REQUEST_TOO_LARGE", "Request body is too large", request_id),
            headers={"X-Request-ID": request_id},
        )
        await response(scope, receive, send)
