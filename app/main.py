import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from supabase import AuthApiError

from app.auth import get_current_user
from app.cloudinary_service import upload_media
from app.config import get_settings
from app.database import get_auth_supabase, get_supabase
from app.oauth import authorization_url, exchange_code, fetch_profile, get_provider
from app.security import encrypt_token
from app.tasks import publish_post

BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
oauth_serializer = URLSafeTimedSerializer(settings.app_secret_key, salt="social-oauth-state")
ALLOWED_PLATFORMS = {"instagram", "tiktok", "facebook", "x", "linkedin"}
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "video/mp4", "video/quicktime"}


class Credentials(BaseModel):
    email: str
    password: str = Field(min_length=8)


class PostInput(BaseModel):
    content: str = Field(default="", max_length=5000)
    platforms: list[str] = Field(min_length=1)
    media_urls: list[str] = Field(default_factory=list)
    media_public_ids: list[dict[str, str]] = Field(default_factory=list)
    scheduled_at: datetime | None = None


def _session_access_token(auth_response: Any) -> str | None:
    session = getattr(auth_response, "session", None)
    return getattr(session, "access_token", None) if session else None


def _set_auth_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=60 * 60,
        path="/",
    )


@app.get("/ping")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "login.html", {"app_name": settings.app_name})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"app_name": settings.app_name})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict[str, Any] = Depends(get_current_user)):
    return templates.TemplateResponse(request, "dashboard.html", {"app_name": settings.app_name, "user": user})


@app.post("/auth/signup")
async def signup(credentials: Credentials):
    try:
        result = get_auth_supabase().auth.sign_up({"email": credentials.email, "password": credentials.password})
    except AuthApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    token = _session_access_token(result)
    response = JSONResponse(
        {
            "message": "Account created." if token else "Check your email to confirm your account.",
            "authenticated": bool(token),
        },
        status_code=201,
    )
    if token:
        _set_auth_cookie(response, token)
    return response


@app.post("/auth/login")
async def login(credentials: Credentials):
    try:
        result = get_auth_supabase().auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )
    except AuthApiError as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password.") from exc
    token = _session_access_token(result)
    if not token:
        raise HTTPException(status_code=401, detail="Sign-in did not return a valid session.")
    response = JSONResponse({"message": "Signed in."})
    _set_auth_cookie(response, token)
    return response


@app.post("/auth/logout")
async def logout():
    response = JSONResponse({"message": "Signed out."})
    response.delete_cookie("access_token", path="/", secure=settings.secure_cookies, httponly=True, samesite="lax")
    return response


@app.get("/api/social-accounts")
async def social_accounts(user: dict[str, Any] = Depends(get_current_user)):
    result = (
        get_supabase()
        .table("social_accounts")
        .select("id,platform,account_id,account_name,created_at")
        .eq("user_id", user["id"])
        .execute()
    )
    return result.data


@app.get("/oauth/{platform}/connect")
async def connect_social_account(platform: str, user: dict[str, Any] = Depends(get_current_user)):
    if platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=404, detail="Unsupported social platform.")
    try:
        get_provider(platform)
        nonce = secrets.token_urlsafe(32)
        state = oauth_serializer.dumps({"user_id": user["id"], "platform": platform, "nonce": nonce})
        redirect_uri = f"{settings.public_base_url.rstrip('/')}/oauth/{platform}/callback"
        url, verifier = authorization_url(platform, state, redirect_uri)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        "oauth_nonce",
        nonce,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=600,
        path=f"/oauth/{platform}/callback",
    )
    if verifier:
        response.set_cookie(
            "oauth_pkce",
            verifier,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="lax",
            max_age=600,
            path=f"/oauth/{platform}/callback",
        )
    return response


