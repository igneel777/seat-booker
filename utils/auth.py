from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from settings import get_auth_settings
from utils.logging import get_logger

logger = get_logger("seat_booker.auth")

# auto_error=False so a missing header gives 401 (FastAPI's default is 403).
_bearer = HTTPBearer(auto_error=False)


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


def require_role(role: Role) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Dependency factory: decode the JWT and require an exact role match."""

    async def dependency(
        request: Request,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> dict[str, Any]:
        if credentials is None:
            logger.error("missing bearer token", stack_info=True)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        settings = get_auth_settings()
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )
        except jwt.InvalidTokenError as exc:
            logger.error("invalid token", exc_info=True)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
        if payload.get("role") != role:
            logger.error(
                "role mismatch: required=%s got=%s",
                role,
                payload.get("role"),
                stack_info=True,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role '{role}'")
        sub = payload.get("sub")
        if not sub:
            logger.error("token has no subject", stack_info=True)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token has no subject")
        request.state.user_id = sub
        return payload

    return dependency


def get_user_id(request: Request) -> str:
    """User id from the token's `sub`, set by the router-level `require_role`."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        logger.error("user_id missing on request state", stack_info=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthenticated")
    return user_id
