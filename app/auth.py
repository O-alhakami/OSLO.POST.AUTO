from typing import Any

from fastapi import Depends, HTTPException, Request, status
from supabase import AuthApiError

from app.database import get_auth_supabase


def _get_user_from_response(response: Any) -> Any:
    user = getattr(response, "user", None)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="الجلسة منتهية أو غير صالحة.")
    return user


def get_current_user(request: Request) -> dict[str, Any]:
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="يرجى تسجيل الدخول أولاً.")
    try:
        user = _get_user_from_response(get_auth_supabase().auth.get_user(access_token))
    except AuthApiError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="انتهت الجلسة، يرجى تسجيل الدخول مرة أخرى.") from exc
    app_metadata = getattr(user, "app_metadata", None) or {}
    return {
        "id": str(user.id),
        "email": user.email,
        "role": app_metadata.get("role", "user"),
    }


def get_admin_user(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="هذه الصفحة مخصصة للمدير فقط.")
    return user


CurrentUser = Depends(get_current_user)
