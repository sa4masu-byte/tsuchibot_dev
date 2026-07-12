from typing import Annotated, cast

from fastapi import Cookie, Depends, HTTPException, Request, status

from backend.app.infrastructure.security import SessionManager
from backend.app.infrastructure.security.session import SessionIdentity

SESSION_COOKIE = "tsuchibot_session"


def get_session_manager(request: Request) -> SessionManager:
    return cast(SessionManager, request.app.state.session_manager)


def require_session(
    manager: Annotated[SessionManager, Depends(get_session_manager)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> SessionIdentity:
    identity = manager.verify(token)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return identity


CurrentSession = Annotated[SessionIdentity, Depends(require_session)]
