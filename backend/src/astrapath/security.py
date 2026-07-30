import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from jwt import PyJWKClient

from astrapath.config import Settings
from astrapath.enums import Role
from astrapath.errors import AppError

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    issuer: str
    email: str | None
    full_name: str | None
    role: Role
    auth_version: int | None
    token_type: str


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        return password_hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHash):
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwk_client = (
            PyJWKClient(settings.oidc_jwks_url, cache_jwk_set=True, lifespan=300)
            if settings.auth_mode == "oidc" and settings.oidc_jwks_url
            else None
        )

    def create_access_token(
        self, user_id: uuid.UUID, role: Role, auth_version: int
    ) -> tuple[str, int]:
        now = datetime.now(UTC)
        expires = now + timedelta(minutes=self.settings.access_token_minutes)
        claims = {
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "sub": str(user_id),
            "role": role.value,
            "type": "access",
            "ver": auth_version,
            "jti": secrets.token_urlsafe(18),
            "iat": now,
            "nbf": now,
            "exp": expires,
        }
        return (
            jwt.encode(
                claims,
                self.settings.jwt_secret,
                algorithm=self.settings.jwt_algorithm,
            ),
            self.settings.access_token_minutes * 60,
        )

    def create_refresh_token(
        self, user_id: uuid.UUID, role: Role, auth_version: int
    ) -> tuple[str, datetime]:
        now = datetime.now(UTC)
        expires = now + timedelta(days=self.settings.refresh_token_days)
        claims = {
            "iss": self.settings.jwt_issuer,
            "aud": self.settings.jwt_audience,
            "sub": str(user_id),
            "role": role.value,
            "type": "refresh",
            "ver": auth_version,
            "jti": secrets.token_urlsafe(24),
            "iat": now,
            "nbf": now,
            "exp": expires,
        }
        return (
            jwt.encode(
                claims,
                self.settings.jwt_secret,
                algorithm=self.settings.jwt_algorithm,
            ),
            expires,
        )

    def verify_local_token(self, token: str, expected_type: str = "access") -> VerifiedIdentity:
        try:
            claims = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                audience=self.settings.jwt_audience,
                issuer=self.settings.jwt_issuer,
                options={"require": ["exp", "iat", "sub", "type", "role", "ver"]},
            )
        except jwt.PyJWTError as exc:
            raise AppError(401, "invalid_token", "Token is invalid or expired") from exc
        if claims.get("type") != expected_type:
            raise AppError(401, "invalid_token_type", f"Expected a {expected_type} token")
        try:
            role = Role(claims["role"])
        except (ValueError, KeyError) as exc:
            raise AppError(403, "invalid_role", "Token does not contain an allowed role") from exc
        return VerifiedIdentity(
            subject=claims["sub"],
            issuer=self.settings.jwt_issuer,
            email=None,
            full_name=None,
            role=role,
            auth_version=int(claims["ver"]),
            token_type=expected_type,
        )

    def verify_oidc_token(self, token: str) -> VerifiedIdentity:
        if not self._jwk_client:
            raise AppError(503, "oidc_unavailable", "OIDC verification is not configured")
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AppError(401, "invalid_token", "OIDC token is invalid or expired") from exc
        role = self._extract_oidc_role(claims)
        return VerifiedIdentity(
            subject=str(claims["sub"]),
            issuer=str(claims.get("iss", self.settings.oidc_issuer)),
            email=claims.get("email"),
            full_name=claims.get("name"),
            role=role,
            auth_version=None,
            token_type="access",  # noqa: S106
        )

    def verify_access_token(self, token: str) -> VerifiedIdentity:
        if self.settings.auth_mode == "oidc":
            return self.verify_oidc_token(token)
        return self.verify_local_token(token)

    def _extract_oidc_role(self, claims: dict[str, Any]) -> Role:
        raw_roles = claims.get(self.settings.oidc_role_claim, [])
        roles = [raw_roles] if isinstance(raw_roles, str) else list(raw_roles)
        if Role.ADMIN.value in roles and self.settings.oidc_allow_admin_jit:
            return Role.ADMIN
        return Role.STUDENT
