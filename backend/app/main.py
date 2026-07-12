from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from backend.app.api.errors import install_error_handlers
from backend.app.api.routes import router
from backend.app.application.runs import (
    InMemoryRunRepository,
    LocalWorkflowDispatcher,
    StartExplorationRun,
    WorkflowDispatcher,
)
from backend.app.infrastructure.database import PostgresRunRepository
from backend.app.infrastructure.github import GitHubActionsDispatcher
from backend.app.infrastructure.security import SessionManager
from backend.app.shared.config import get_settings
from backend.app.shared.logging import configure_logging

configure_logging(get_settings().log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("application_started", module="api", environment=settings.env)
    yield
    logger.info("application_stopped", module="api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Tsuchibot API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Idempotency-Key", "X-CSRF-Token"],
    )

    repository = (
        PostgresRunRepository(settings.database_url)
        if settings.database_url
        else InMemoryRunRepository()
    )
    dispatcher: WorkflowDispatcher
    if settings.github_repository and settings.github_token:
        dispatcher = GitHubActionsDispatcher(
            repository=settings.github_repository,
            workflow=settings.github_workflow,
            token=settings.github_token,
        )
    else:
        dispatcher = LocalWorkflowDispatcher()
    app.state.run_repository = repository
    app.state.start_exploration_run = StartExplorationRun(repository, dispatcher)
    app.state.session_manager = SessionManager(
        settings.session_secret,
        settings.session_ttl_seconds,
    )

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs", status_code=307)

    @app.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        with structlog.contextvars.bound_contextvars(request_id=request_id):
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
