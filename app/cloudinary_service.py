from typing import Any, BinaryIO

import cloudinary
import cloudinary.uploader

from app.config import get_settings


def configure_cloudinary() -> None:
    settings = get_settings()
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


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
