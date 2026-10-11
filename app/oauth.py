import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings


@dataclass(frozen=True)
class Provider:
    client_id_field: str
    client_secret_field: str
    authorization_url: str
    token_url: str
    scopes: tuple[str, ...]
    profile_url: str
    profile_fields: dict[str, str]
    client_id_parameter: str = "client_id"
    token_auth_method: str = "post"
    use_pkce: bool = False
    token_json: bool = False


PROVIDERS: dict[str, Provider] = {
    "instagram": Provider(
        "instagram_client_id", "instagram_client_secret",
        "https://www.instagram.com/oauth/authorize",
        "https://api.instagram.com/oauth/access_token",
        ("instagram_business_basic",),
        "https://graph.instagram.com/me?fields=user_id,username",
        {"id": "user_id", "name": "username"},
    ),
    "facebook": Provider(
        "facebook_client_id", "facebook_client_secret",
        "https://www.facebook.com/v21.0/dialog/oauth",
        "https://graph.facebook.com/v21.0/oauth/access_token",
        ("pages_show_list", "pages_read_engagement", "pages_manage_posts"),
        "https://graph.facebook.com/me?fields=id,name",
        {"id": "id", "name": "name"},
    ),
    "tiktok": Provider(
        "tiktok_client_id", "tiktok_client_secret",
        "https://www.tiktok.com/v2/auth/authorize/",
        "https://open.tiktokapis.com/v2/oauth/token/",
        ("user.info.basic", "video.publish"),
        "https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name",
        {"id": "open_id", "name": "display_name"},
        client_id_parameter="client_key",
        token_auth_method="body",
        token_json=True,
    ),
    "x": Provider(
        "x_client_id", "x_client_secret",
        "https://twitter.com/i/oauth2/authorize",
        "https://api.x.com/2/oauth2/token",
        ("tweet.read", "tweet.write", "users.read", "offline.access"),
        "https://api.x.com/2/users/me?user.fields=name,username",
        {"id": "id", "name": "name"},
        token_auth_method="basic",
        use_pkce=True,
    ),
    "linkedin": Provider(
        "linkedin_client_id", "linkedin_client_secret",
        "https://www.linkedin.com/oauth/v2/authorization",
        "https://www.linkedin.com/oauth/v2/accessToken",
        ("openid", "profile", "w_member_social"),
        "https://api.linkedin.com/v2/userinfo",
        {"id": "sub", "name": "name"},
    ),
}


def get_provider(platform: str) -> Provider:
    try:
        return PROVIDERS[platform]
    except KeyError as exc:
        raise ValueError(f"Unsupported social platform: {platform}") from exc


def _credentials(provider: Provider, settings: Settings) -> tuple[str, str]:
    client_id = getattr(settings, provider.client_id_field)
    client_secret = getattr(settings, provider.client_secret_field)
    if not client_id or not client_secret:
        raise RuntimeError(f"OAuth credentials are not configured for {provider.client_id_field.removesuffix('_client_id')}.")
    return client_id, client_secret


def authorization_url(platform: str, state: str, redirect_uri: str) -> tuple[str, str | None]:
    provider = get_provider(platform)
    settings = get_settings()
    client_id, _ = _credentials(provider, settings)
    params: dict[str, str] = {
        provider.client_id_parameter: client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(provider.scopes),
        "state": state,
    }
    verifier = None
    if provider.use_pkce:
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        params.update({"code_challenge": challenge, "code_challenge_method": "S256"})
    if platform == "tiktok":
        params["client_key"] = client_id
        params["scope"] = ",".join(provider.scopes)
    return f"{provider.authorization_url}?{urlencode(params)}", verifier


async def exchange_code(platform: str, code: str, redirect_uri: str, code_verifier: str | None) -> dict[str, Any]:
    provider = get_provider(platform)
    client_id, client_secret = _credentials(provider, get_settings())
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if platform == "tiktok":
        data["client_key"] = client_id
        data.pop("client_id")
    if code_verifier:
        data["code_verifier"] = code_verifier
    auth = (client_id, client_secret) if provider.token_auth_method == "basic" else None
    if auth:
        data.pop("client_id", None)
        data.pop("client_secret", None)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(provider.token_url, data=data, auth=auth)
        response.raise_for_status()
        payload = response.json()
    if platform == "tiktok":
        if payload.get("error") != "ok":
            raise RuntimeError(payload.get("error_description", "TikTok token exchange failed."))
        payload = payload.get("data", {})
    return payload


async def fetch_profile(platform: str, access_token: str) -> dict[str, str]:
    provider = get_provider(platform)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            provider.profile_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        payload = response.json()
    if platform == "tiktok":
        payload = payload.get("data", {}).get("user", {})
    elif platform == "x":
        payload = payload.get("data", {})
    account_id = payload.get(provider.profile_fields["id"])
    if not account_id:
        raise RuntimeError(f"Could not identify the {platform} account from the OAuth profile response.")
    return {
        "account_id": str(account_id),
        "account_name": str(payload.get(provider.profile_fields["name"], account_id)),
    }
