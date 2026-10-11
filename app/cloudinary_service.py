import os
from typing import Any, BinaryIO

cloudinary_url = os.environ.get("CLOUDINARY_URL")
if cloudinary_url and not cloudinary_url.startswith("cloudinary://"):
    os.environ.pop("CLOUDINARY_URL", None)

import cloudinary
import cloudinary.uploader

from app.config import get_settings


def _safe_cloudinary_config() -> None:
    settings = get_settings()
    cloud_name = settings.cloudinary_cloud_name.strip()
    api_key = settings.cloudinary_api_key.strip()
    api_secret = settings.cloudinary_api_secret.strip()
    if not cloud_name or not api_key or not api_secret:
        return
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )


def configure_cloudinary() -> None:
    _safe_cloudinary_config()


def upload_media(file: BinaryIO, filename: str, user_id: str) -> dict[str, Any]:
    configure_cloudinary()
    return cloudinary.uploader.upload(
        file,
        resource_type="auto",
        folder=f"oslo-post-auto/{user_id}",
        public_id=filename.rsplit(".", 1)[0],
        use_filename=True,
        unique_filename=True,
    )


def delete_media(public_id: str, resource_type: str | None = None) -> None:
    configure_cloudinary()
    result = cloudinary.uploader.destroy(public_id, resource_type=resource_type or "image", invalidate=True)
    if result.get("result") not in {"ok", "not found"}:
        raise RuntimeError(f"Cloudinary could not delete asset {public_id}: {result}")