@app.get("/oauth/{platform}/callback")
async def oauth_callback(platform: str, request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return RedirectResponse(f"/dashboard?oauth_error={quote(error)}", status_code=303)
    if not code or not state or platform not in ALLOWED_PLATFORMS:
        raise HTTPException(status_code=400, detail="OAuth callback is missing required parameters.")
    try:
        payload = oauth_serializer.loads(state, max_age=600)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=400, detail="OAuth state is invalid or expired.") from exc
    if payload.get("platform") != platform or not secrets.compare_digest(
        payload.get("nonce", ""), request.cookies.get("oauth_nonce", "")
    ):
        raise HTTPException(status_code=400, detail="OAuth state verification failed.")
    redirect_uri = f"{settings.public_base_url.rstrip('/')}/oauth/{platform}/callback"
    try:
        tokens = await exchange_code(platform, code, redirect_uri, request.cookies.get("oauth_pkce"))
        profile = await fetch_profile(platform, tokens["access_token"])
        expires_in = tokens.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
        row = {
            "user_id": payload["user_id"],
            "platform": platform,
            "account_id": profile["account_id"],
            "account_name": profile["account_name"],
            "access_token": encrypt_token(tokens["access_token"]),
            "refresh_token": encrypt_token(tokens.get("refresh_token")),
            "expires_at": expires_at,
        }
        db = get_supabase()
        existing = (
            db.table("social_accounts")
            .select("id")
            .eq("user_id", payload["user_id"])
            .eq("platform", platform)
            .eq("account_id", profile["account_id"])
            .limit(1)
            .execute()
        )
        if existing.data:
            db.table("social_accounts").update(row).eq("id", existing.data[0]["id"]).execute()
        else:
            db.table("social_accounts").insert(row).execute()
    except (httpx.HTTPError, KeyError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Could not connect {platform}: {exc}") from exc
    response = RedirectResponse("/dashboard?connected=" + platform, status_code=303)
    response.delete_cookie("oauth_nonce", path=f"/oauth/{platform}/callback")
    response.delete_cookie("oauth_pkce", path=f"/oauth/{platform}/callback")
    return response


@app.post("/api/media")
async def media_upload(file: UploadFile = File(...), user: dict[str, Any] = Depends(get_current_user)):
    del user
    if file.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=415, detail="Only supported image and video formats can be uploaded.")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the size limit.")
    try:
        import io

        uploaded = upload_media(io.BytesIO(content), file.filename or "upload", user["id"])
    except (Exception, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=502, detail=f"Cloudinary upload failed: {exc}") from exc
    return {
        "url": uploaded["secure_url"],
        "public_id": uploaded["public_id"],
        "resource_type": uploaded.get("resource_type", "image"),
    }


@app.post("/api/posts", status_code=202)
async def create_post(post_input: PostInput, user: dict[str, Any] = Depends(get_current_user)):
    if not post_input.content.strip() and not post_input.media_urls:
        raise HTTPException(status_code=422, detail="A post must include text or at least one media item.")
    platforms = list(dict.fromkeys(post_input.platforms))
    if not platforms or any(platform not in ALLOWED_PLATFORMS for platform in platforms):
        raise HTTPException(status_code=422, detail="Select one or more supported platforms.")
    if len(post_input.media_urls) != len(post_input.media_public_ids):
        raise HTTPException(status_code=422, detail="Media URLs and Cloudinary asset IDs must match.")
    expected_folder = f"oslo-post-auto/{user['id']}/"
    for media_url, asset in zip(post_input.media_urls, post_input.media_public_ids):
        public_id = asset.get("public_id", "")
        parsed_url = urlparse(media_url)
        if (
            not public_id.startswith(expected_folder)
            or parsed_url.scheme != "https"
            or parsed_url.netloc != "res.cloudinary.com"
            or f"/{settings.cloudinary_cloud_name}/" not in parsed_url.path
        ):
            raise HTTPException(status_code=422, detail="Media must be uploaded to your own Cloudinary folder.")
    scheduled_at = post_input.scheduled_at
    if scheduled_at and scheduled_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="scheduled_at must include a timezone.")
    now = datetime.now(timezone.utc)
    if scheduled_at:
        scheduled_at = scheduled_at.astimezone(timezone.utc)
        if scheduled_at <= now:
            raise HTTPException(status_code=422, detail="Scheduled time must be in the future.")
    db = get_supabase()
    connected = (
        db.table("social_accounts")
        .select("platform")
        .eq("user_id", user["id"])
        .execute()
    )
    available_platforms = {account["platform"] for account in connected.data}
    missing = sorted(set(platforms) - available_platforms)
    if missing:
        raise HTTPException(status_code=422, detail=f"Connect these accounts first: {', '.join(missing)}.")
    row = {
        "user_id": user["id"],
        "content": post_input.content.strip(),
        "media_urls": post_input.media_urls,
        "media_public_ids": post_input.media_public_ids,
        "platforms": platforms,
        "status": "scheduled" if scheduled_at else "queued",
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else now.isoformat(),
    }
    result = db.table("posts").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="The post could not be saved.")
    created = result.data[0]
    try:
        if scheduled_at:
            publish_post.apply_async(args=[str(created["id"])], eta=scheduled_at)
        else:
            publish_post.delay(str(created["id"]))
    except Exception as exc:
        db.table("posts").update({"status": "failed", "error_message": f"Could not enqueue task: {exc}"}).eq(
            "id", created["id"]
        ).execute()
        raise HTTPException(status_code=503, detail="The post was saved, but the worker could not be reached.") from exc
    return {"id": created["id"], "status": row["status"], "scheduled_at": row["scheduled_at"]}


@app.get("/api/posts")
async def list_posts(user: dict[str, Any] = Depends(get_current_user)):
    result = (
        get_supabase()
        .table("posts")
        .select("id,content,media_urls,platforms,status,scheduled_at,published_at,created_at,error_message")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return result.data
