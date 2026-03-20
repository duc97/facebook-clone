from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://fb:fb_password@localhost:5432/facebook_clone"
    database_echo: bool = False

    # Database connection pool
    # pool_size: persistent connections kept open per worker process.
    #   10 is a good baseline for a single-instance asyncpg app; tune up
    #   (e.g. 20) if the Prometheus checkout_wait_seconds p99 climbs above 5 ms.
    db_pool_size: int = 10
    # max_overflow: burst capacity above pool_size.  Total max connections =
    #   pool_size + max_overflow = 30 per worker.  Set 0 to disable overflow.
    db_pool_max_overflow: int = 20
    # pool_recycle: force-close and reopen connections after this many seconds
    #   to prevent stale TCP handles.  1800 s (30 min) is safer than 3600 s
    #   in Kubernetes environments where pods may restart within the hour.
    db_pool_recycle: int = 1800
    # pool_timeout: max seconds to wait for a free connection before raising
    #   sqlalchemy.exc.TimeoutError.  30 s is reasonable; lower to 10 s for
    #   stricter SLOs.
    db_pool_timeout: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Upload / Storage
    upload_dir: str = "./uploads"
    storage_backend: str = "local"  # "local" or "s3"
    s3_bucket_name: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str = ""  # For MinIO / LocalStack
    max_media_upload_size: int = 50 * 1024 * 1024  # 50 MB
    allowed_media_types: list[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "video/mp4",
        "video/quicktime",
        "video/webm",
    ]

    # Video Processing
    video_max_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    video_thumbnail_at_second: float = 1.0

    # Image Processing
    image_max_width: int = 1920
    image_max_height: int = 1080
    image_thumbnail_size: int = 320
    image_quality: int = 85
    image_max_size_bytes: int = 10 * 1024 * 1024  # 10 MB

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Feed Cache
    feed_cache_max_size: int = 200
    feed_fan_out_max_friends: int = 500

    # Debug
    debug: bool = True

    # Rate Limiting
    rate_limit_guest: int = 30  # per minute
    rate_limit_user: int = 60
    rate_limit_premium: int = 120

    # API
    api_version: str = "1.0"

    # Cache TTLs (seconds) — can override via env vars
    cache_ttl_profile: int = 300
    cache_ttl_post: int = 120
    cache_ttl_user_posts: int = 60
    cache_ttl_friends: int = 600
    cache_ttl_friend_count: int = 120  # 2 min — invalidated on friend add/remove
    cache_ttl_notif_unread: int = 30
    cache_ttl_feed: int = 60
    cache_enabled: bool = True


def get_settings() -> Settings:
    return Settings()
