"""
==============================================================
File: settings.py

Settings - Cau hinh tap trung qua pydantic-settings.
Doc bien moi truong mot lan va dung get_settings() o moi noi.

Luu y: Moi field co alias = env var name (UPPER_SNAKE) de pydantic-settings
doc dung tu os.environ. Trong code dung field name (snake_case).
==============================================================
"""

import logging
import re
from functools import lru_cache
from typing import List

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


GEMINI_TEXT_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")


def _within_gemini_version_limit(model: str) -> bool:
    # Unversioned 'latest' aliases can silently resolve above the chosen cap.
    version = re.match(r"^(?:models/)?gemini-(\d+)(?:\.(\d+))?-", model)
    return bool(version and (int(version[1]), int(version[2] or 0)) <= (3, 6))


class FirebaseSettings(BaseSettings):
    """Cau hinh Firebase Admin SDK."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    google_application_credentials: str = Field(
        default="./config/serviceAccountKey.json",
        validation_alias=AliasChoices("GOOGLE_APPLICATION_CREDENTIALS"),
        description="Duong dan den service account JSON file",
    )
    project_id: str = Field(
        default="",
        validation_alias=AliasChoices("FIREBASE_PROJECT_ID"),
        description="Firebase project ID",
    )
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("FIREBASE_API_KEY"),
        description="Firebase web API key (client)",
    )
    auth_domain: str = Field(
        default="",
        validation_alias=AliasChoices("FIREBASE_AUTH_DOMAIN"),
        description="Firebase auth domain (client)",
    )


class AuthSettings(BaseSettings):
    """Cau hinh custom auth (JWT HS256, username/password)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    jwt_secret: str = Field(
        default="change-me-in-production-must-be-32-bytes-minimum",
        validation_alias=AliasChoices("JWT_SECRET"),
        description="JWT HS256 secret (>= 32 ky tu)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM"),
    )
    jwt_expire_hours: int = Field(
        default=24,
        validation_alias=AliasChoices("JWT_EXPIRE_HOURS"),
        description="Token song (gio)",
    )
    bcrypt_rounds: int = Field(
        default=12,
        validation_alias=AliasChoices("BCRYPT_ROUNDS"),
        description="bcrypt cost (12 = ~250ms/hash)",
    )
    min_password_length: int = Field(
        default=6,
        validation_alias=AliasChoices("MIN_PASSWORD_LENGTH"),
    )
    min_username_length: int = Field(
        default=3,
        validation_alias=AliasChoices("MIN_USERNAME_LENGTH"),
    )


class GoogleAISettings(BaseSettings):
    """Cau hinh Google AI Studio (Gemini API)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY"),
        description="Google AI Studio API key chính",
    )
    api_key_2: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY_2"),
        description="Google AI Studio API key dự phòng 2",
    )
    api_key_3: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY_3"),
        description="Google AI Studio API key dự phòng 3",
    )
    api_key_4: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY_4"),
        description="Google AI Studio API key dự phòng 4",
    )
    api_key_5: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY_5"),
        description="Google AI Studio API key dự phòng 5",
    )
    model: str = Field(
        default=GEMINI_TEXT_MODELS[0],
        validation_alias=AliasChoices("GEMINI_MODEL"),
        description="Model Gemini su dung mac dinh",
    )
    models_csv: str = Field(
        default=",".join(GEMINI_TEXT_MODELS),
        validation_alias=AliasChoices("GEMINI_MODELS"),
        description="Danh sach cac model xoay vong cach nhau boi dau phay",
    )
    timeout_seconds: int = Field(
        default=20,
        validation_alias=AliasChoices("GEMINI_TIMEOUT_SECONDS"),
        description="Timeout goi API (seconds)",
    )

    @field_validator("model")
    @classmethod
    def enforce_model_version_limit(cls, value: str) -> str:
        value = value.strip()
        if not _within_gemini_version_limit(value):
            logging.getLogger(__name__).warning("Gemini primary model exceeds configured version policy; using 3.6 Flash")
            return GEMINI_TEXT_MODELS[0]
        return value

    @property
    def api_keys(self) -> list[str]:
        """Danh sach tat ca API keys hop le, khong trung lap va khong rong."""
        candidates = [self.api_key, self.api_key_2, self.api_key_3, self.api_key_4, self.api_key_5]
        seen = set()
        valid = []
        for k in candidates:
            k_clean = (k or "").strip()
            if k_clean and k_clean not in seen and not k_clean.startswith("YOUR_"):
                seen.add(k_clean)
                valid.append(k_clean)
        return valid

    @property
    def model_pool(self) -> list[str]:
        """Danh sach cac model theo thu tu uu tien xoay vong."""
        raw_list = list(dict.fromkeys(m.strip() for m in self.models_csv.split(",") if m.strip()))
        allowed = [m for m in raw_list if _within_gemini_version_limit(m)]
        if len(allowed) != len(raw_list):
            logging.getLogger(__name__).warning("Ignored Gemini model pool entries above 3.6 or with unversioned aliases")
        return allowed or [self.model, *[m for m in GEMINI_TEXT_MODELS if m != self.model]]


class GoogleAIEmbedSettings(BaseSettings):
    """Cau hinh Google AI Embedding (text-embedding-004).

    Dung chung GOOGLE_API_KEY voi GoogleAISettings (cung provider).
    Output dimensionality mac dinh 768 (text-embedding-004).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_API_KEY"),
        description="Dung chung key voi Gemini (reuse).",
    )
    model: str = Field(
        default="text-embedding-004",
        validation_alias=AliasChoices("GEMINI_EMBED_MODEL"),
        description="Embedding model (text-embedding-004)",
    )
    output_dimensionality: int = Field(
        default=768,
        validation_alias=AliasChoices("GEMINI_EMBED_DIM"),
        description="Output embedding dimensions",
    )
    timeout_seconds: int = Field(
        default=20,
        validation_alias=AliasChoices("GEMINI_EMBED_TIMEOUT_SECONDS"),
        description="Timeout goi API (seconds)",
    )


