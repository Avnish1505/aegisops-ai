"""FastAPI application factory and cross-cutting HTTP protections."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Literal, Protocol, cast

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT, HTTP_500_INTERNAL_SERVER_ERROR

from aegisops.api.schemas import (
    DecisionDispositionRequest,
    ErrorResponse,
    ScenarioDecisionRequest,
)
from aegisops.api.security import require_operator
from aegisops.application.roles import UserRole
from aegisops.application.scenario_service import generate_scenario
from aegisops.core.config import Settings
from aegisops.core.logging import configure_logging, request_id_var
from aegisops.domain.models import DecisionResult, Scenario
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from backend.db.models import Approval, AuditLog, Base, Decision, User

logger = logging.getLogger(__name__)


class DecisionEngine(Protocol):
    def recommend(self, scenario: Scenario) -> DecisionResult: ...


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API with injected configuration for deterministic testing."""
    active_settings = settings or Settings()
    configure_logging(active_settings.debug)
    app = FastAPI(
        title=active_settings.application_name,
        version=active_settings.version,
        description=(
            "Human-supervised crisis recommendation API. "
            "It never autonomously dispatches resources."
        ),
        docs_url="/docs" if active_settings.debug else None,
        redoc_url=None,
    )
    engine_options: dict[str, object] = {}
    if active_settings.database_url.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
    if active_settings.database_url == "sqlite://":
        engine_options["poolclass"] = StaticPool
    database_engine = create_engine(active_settings.database_url, **engine_options)
    session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
    if active_settings.environment == "test":
        Base.metadata.create_all(database_engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in active_settings.cors_origins],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.state.settings = active_settings
    app.state.session_factory = session_factory

    # Rate limiting setup
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response as StarletteResponse

    limiter = Limiter(key_func=get_remote_address, default_limits=[])
    app.state.limiter = limiter
    exception_handler = cast(
        Callable[[StarletteRequest, Exception], StarletteResponse | Awaitable[StarletteResponse]],
        _rate_limit_exceeded_handler,
    )
    app.add_exception_handler(RateLimitExceeded, exception_handler)

    @app.middleware("http")
    async def security_and_observability_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            started = time.perf_counter()
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            logger.info(
                "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started) * 1000,
            )
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID")
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            content=ErrorResponse(
                detail="Request validation failed.", request_id=request_id
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = request.headers.get("X-Request-ID")
        logger.exception("unhandled_error request_id=%s", request_id)
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                detail="Internal server error.", request_id=request_id
            ).model_dump(),
        )

    engines: dict[str, DecisionEngine] = {
        "rule_based": RuleBasedDecisionEngine(),
        "llm_rag": LLMDecisionEngine(
            RetrievalEngine(Path(__file__).parents[2] / "knowledge")
        ),
    }

    @app.get("/health/live", tags=["health"])
    @limiter.limit(active_settings.rate_limit)
    async def liveness(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    @limiter.limit(active_settings.rate_limit)
    async def readiness(request: Request) -> dict[str, str]:
        return {"status": "ready", "environment": active_settings.environment}

    @app.get("/metrics", include_in_schema=False)
    @limiter.limit(active_settings.rate_limit)
    async def metrics(request: Request) -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/v1/scenarios", tags=["scenarios"])
    @limiter.limit(active_settings.rate_limit)
    async def get_scenario(request: Request, seed: int | None = None) -> dict[str, object]:
        return cast(dict[str, object], generate_scenario(seed=seed).model_dump(mode="json"))

    @app.post("/api/v1/decisions", tags=["decisions"])
    async def create_decision(
        request: Request,
        request_body: ScenarioDecisionRequest,
        role: Annotated[UserRole, Depends(require_operator)],
        engine: Literal["rule_based", "llm_rag"] = "rule_based",
    ) -> dict[str, object]:
        scenario: Scenario = (
            request_body.scenario or generate_scenario(seed=request_body.seed)
        )
        result: DecisionResult = engines[engine].recommend(scenario)

        with session_factory.begin() as session:
            decision = Decision(
                scenario_id=result.scenario_id,
                engine=result.engine,
                status=result.status.value,
                requires_human_approval=result.requires_human_approval,
                advisory_confidence=result.advisory_confidence,
                decision_trace=result.decision_trace,
            )
            session.add(decision)
            session.flush()
            session.add(
                AuditLog(
                    user_id=None,
                    action="decision_created",
                    table_name="decisions",
                    record_id=str(decision.id),
                    change_data={"actor": role.name.lower(), "scenario_id": result.scenario_id},
                )
            )
            response = cast(dict[str, object], result.model_dump(mode="json"))
            response["decision_id"] = decision.id
        return response

    @app.post("/api/v1/decisions/{decision_id}/disposition", tags=["decisions"])
    async def create_disposition(
        request: Request,
        decision_id: int,
        request_body: DecisionDispositionRequest,
        role: Annotated[UserRole, Depends(require_operator)],
    ) -> dict[str, object]:
        with session_factory.begin() as session:
            decision = session.get(Decision, decision_id)
            if decision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Decision not found.",
                )
            if request_body.action == "approve" and decision.status == "blocked":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Blocked decisions cannot be approved.",
                )
            actor_name = f"development-{role.name.lower()}"
            actor = session.query(User).filter_by(username=actor_name).one_or_none()
            if actor is None:
                actor = User(
                    username=actor_name,
                    email=f"{actor_name}@local.invalid",
                    hashed_password="development-role-token",
                )
                session.add(actor)
                session.flush()
            approval = Approval(
                decision_id=decision.id,
                user_id=actor.id,
                approved=request_body.action == "approve",
            )
            session.add(approval)
            session.flush()
            audit = AuditLog(
                user_id=actor.id,
                action=(
                    "decision_approved" if request_body.action == "approve" else "decision_rejected"
                ),
                table_name="decisions",
                record_id=str(decision.id),
                change_data={
                    "actor": role.name.lower(),
                    "action": request_body.action,
                    "reason": request_body.reason,
                },
            )
            session.add(audit)
            session.flush()
            return {
                "decision_id": decision.id,
                "disposition_id": approval.id,
                "action": request_body.action,
                "timestamp": audit.timestamp.isoformat(),
            }

    @app.get("/health", include_in_schema=False)
    @limiter.limit(active_settings.rate_limit)
    async def legacy_health(request: Request) -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/scenario", include_in_schema=False)
    @limiter.limit(active_settings.rate_limit)
    async def legacy_scenario(request: Request, seed: int | None = None) -> dict[str, object]:
        return cast(dict[str, object], generate_scenario(seed=seed).model_dump(mode="json"))

    @app.post("/simulate", include_in_schema=False)
    async def legacy_simulate(
        request: Request,
        request_body: ScenarioDecisionRequest,
        role: Annotated[UserRole, Depends(require_operator)],
        engine: Literal["rule_based", "llm_rag"] = "rule_based",
    ) -> dict[str, object]:
        scenario: Scenario = (
            request_body.scenario or generate_scenario(seed=request_body.seed)
        )
        del role
        result: DecisionResult = engines[engine].recommend(scenario)
        return cast(dict[str, object], result.model_dump(mode="json"))

    return app


app = create_app()