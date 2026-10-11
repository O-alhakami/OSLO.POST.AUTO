from typing import Any

from fastapi import Depends, HTTPException, Request, status
from supabase import AuthApiError

from app.database import get_auth_supabase


def _get_user_from_response(response: Any) -> Any:
    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.")
    return user


def get_current_user(request: Request) -> dict[str, Any]:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in.")
    try:
        user = _get_user_from_response(get_auth_supabase().auth.get_user(access_token))
    except AuthApiError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired; please sign in again.") from exc
    return {"id": str(user.id), "email": user.email}


CurrentUser = Depends(get_current_user)