class QdrantSettings(BaseSettings):
    """Cau hinh Qdrant vector database (self-host Docker local)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(
        default="localhost",
        validation_alias=AliasChoices("QDRANT_HOST"),
        description="Qdrant host",
    )
    port: int = Field(
        default=6333,
        validation_alias=AliasChoices("QDRANT_PORT"),
        description="Qdrant HTTP port",
    )
    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("QDRANT_API_KEY"),
        description="Qdrant API key (rong neu self-host khong set auth)",
    )
    collection_name: str = Field(
        default="burnout_case_memory",
        validation_alias=AliasChoices("QDRANT_COLLECTION"),
        description="Ten collection (default: burnout_case_memory per knowledge.py Literal)",
    )
    vector_size: int = Field(
        default=768,
        validation_alias=AliasChoices("QDRANT_VECTOR_SIZE"),
        description="Vector dimensionality (phai match embedding model)",
    )
    timeout_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("QDRANT_TIMEOUT_SECONDS"),
        description="Timeout cho Qdrant client",
    )


class R2Settings(BaseSettings):
    """Cau hinh Cloudflare R2 (S3-compatible)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    account_id: str = Field(
        default="",
        validation_alias=AliasChoices("R2_ACCOUNT_ID"),
        description="Cloudflare account ID",
    )
    access_key_id: str = Field(
        default="",
        validation_alias=AliasChoices("R2_ACCESS_KEY_ID"),
        description="R2 access key ID",
    )
    secret_access_key: str = Field(
        default="",
        validation_alias=AliasChoices("R2_SECRET_ACCESS_KEY"),
        description="R2 secret access key",
    )
    bucket_name: str = Field(
        default="burnout-ai-images",
        validation_alias=AliasChoices("R2_BUCKET_NAME"),
        description="Ten bucket",
    )
    public_url: str = Field(
        default="https://your-bucket.r2.dev",
        validation_alias=AliasChoices("R2_PUBLIC_URL"),
        description="Public URL prefix",
    )
    region: str = Field(
        default="auto",
        validation_alias=AliasChoices("R2_REGION"),
        description="R2 region (auto mac dinh)",
    )


