from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Oslo Post Auto"
    app_secret_key: str = "replace-this-development-secret"
    token_encryption_key: str = ""
    secure_cookies: bool = False

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    redis_url: str = "redis://localhost:6379/0"
    public_base_url: str = "http://localhost:8000"
    max_upload_bytes: int = 100 * 1024 * 1024

    instagram_client_id: str = ""
    instagram_client_secret: str = ""
    facebook_client_id: str = ""
    facebook_client_secret: str = ""
    tiktok_client_id: str = ""
    tiktok_client_secret: str = ""
    x_client_id: str = ""
    x_client_secret: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
