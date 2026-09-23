"""FastAPI application factory and cross-cutting HTTP protections."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.status import HTTP_422_UNPROCESSABLE_CONTENT, HTTP_500_INTERNAL_SERVER_ERROR

from aegisops.api.auth import (
    Principal,
    TokenVerifier,
    check_secret_configuration,
    issue_dev_token,
    require_operator,
    require_viewer,
)
from aegisops.api.schemas import (
    DecisionDispositionRequest,
    DevTokenRequest,
    ErrorResponse,
    ScenarioDecisionRequest,
)
from aegisops.application.decision_service import DecisionService
from aegisops.application.roles import UserRole
from aegisops.application.scenario_service import generate_scenario
from aegisops.audit.event_log import (
    append_event,
    approval_record_sha256,
    record_ref,
    verify_chain,
)
from aegisops.core.config import Settings
from aegisops.core.logging import configure_logging, request_id_var
from aegisops.domain.canonical import sha256_hex
from aegisops.domain.models import Scenario
from aegisops.infrastructure.decision_store import record_decision, serialize_decision
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from aegisops.planning.travel import EuclideanProvider, TravelTimeProvider
from backend.db.models import Approval, Base, Decision, User

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    travel_provider: TravelTimeProvider | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    """Build the API with injected configuration for deterministic testing."""
    active_settings = settings or Settings()
    check_secret_configuration(active_settings)
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
    app.state.token_verifier = token_verifier or TokenVerifier(active_settings)
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

    decision_service = DecisionService(
        {
            "rule_based": RuleBasedDecisionEngine(),
            "llm_rag": LLMDecisionEngine(RetrievalEngine(active_settings.knowledge_base_path)),
        },
        travel_provider or EuclideanProvider(),
    )

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
        principal: Annotated[Principal, Depends(require_operator)],
        engine: Literal["solver", "rule_based", "llm_rag"] = "solver",
    ) -> dict[str, object]:
        scenario: Scenario = (
            request_body.scenario or generate_scenario(seed=request_body.seed)
        )
        outcome = decision_service.decide(scenario, engine, request_body.constraints)

        with session_factory.begin() as session:
            decision = record_decision(session, scenario, outcome, proposer=principal.sub)
            return serialize_decision(decision)

    @app.get("/api/v1/decisions/{decision_id}", tags=["decisions"])
    async def get_decision(
        request: Request,
        decision_id: int,
        principal: Annotated[Principal, Depends(require_viewer)],
    ) -> dict[str, object]:
        del principal
        with session_factory() as session:
            decision = session.get(Decision, decision_id)
            if decision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Decision not found.",
                )
            return serialize_decision(decision)

    @app.post("/api/v1/decisions/{decision_id}/disposition", tags=["decisions"])
    async def create_disposition(
        request: Request,
        decision_id: int,
        request_body: DecisionDispositionRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, object]:
        approving = request_body.action == "approve"
        if approving and not principal.role.at_least(UserRole.APPROVER):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approving requires the approver role or higher.",
            )
        with session_factory.begin() as session:
            decision = session.get(Decision, decision_id)
            if decision is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Decision not found.",
                )
            if approving and decision.status == "blocked":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Blocked decisions cannot be approved.",
                )
            if approving and decision.proposer_sub == principal.sub:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="proposer cannot approve",
                )
            actor_name = principal.sub
            actor = session.query(User).filter_by(username=actor_name).one_or_none()
            if actor is None:
                actor = User(
                    username=actor_name,
                    email=f"{sha256_hex(actor_name)[:32]}@identity.invalid",
                    hashed_password="external-identity",
                )
                session.add(actor)
                session.flush()
            approval = Approval(
                decision_id=decision.id,
                user_id=actor.id,
                approved=approving,
            )
            session.add(approval)
            session.flush()
            event = append_event(
                session,
                actor=actor_name,
                type="disposition_recorded",
                payload={
                    "decision_id": decision.id,
                    "approval_id": approval.id,
                    "action": request_body.action,
                    "reason": request_body.reason,
                    "record": record_ref(
                        "approvals", approval.id, approval_record_sha256(approval)
                    ),
                },
            )
            return {
                "decision_id": decision.id,
                "disposition_id": approval.id,
                "action": request_body.action,
                "timestamp": event.ts,
            }

    if active_settings.environment == "development":

        @app.post("/api/v1/dev/token", tags=["development"])
        @limiter.limit(active_settings.rate_limit)
        async def dev_token(request: Request, request_body: DevTokenRequest) -> dict[str, object]:
            """Development only: mint a signed token for any subject and role."""
            return {
                "access_token": issue_dev_token(
                    active_settings, request_body.sub, request_body.role
                ),
                "token_type": "bearer",
                "expires_in": active_settings.dev_token_ttl_s,
            }

    @app.get("/api/v1/audit/verify", tags=["audit"])
    async def verify_audit_chain(
        request: Request,
        principal: Annotated[Principal, Depends(require_viewer)],
    ) -> dict[str, object]:
        del principal
        with session_factory() as session:
            return verify_chain(session).as_dict()

    return app
