from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status

from backend.app.api.dependencies import (
    SESSION_COOKIE,
    CurrentSession,
    get_session_manager,
)
from backend.app.api.schemas import (
    ComparableDecisionRequest,
    DispatchResponse,
    HealthResponse,
    LoginRequest,
    ProductCorrectionRequest,
    RunDispatchRequest,
    RunResponse,
    SessionResponse,
)
from backend.app.application.runs import (
    RunConflictError,
    StartExplorationRun,
    WorkflowDispatchError,
)
from backend.app.infrastructure.security import SessionManager
from backend.app.shared.config import Settings, get_settings

router = APIRouter(prefix="/api/v1")


def require_same_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.cors_origin_list:
        raise HTTPException(status_code=403, detail="Origin is not allowed")


def review_repository(request: Request) -> Any:
    repository = getattr(request.app.state, "review_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Review database is not configured")
    return repository


async def recalculate_and_read(
    request: Request,
    repository: Any,
    product_id: UUID,
    context: dict[str, UUID],
) -> dict[str, Any]:
    recalculate = getattr(request.app.state, "recalculate_reviewed_product", None)
    if recalculate is None:
        raise HTTPException(status_code=503, detail="Recommendation engine is not configured")
    try:
        await recalculate.execute(context)
    except LookupError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    detail = cast(dict[str, Any] | None, await repository.product_detail(product_id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Product was not found")
    return detail


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
    except WorkflowDispatchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


@router.get("/dashboard", response_model=dict[str, Any], tags=["review"])
async def dashboard(request: Request, _: CurrentSession) -> dict[str, Any]:
    return cast(dict[str, Any], await review_repository(request).dashboard())


@router.get("/products", response_model=list[dict[str, Any]], tags=["review"])
async def list_products(
    request: Request,
    _: CurrentSession,
    tier: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    sort: str = "overall_sourcing_score",
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        await review_repository(request).list_products(
            tier=tier,
            search=search,
            sort=sort,
            limit=limit,
        ),
    )


@router.get("/products/{product_id}", response_model=dict[str, Any], tags=["review"])
async def product_detail(
    product_id: UUID, request: Request, _: CurrentSession
) -> dict[str, Any]:
    detail = cast(
        dict[str, Any] | None,
        await review_repository(request).product_detail(product_id),
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Product was not found")
    return detail


@router.post(
    "/products/{product_id}/corrections",
    response_model=dict[str, Any],
    tags=["review"],
)
async def correct_product(
    product_id: UUID,
    body: ProductCorrectionRequest,
    request: Request,
    identity: CurrentSession,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> dict[str, Any]:
    require_same_origin(request, settings)
    repository = review_repository(request)
    try:
        context = await repository.create_correction(
            product_id,
            body.field_name,
            body.corrected_value,
            body.reason,
            identity.subject,
            idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Product was not found") from exc
    return await recalculate_and_read(request, repository, product_id, context)


async def change_comparable_decision(
    product_id: UUID,
    comparable_id: UUID,
    body: ComparableDecisionRequest,
    request: Request,
    identity: Any,
    settings: Settings,
    idempotency_key: str,
    *,
    exclude: bool,
) -> dict[str, Any]:
    require_same_origin(request, settings)
    repository = review_repository(request)
    try:
        context = await repository.set_comparable_decision(
            product_id,
            comparable_id,
            exclude=exclude,
            actor=identity.subject,
            reason=body.reason,
            idempotency_key=idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Comparable was not found") from exc
    return await recalculate_and_read(request, repository, product_id, context)


@router.post(
    "/products/{product_id}/comparables/{comparable_id}/exclude",
    response_model=dict[str, Any],
    tags=["review"],
)
async def exclude_comparable(
    product_id: UUID,
    comparable_id: UUID,
    body: ComparableDecisionRequest,
    request: Request,
    identity: CurrentSession,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> dict[str, Any]:
    return await change_comparable_decision(
        product_id,
        comparable_id,
        body,
        request,
        identity,
        settings,
        idempotency_key,
        exclude=True,
    )


@router.post(
    "/products/{product_id}/comparables/{comparable_id}/restore",
    response_model=dict[str, Any],
    tags=["review"],
)
async def restore_comparable(
    product_id: UUID,
    comparable_id: UUID,
    body: ComparableDecisionRequest,
    request: Request,
    identity: CurrentSession,
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=8, max_length=128)
    ],
) -> dict[str, Any]:
    return await change_comparable_decision(
        product_id,
        comparable_id,
        body,
        request,
        identity,
        settings,
        idempotency_key,
        exclude=False,
    )
