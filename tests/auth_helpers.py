"""Mint development JWTs for tests (the same HS256 key the test apps use)."""

from aegisops.api.auth import issue_dev_token
from aegisops.application.roles import UserRole
from aegisops.core.config import Settings


def bearer(sub: str = "alice", role: str = "operator") -> dict[str, str]:
    token = issue_dev_token(Settings(environment="test"), sub, UserRole(role))
    return {"Authorization": f"Bearer {token}"}


# Dispositions need a reason code that fits the action (aegisops/application/dispositions.py).
APPROVE = {"action": "approve", "reason_code": "reviewed_as_proposed"}
REJECT = {"action": "reject", "reason_code": "better_plan_needed"}
