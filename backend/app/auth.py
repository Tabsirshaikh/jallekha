"""Token auth for the API (T10): bearer tokens per role, a local dev token, a gateway credential.

Errors use the shared error shape: 401 `unauthorized` without a valid credential, 403 `forbidden`
for a valid token with the wrong role.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.config.api import ROLES, ApiConfig


def get_api_config() -> ApiConfig:
    """Read at request time so a changed environment takes effect without a restart."""
    return ApiConfig.from_env()


Config = Annotated[ApiConfig, Depends(get_api_config)]


@dataclass(frozen=True)
class Principal:
    role: str  # one of ROLES, "dev" or "gateway"
    user_id: str | None = None  # from `API_TOKENS` role:token:user_id; None if the token has none


def _match(token: str, candidates: dict[str, str]) -> str | None:
    """The configured token equal to `token`, compared in constant time."""
    for known in candidates:
        if hmac.compare_digest(token.encode(), known.encode()):
            return known
    return None


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def require_roles(*roles: str) -> Callable[..., Principal]:
    assert all(r in ROLES for r in roles), roles

    def dependency(
        config: Config, authorization: Annotated[str | None, Header()] = None
    ) -> Principal:
        token = _bearer(authorization)
        if token is None:
            raise HTTPException(401, "A bearer token is required")
        if config.dev_token and hmac.compare_digest(token.encode(), config.dev_token.encode()):
            return Principal("dev")
        known = _match(token, config.tokens)
        if known is None:
            raise HTTPException(401, "Unknown token")
        role = config.tokens[known]
        if role not in roles:
            raise HTTPException(403, f"Role {role} may not call this endpoint")
        return Principal(role, config.token_users.get(known))

    return dependency


def require_gateway(
    config: Config, x_gateway_token: Annotated[str | None, Header()] = None
) -> Principal:
    if not config.gateway_token or not x_gateway_token:
        raise HTTPException(401, "The gateway credential is required")
    if not hmac.compare_digest(x_gateway_token.encode(), config.gateway_token.encode()):
        raise HTTPException(401, "Unknown gateway credential")
    return Principal("gateway")


OFFICER = Depends(require_roles("officer"))
