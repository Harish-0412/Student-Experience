from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ASTRAPATH_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AstraPath API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./astrapath.db"
    sql_echo: bool = False
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    auth_mode: Literal["local", "oidc"] = "local"
    jwt_secret: str = "development-only-secret-change-before-production"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "astrapath"
    jwt_audience: str = "astrapath-api"
    access_token_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_days: int = Field(default=30, ge=1, le=90)

    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_role_claim: str = "roles"
    oidc_allow_admin_jit: bool = False

    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "astrapath-goals"

    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "testserver"]
    )
    trust_proxy_headers: bool = False
    max_request_bytes: int = Field(default=1_048_576, ge=256, le=10_485_760)
    rate_limit_requests: int = Field(default=600, ge=1, le=100_000)
    auth_rate_limit_requests: int = Field(default=30, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    max_inflight_requests: int = Field(default=100, ge=1, le=10_000)
    idempotency_ttl_seconds: int = Field(default=3600, ge=60, le=86_400)
    idempotency_max_entries: int = Field(default=10_000, ge=100, le=100_000)

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.environment in {"staging", "production"} and len(self.jwt_secret) < 32:
            raise ValueError("ASTRAPATH_JWT_SECRET must contain at least 32 characters")
        if self.environment in {"staging", "production"}:
            if "*" in self.allowed_origins:
                raise ValueError("Wildcard CORS origins are forbidden outside development")
            if "*" in self.trusted_hosts:
                raise ValueError("Wildcard trusted hosts are forbidden outside development")
        if self.auth_mode == "oidc":
            missing = [
                name
                for name, value in (
                    ("OIDC issuer", self.oidc_issuer),
                    ("OIDC audience", self.oidc_audience),
                    ("OIDC JWKS URL", self.oidc_jwks_url),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"Missing OIDC settings: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
