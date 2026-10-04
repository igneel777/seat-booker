from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from settings import get_auth_settings

# auto_error=False so a missing header gives 401 (FastAPI's default is 403).
_bearer = HTTPBearer(auto_error=False)


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


def require_role(role: Role) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Dependency factory: decode the JWT and require an exact role match."""

    async def dependency(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> dict[str, Any]:
        if credentials is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
        settings = get_auth_settings()
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret.get_secret_value(),
                algorithms=[settings.jwt_algorithm],
            )
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from exc
        if payload.get("role") != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role '{role}'")
        return payload

    return dependency
