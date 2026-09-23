"""JWT bearer authentication.

HS256 with ``AEGISOPS_SECRET_KEY`` for development, or RS256 with keys from an OIDC provider's
JWKS (``AEGISOPS_JWT_ALGORITHM=RS256``, ``AEGISOPS_JWT_JWKS_URL``, optional issuer/audience).
A token must carry ``sub``, ``exp`` and a role claim (``AEGISOPS_JWT_ROLE_CLAIM``, default
``role``; a list of roles resolves to the most privileged recognised one).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from aegisops.application.roles import UserRole
from aegisops.core.config import DEFAULT_SECRET_KEY, Settings

bearer_scheme = HTTPBearer(auto_error=False)
Subject = Annotated[str, Field(min_length=1, max_length=255)]


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: Subject
    role: UserRole


class TokenVerifier:
    def __init__(self, settings: Settings, jwks_client: jwt.PyJWKClient | None = None) -> None:
        self._settings = settings
        self._jwks: jwt.PyJWKClient | None = None
        if settings.jwt_algorithm == "RS256":
            if jwks_client is None and not settings.jwt_jwks_url:
                raise ValueError("RS256 requires AEGISOPS_JWT_JWKS_URL")
            self._jwks = jwks_client or jwt.PyJWKClient(str(settings.jwt_jwks_url))

    def verify(self, token: str) -> Principal:
        settings = self._settings
        key: object = settings.secret_key
        if self._jwks is not None:
            key = self._jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,  # type: ignore[arg-type]
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_s,
            options={"require": ["exp", "sub"], "verify_aud": settings.jwt_audience is not None},
        )
        return Principal(sub=claims["sub"], role=_role_from(claims.get(settings.jwt_role_claim)))


def _role_from(claim: object) -> UserRole:
    values = claim if isinstance(claim, list) else [claim]
    roles = [UserRole(value) for value in values if value in {r.value for r in UserRole}]
    if not roles:
        raise jwt.InvalidTokenError("token carries no recognised role")
    return max(roles, key=lambda role: role.rank)


def issue_dev_token(
    settings: Settings, sub: str, role: UserRole, ttl_s: int | None = None
) -> str:
    """Mint an HS256 token signed with the development key. Never exposed outside development."""
    if settings.jwt_algorithm != "HS256":
        raise ValueError("development tokens are HS256 only")
    now = int(time.time())
    claims: dict[str, object] = {
        "sub": sub,
        settings.jwt_role_claim: role.value,
        "iat": now,
        "exp": now + (ttl_s or settings.dev_token_ttl_s),
    }
    if settings.jwt_issuer:
        claims["iss"] = settings.jwt_issuer
    if settings.jwt_audience:
        claims["aud"] = settings.jwt_audience
    return jwt.encode(claims, settings.secret_key, algorithm="HS256")


def check_secret_configuration(settings: Settings) -> None:
    """Refuse to serve with the published development key outside development and tests."""
    if settings.environment in {"development", "test"}:
        return
    if settings.jwt_algorithm == "HS256" and settings.secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "AEGISOPS_SECRET_KEY is the development default; set a real key, or use RS256 "
            "with AEGISOPS_JWT_JWKS_URL, before running outside development."
        )


def get_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid bearer token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    verifier: TokenVerifier = request.app.state.token_verifier
    try:
        return verifier.verify(credentials.credentials)
    except (jwt.PyJWTError, ValueError) as error:
        raise unauthorized from error


def require_role(minimum: UserRole) -> Callable[[Principal], Principal]:
    def checker(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if not principal.role.at_least(minimum):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires the {minimum.value} role or higher.",
            )
        return principal

    return checker


require_viewer = require_role(UserRole.VIEWER)
require_operator = require_role(UserRole.OPERATOR)
require_approver = require_role(UserRole.APPROVER)
require_admin = require_role(UserRole.ADMIN)
