"""Mint development JWTs for tests (the same HS256 key the test apps use)."""

from aegisops.api.auth import issue_dev_token
from aegisops.application.roles import UserRole
from aegisops.core.config import Settings


def bearer(sub: str = "alice", role: str = "operator") -> dict[str, str]:
    token = issue_dev_token(Settings(environment="test"), sub, UserRole(role))
    return {"Authorization": f"Bearer {token}"}
