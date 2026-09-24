"""Public demo: fixed identities and the hourly sandbox reset (AEGISOPS_ENVIRONMENT=demo).

Anyone can sign in as ``demo-operator`` or ``demo-approver``; roles are fixed by the server, not
chosen by the client. Nothing else about users, seeds or configuration can be changed, and no
model is configured, so visitors never spend credits.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from aegisops.api.auth import issue_dev_token
from aegisops.application.roles import UserRole
from aegisops.core.config import Settings

DEMO_ROLES = {"demo-operator": UserRole.OPERATOR, "demo-approver": UserRole.APPROVER}


class DemoTokenRequest(BaseModel):
    # A role sent by the client is ignored: each demo identity has one fixed role.
    model_config = ConfigDict(extra="ignore")

    sub: Literal["demo-operator", "demo-approver"]


class DemoClock:
    """When the sandbox was last reset and when it will be next."""

    def __init__(self, interval_min: int, now: Callable[[], datetime] = lambda: datetime.now(UTC)):
        self.interval = timedelta(minutes=interval_min)
        self._now = now
        self.last_reset = now()

    def mark_reset(self) -> None:
        self.last_reset = self._now()

    def as_dict(self) -> dict[str, Any]:
        return {"interval_min": int(self.interval.total_seconds() // 60),
                "last_reset_at": self.last_reset.isoformat(),
                "next_reset_at": (self.last_reset + self.interval).isoformat()}


def demo_router(settings: Settings, limit: Callable[[Callable[..., Any]], Any]) -> APIRouter:
    router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

    @router.post("/token")
    @limit
    async def demo_token(request: Request, body: DemoTokenRequest) -> dict[str, object]:
        """A short-lived token for one of the two fixed demo identities."""
        return {
            "access_token": issue_dev_token(
                settings, body.sub, DEMO_ROLES[body.sub], ttl_s=settings.demo_token_ttl_s
            ),
            "token_type": "bearer",
            "expires_in": settings.demo_token_ttl_s,
        }

    return router


def start_reset_schedule(settings: Settings, clock: DemoClock,
                         reset: Callable[[Settings], object]) -> object:
    """Reset the sandbox every ``demo_reset_interval_min`` in a background thread."""
    from apscheduler.schedulers.background import BackgroundScheduler

    def job() -> None:
        reset(settings)
        clock.mark_reset()

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(job, "interval", minutes=settings.demo_reset_interval_min,
                      id="demo-reset", max_instances=1, coalesce=True)
    scheduler.start()
    return scheduler
