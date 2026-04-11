"""Typed configuration loaded from environment variables.

All runtime configuration lives in :class:`Settings`. Never read ``os.environ``
directly from application code — add a field here instead so every config
value is validated, typed, and discoverable from one place.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ─── Runtime ──────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    PROJECT_NAME: str = "Relict"
    API_V1_PREFIX: str = "/api/v1"

    # ─── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:8080",
        ],
        description="Origins permitted to call the API from a browser.",
    )

    # ─── Database ─────────────────────────────────────────────────────
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "relict"
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str = "relict"

    # ─── Redis ────────────────────────────────────────────────────────
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # ─── MinIO / object storage ───────────────────────────────────────
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: SecretStr
    MINIO_BUCKET: str = "relict"
    MINIO_SECURE: bool = False

    # ─── Security ─────────────────────────────────────────────────────
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_ACCESS_TTL_MINUTES: int = 15
    JWT_REFRESH_TTL_DAYS: int = 14

    # ─── Upload limits ────────────────────────────────────────────────
    MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024  # 500 MiB
    ALLOWED_UPLOAD_SUFFIXES: tuple[str, ...] = (
        ".fastq",
        ".fastq.gz",
        ".fq",
        ".fq.gz",
        ".fasta",
        ".fa",
        ".fna",
        ".fasta.gz",
        ".fa.gz",
    )

    # ─── External APIs (used in later phases) ─────────────────────────
    IUCN_REDLIST_TOKEN: SecretStr | None = None
    GBIF_USERNAME: str | None = None
    GBIF_PASSWORD: SecretStr | None = None
    GBIF_EMAIL: str | None = None
    NCBI_API_KEY: SecretStr | None = None
    NCBI_EMAIL: str | None = None

    # ─── Optional ─────────────────────────────────────────────────────
    ZENODO_SANDBOX_TOKEN: SecretStr | None = None

    # ─── Derived URLs ─────────────────────────────────────────────────
    @property
    def database_url_async(self) -> str:
        """SQLAlchemy async URL for FastAPI request handlers."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD.get_secret_value()}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync URL used by Alembic migrations (they don't support async drivers)."""
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD.get_secret_value()}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # ─── Validators ───────────────────────────────────────────────────
    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_strength(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if len(raw) < 16:
            msg = (
                "JWT_SECRET must be at least 16 characters. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
            raise ValueError(msg)
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        # Accept a comma-separated env-var string as well as a real list.
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance.

    Using ``lru_cache`` means Pydantic only parses the env once per process.
    Tests that need to override values should call ``get_settings.cache_clear()``
    before instantiating a new Settings object.
    """
    return Settings()  # type: ignore[call-arg]
