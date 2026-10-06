"""Who am I (T10): the role and bound user id of the calling token, for the frontend.

Any valid user-role token answers, and so does the dev token (role `dev`, no user id). When the
server is open (no AUTH_REQUIRED) everyone answers as `dev` with `open: true`. The token itself
is never echoed. The gateway credential is not a user and gets 401.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import Config, Principal, require_roles
from app.config.api import ROLES

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
def me(
    principal: Annotated[Principal, Depends(require_roles(*ROLES))], config: Config
) -> dict[str, str | bool | None]:
    """`open` is true when the server does not ask anyone to sign in (AUTH_REQUIRED unset)."""
    return {"role": principal.role, "user_id": principal.user_id, "open": not config.auth_required}
