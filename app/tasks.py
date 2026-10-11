from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Celery

from app.cloudinary_service import delete_media
from app.config import get_settings
from app.database import get_supabase
from app.security import decrypt_token

settings = get_settings()
celery_app = Celery("oslo_post_auto", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "cleanup-published-posts-daily": {
            "task": "app.tasks.cleanup_published_posts",
            "schedule": 24 * 60 * 60,
        }
    },
)


def publish_to_platform(platform: str, access_token: str, content: str, media_urls: list[str]) -> dict[str, Any]:
    """Replace with the platform's publishing API; this intentionally never publishes externally."""
    if not access_token:
        raise ValueError(f"Missing access token for {platform}.")
    return {"platform": platform, "success": True, "mock": True, "media_count": len(media_urls)}


@celery_app.task(name="app.tasks.publish_post")
def publish_post(post_id: str) -> dict[str, Any]:
    db = get_supabase()
    result = db.table("posts").select("*").eq("id", post_id).limit(1).execute()
    if not result.data:
        raise ValueError(f"Post {post_id} was not found.")
    post = result.data[0]
    accounts_result = (
        db.table("social_accounts")
        .select("platform,access_token")
        .eq("user_id", post["user_id"])
        .execute()
    )
    accounts = {item["platform"]: item for item in accounts_result.data}
    outcomes = []
    try:
        for platform in post["platforms"]:
            account = accounts.get(platform)
            if not account:
                raise ValueError(f"No connected {platform} account is available for post {post_id}.")
            token = decrypt_token(account.get("access_token"))
            outcomes.append(publish_to_platform(platform, token or "", post.get("content", ""), post.get("media_urls", [])))
    except Exception as exc:
        db.table("posts").update({"status": "failed", "error_message": str(exc)}).eq("id", post_id).execute()
        raise
    published_at = datetime.now(timezone.utc).isoformat()
    db.table("posts").update(
        {"status": "published", "published_at": published_at, "error_message": None}
    ).eq("id", post_id).execute()
    return {"post_id": post_id, "results": outcomes, "mock": True}


@celery_app.task(name="app.tasks.cleanup_published_posts")
def cleanup_published_posts() -> dict[str, int]:
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    result = db.table("posts").select("id,media_public_ids").eq("status", "published").lt("published_at", cutoff).execute()
    deleted_posts = 0
    deleted_assets = 0
    for post in result.data:
        for asset in post.get("media_public_ids") or []:
            if isinstance(asset, str):
                public_id, resource_type = asset, "image"
            else:
                public_id = asset["public_id"]
                resource_type = asset.get("resource_type", "image")
            delete_media(public_id, resource_type)
            deleted_assets += 1
        db.table("posts").delete().eq("id", post["id"]).execute()
        deleted_posts += 1
    return {"posts": deleted_posts, "assets": deleted_assets}
