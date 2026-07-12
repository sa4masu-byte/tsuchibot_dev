from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_payload(
    code: str,
    message: str,
    request_id: str,
    details: object | None = None,
) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id,
        }
    }


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        code = {
            401: "AUTHENTICATION_REQUIRED",
            404: "NOT_FOUND",
            409: "CONFLICT",
            503: "SERVICE_UNAVAILABLE",
        }.get(exc.status_code, "REQUEST_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(code, str(exc.detail), request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=422,
            content=error_payload(
                "VALIDATION_ERROR",
                "Request validation failed",
                request_id,
                jsonable_encoder(exc.errors()),
            ),
        )
