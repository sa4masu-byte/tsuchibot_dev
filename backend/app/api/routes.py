from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.api.dependencies import (
    SESSION_COOKIE,
    CurrentSession,
    get_session_manager,
)
from backend.app.api.schemas import (
    DispatchResponse,
    HealthResponse,
    LoginRequest,
    RunDispatchRequest,
    RunResponse,
    SessionResponse,
)
from backend.app.application.runs import RunConflictError, StartExplorationRun
from backend.app.infrastructure.security import SessionManager
from backend.app.shared.config import Settings, get_settings

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="tsuchibot-api")


@router.post("/auth/login", response_model=SessionResponse, tags=["authentication"])
async def login(
    body: LoginRequest,
    response: Response,
    manager: Annotated[SessionManager, Depends(get_session_manager)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionResponse:
    if not manager.password_matches(body.password, settings.shared_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    token = manager.create()
    identity = manager.verify(token)
    assert identity is not None
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_secure,
        samesite="lax",
        path="/",
    )
    return SessionResponse(authenticated=True, expires_at=identity.expires_at)


@router.post("/auth/logout", status_code=204, tags=["authentication"])
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/auth/session", response_model=SessionResponse, tags=["authentication"])
async def session(identity: CurrentSession) -> SessionResponse:
    return SessionResponse(authenticated=True, expires_at=identity.expires_at)


@router.post("/runs/dispatch", response_model=DispatchResponse, tags=["runs"])
async def dispatch_run(
    body: RunDispatchRequest,
    request: Request,
    identity: CurrentSession,
) -> DispatchResponse:
    use_case: StartExplorationRun = request.app.state.start_exploration_run
    try:
        run, dispatch = await use_case.execute(body.mode, identity.subject, body.target_run_id)
    except RunConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DispatchResponse(
        run=RunResponse.from_domain(run),
        dispatch_accepted=dispatch.accepted,
        external_run_id=dispatch.external_run_id,
    )


@router.get("/runs", response_model=list[RunResponse], tags=["runs"])
async def list_runs(request: Request, _: CurrentSession) -> list[RunResponse]:
    runs = await request.app.state.run_repository.list()
    return [RunResponse.from_domain(run) for run in runs]


@router.get("/runs/{run_id}", response_model=RunResponse, tags=["runs"])
async def get_run(run_id: UUID, request: Request, _: CurrentSession) -> RunResponse:
    run = await request.app.state.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run was not found")
    return RunResponse.from_domain(run)
