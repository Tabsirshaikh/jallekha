"""Who am I (T10): the role and bound user id of the calling token, for the frontend.

Any valid user-role token answers, and so does the dev token (role `dev`, no user id). The
token itself is never echoed. The gateway credential is not a user and gets 401.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import Principal, require_roles
from app.config.api import ROLES

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
def me(principal: Annotated[Principal, Depends(require_roles(*ROLES))]) -> dict[str, str | None]:
    return {"role": principal.role, "user_id": principal.user_id}