class GeoapifySettings(BaseSettings):
    """Cau hinh Geoapify Places API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEOAPIFY_API_KEY"),
        description="Geoapify API key",
    )
    base_url: str = Field(
        default="https://api.geoapify.com",
        validation_alias=AliasChoices("GEOAPIFY_BASE_URL"),
        description="Geoapify base URL",
    )
    places_url: str = Field(
        default="https://api.geoapify.com/v1/mcp",
        validation_alias=AliasChoices("GEOAPIFY_PLACES_URL"),
        description="Geoapify Places API URL (v1 MCP)",
    )
    timeout_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("GEOAPIFY_TIMEOUT_SECONDS"),
        description="API timeout (seconds)",
    )
    default_radius_meters: int = Field(
        default=5000,
        validation_alias=AliasChoices("GEOAPIFY_DEFAULT_RADIUS_METERS"),
        description="Default search radius (meters)",
    )
    default_limit: int = Field(
        default=10,
        validation_alias=AliasChoices("GEOAPIFY_DEFAULT_LIMIT"),
        description="Default number of places to return",
    )


class ServerSettings(BaseSettings):
    """Cau hinh server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    host: str = Field(default="0.0.0.0", validation_alias=AliasChoices("API_HOST"))
    port: int = Field(default=8000, validation_alias=AliasChoices("API_PORT"))
    environment: str = Field(default="development", validation_alias=AliasChoices("ENVIRONMENT"))
    max_upload_size: int = Field(
        default=5 * 1024 * 1024,  # 5 MB
        validation_alias=AliasChoices("MAX_UPLOAD_SIZE"),
        description="Max upload bytes (mac dinh 5MB)",
    )
    max_image_width: int = Field(
        default=3840,
        validation_alias=AliasChoices("MAX_IMAGE_WIDTH"),
        description="Max width (px) - anh lon hon se bi reject",
    )
    max_image_height: int = Field(
        default=2160,
        validation_alias=AliasChoices("MAX_IMAGE_HEIGHT"),
        description="Max height (px) - anh lon hon se bi reject",
    )


class CORSSettings(BaseSettings):
    """Cau hinh CORS."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    allowed_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices("CORS_ALLOWED_ORIGINS"),
        description="Danh sach origin duoc phep (mac dinh: tat ca)",
    )


class CacheSettings(BaseSettings):
    """Cau hinh Cache (Assessment + Chat)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    assessment_ttl_days: int = Field(
        default=7,
        validation_alias=AliasChoices("ASSESSMENT_CACHE_TTL_DAYS"),
        description="TTL cho assessment cache (days)",
    )
    chat_ttl_hours: int = Field(
        default=24,
        validation_alias=AliasChoices("CHAT_CACHE_TTL_HOURS"),
        description="TTL cho chat cache (hours)",
    )


class RateLimitSettings(BaseSettings):
    """Cau hinh Rate Limiting."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    user_daily_limit: int = Field(
        default=100,
        validation_alias=AliasChoices("RATE_LIMIT_USER_DAILY"),
        description="AI calls per user per day",
    )
    global_hourly_limit: int = Field(
        default=10000,
        validation_alias=AliasChoices("RATE_LIMIT_GLOBAL_HOURLY"),
        description="Total AI calls per hour",
    )


class EmotionChatSettings(BaseSettings):
    """Cau hinh Emotion Chat Session Management."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    max_session_hours: int = Field(
        default=5,
        validation_alias=AliasChoices("EMOTION_CHAT_MAX_SESSION_HOURS"),
        description="Thoi gian toi da mot session (gio)",
    )
    idle_timeout_minutes: int = Field(
        default=60,
        validation_alias=AliasChoices("EMOTION_CHAT_IDLE_TIMEOUT_MINUTES"),
        description="Thoi gian idle toi da truoc khi tao session moi (phut)",
    )
    max_context_messages: int = Field(
        default=20,
        validation_alias=AliasChoices("EMOTION_CHAT_MAX_CONTEXT_MESSAGES"),
        description="So tin nhan toi da gui cho Gemini trong context",
    )


class Settings(BaseSettings):
    """Tong hop settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    firebase: FirebaseSettings = Field(default_factory=FirebaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    google_ai: GoogleAISettings = Field(default_factory=GoogleAISettings)
    google_ai_embed: GoogleAIEmbedSettings = Field(default_factory=GoogleAIEmbedSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    r2: R2Settings = Field(default_factory=R2Settings)
    geoapify: GeoapifySettings = Field(default_factory=GeoapifySettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    cors: CORSSettings = Field(default_factory=CORSSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    emotion_chat: EmotionChatSettings = Field(default_factory=EmotionChatSettings)


# ==========================================
# SINGLETON
# ==========================================

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Lay Settings singleton (cached)."""
    return Settings()


# ==========================================
# LOGGING
# ==========================================

def configure_logging(level: str = "INFO") -> None:
    """Cau hinh logging cho app."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
