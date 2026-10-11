from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Oslo Post Auto"
    app_secret_key: str = Field(
        default="dev-secret-change-me-in-production",
        validation_alias=AliasChoices("APP_SECRET_KEY", "SECRET_KEY", "app_secret_key", "secret_key"),
    )
    token_encryption_key: str = Field(
        default="",
        validation_alias=AliasChoices("TOKEN_ENCRYPTION_KEY", "token_encryption_key"),
    )
    secure_cookies: bool = Field(default=False, validation_alias=AliasChoices("SECURE_COOKIES", "secure_cookies"))

    @model_validator(mode="before")
    @classmethod
    def normalize_env_values(cls, values):
        if isinstance(values, dict):
            for key in list(values):
                if key and isinstance(values[key], str):
                    values[key] = values[key].strip()
            env_secret = values.get("APP_SECRET_KEY") or values.get("SECRET_KEY") or values.get("app_secret_key") or values.get("secret_key")
            if env_secret and env_secret.lower() in {"replace-with-a-long-random-secret", "your-app-secret-key", "changeme", "secret", "development"}:
                values["APP_SECRET_KEY"] = env_secret
            cloudinary_url = values.get("CLOUDINARY_URL") or values.get("cloudinary_url")
            if isinstance(cloudinary_url, str) and cloudinary_url.startswith("cloudinary://"):
                values["CLOUDINARY_URL"] = cloudinary_url.strip()
            if cloudinary_url and not cloudinary_url.startswith("cloudinary://"):
                values["CLOUDINARY_URL"] = ""
        return values

    supabase_url: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_URL", "DATABASE_URL", "supabase_url", "database_url"),
    )
    supabase_anon_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "supabase_anon_key"),
    )
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "supabase_service_role_key"),
    )

    cloudinary_cloud_name: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDINARY_CLOUD_NAME", "cloudinary_cloud_name"),
    )
    cloudinary_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDINARY_API_KEY", "cloudinary_api_key"),
    )
    cloudinary_api_secret: str = Field(
        default="",
        validation_alias=AliasChoices("CLOUDINARY_API_SECRET", "cloudinary_api_secret"),
    )
    cloudinary_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CLOUDINARY_URL", "cloudinary_url"),
    )

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias=AliasChoices("REDIS_URL", "redis_url"))
    public_base_url: str = Field(default="http://localhost:8000", validation_alias=AliasChoices("PUBLIC_BASE_URL", "public_base_url"))
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, validation_alias=AliasChoices("MAX_UPLOAD_BYTES", "max_upload_bytes"))

    instagram_client_id: str = Field(default="", validation_alias=AliasChoices("INSTAGRAM_CLIENT_ID", "instagram_client_id"))
    instagram_client_secret: str = Field(default="", validation_alias=AliasChoices("INSTAGRAM_CLIENT_SECRET", "instagram_client_secret"))
    facebook_client_id: str = Field(default="", validation_alias=AliasChoices("FACEBOOK_CLIENT_ID", "facebook_client_id"))
    facebook_client_secret: str = Field(default="", validation_alias=AliasChoices("FACEBOOK_CLIENT_SECRET", "facebook_client_secret"))
    tiktok_client_id: str = Field(default="", validation_alias=AliasChoices("TIKTOK_CLIENT_ID", "tiktok_client_id"))
    tiktok_client_secret: str = Field(default="", validation_alias=AliasChoices("TIKTOK_CLIENT_SECRET", "tiktok_client_secret"))
    x_client_id: str = Field(default="", validation_alias=AliasChoices("X_CLIENT_ID", "x_client_id", "X_API_KEY", "x_api_key"))
    x_client_secret: str = Field(default="", validation_alias=AliasChoices("X_CLIENT_SECRET", "x_client_secret", "X_API_SECRET", "x_api_secret"))
    linkedin_client_id: str = Field(default="", validation_alias=AliasChoices("LINKEDIN_CLIENT_ID", "linkedin_client_id"))
    linkedin_client_secret: str = Field(default="", validation_alias=AliasChoices("LINKEDIN_CLIENT_SECRET", "linkedin_client_secret"))

    @model_validator(mode="after")
    def resolve_cloudinary_url(self):
        if not self.cloudinary_url:
            self.cloudinary_url = None
        elif not self.cloudinary_url.startswith("cloudinary://"):
            self.cloudinary_url = None
        if self.cloudinary_cloud_name and self.cloudinary_api_key and self.cloudinary_api_secret:
            return self
        if not self.cloudinary_url:
            return self
        parsed = urlparse(self.cloudinary_url)
        if parsed.scheme != "cloudinary":
            self.cloudinary_url = None
            return self
        if parsed.hostname:
            self.cloudinary_cloud_name = parsed.hostname
        if parsed.username:
            self.cloudinary_api_key = parsed.username
        if parsed.password:
            self.cloudinary_api_secret = parsed.password
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
