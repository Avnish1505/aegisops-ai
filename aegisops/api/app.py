"""FastAPI application factory and cross-cutting HTTP protections."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, cast

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import create_engine, select
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
from aegisops.api.console import TicketBook, alert_areas, console_router
from aegisops.api.schemas import (
    DecisionDispositionRequest,
    DevTokenRequest,
    ErrorResponse,
    ReadReportRequest,
    ScenarioDecisionRequest,
    TranslateNoteRequest,
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
from aegisops.communication.reporter import Reporter
from aegisops.core.config import Settings
from aegisops.core.logging import configure_logging, request_id_var
from aegisops.domain.canonical import sha256_hex
from aegisops.domain.models import DecisionResult, Scenario
from aegisops.geodata.labels import Labeller
from aegisops.infrastructure.decision_store import record_decision, serialize_decision
from aegisops.infrastructure.llm_decision_engine import LLMDecisionEngine
from aegisops.infrastructure.retrieval_engine import RetrievalEngine
from aegisops.infrastructure.rule_based_engine import RuleBasedDecisionEngine
from aegisops.intake.constraints import ConstraintTranslator
from aegisops.intake.gazetteer import DEFAULT_GAZETTEER, Gazetteer
from aegisops.intake.reader import Reader, to_incident
from aegisops.llm.client import LLMClient, LLMError, LLMOutputError
from aegisops.planning.osrm import OSRMProvider
from aegisops.planning.travel import StraightLineProvider, TravelTimeMatrix, TravelTimeProvider
from aegisops.telemetry import configure_tracing, current_traceparent, step_span
from backend.db.models import Alert, Approval, Base, Decision, Exercise, User

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    travel_provider: TravelTimeProvider | None = None,
    token_verifier: TokenVerifier | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    """Build the API with injected configuration for deterministic testing."""
    active_settings = settings or Settings()
    check_secret_configuration(active_settings)
    configure_logging(active_settings.debug)
    configure_tracing(active_settings.otel_endpoint, active_settings.otel_service_name)
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
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "traceparent"],
        expose_headers=["traceparent"],
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
                detail="Request validation failed.",
                request_id=request_id,
                errors=[
                    {
                        "loc": [str(part) for part in error.get("loc", ())],
                        "message": str(error.get("msg", "")).removeprefix("Value error, "),
                    }
                    for error in exc.errors()
                ],
            ).model_dump(exclude_none=True),
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

    llm = llm_client or LLMClient(active_settings)
    travel = travel_provider or _default_travel_provider(active_settings)
    decision_service = DecisionService(
        {
            "rule_based": RuleBasedDecisionEngine(),
            "llm_rag": LLMDecisionEngine(
                RetrievalEngine(active_settings.knowledge_base_path), llm=llm
            ),
        },
        travel,
    )

    gazetteer = Gazetteer.load(DEFAULT_GAZETTEER)
    app.include_router(
        console_router(
            session_factory, active_settings, llm, TicketBook(), Labeller(gazetteer), travel
        )
    )
    reader = Reader(llm, gazetteer)
    translator = ConstraintTranslator(llm, gazetteer)
    reporter = Reporter(llm)

    def require_llm() -> None:
        if not llm.available:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No LLM is configured (set AEGISOPS_LLM_API_KEY).",
            )

    @app.post("/api/v1/intake/read", tags=["intake"])
    async def read_report(
        request: Request,
        response: Response,
        request_body: ReadReportRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, object]:
        """Free-text report -> grounded incident candidate (nothing is planned or stored)."""
        del principal
        require_llm()
        with step_span("read") as span:
            try:
                result = reader.read(request_body.report)
            except (LLMError, LLMOutputError) as error:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Reader failed: {error}"
                ) from error
            span.set_attribute("aegisops.fields_dropped", len(result.candidate.dropped))
            traceparent = current_traceparent()
        incident = to_incident(result.candidate, "INC-preview")
        if traceparent:
            response.headers["traceparent"] = traceparent
        return {
            "traceparent": traceparent,
            "candidate": result.candidate.model_dump(mode="json"),
            "incident_preview": incident.model_dump(mode="json") if incident else None,
            "llm": {
                "model": result.record.model,
                "prompt_version": result.record.prompt_version,
                "input_tokens": result.record.input_tokens,
                "output_tokens": result.record.output_tokens,
                "latency_s": round(result.record.latency_s, 3),
                "cost_usd": result.record.cost_usd,
            },
        }

    @app.post("/api/v1/constraints/translate", tags=["intake"])
    async def translate_constraint(
        request: Request,
        request_body: TranslateNoteRequest,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, object]:
        """Operator note -> one proposed constraint. The solver only uses it once the operator
        confirms it by sending it back in a decision request's ``constraints``."""
        del principal
        require_llm()
        try:
            result = translator.translate(request_body.note, request_body.scenario)
        except (LLMError, LLMOutputError) as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Translator failed: {error}"
            ) from error
        return result.proposal.model_dump(mode="json")

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

    @app.get("/api/v1/alerts", tags=["alerts"])
    @limiter.limit(active_settings.rate_limit)
    async def list_alerts(
        request: Request,
        source: Literal["sachet", "usgs", "gdacs"] | None = None,
        limit: int = Query(default=25, ge=1, le=200),
    ) -> list[dict[str, object]]:
        """Latest ingested alerts (summaries; the stored raw payload is not returned)."""
        query = select(Alert).order_by(Alert.sent_at.desc().nulls_last(), Alert.id.desc())
        if source is not None:
            query = query.where(Alert.source == source)
        with session_factory() as session:
            return [
                {
                    "source": alert.source,
                    "identifier": alert.identifier,
                    "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
                    "fetched_at": alert.fetched_at.isoformat(),
                    "event": alert.event,
                    "severity": alert.severity,
                    "headline": alert.headline,
                    "area_desc": alert.area_desc,
                    "location": (
                        {"lat": alert.location[0], "lon": alert.location[1]}
                        if alert.location
                        else None
                    ),
                    "areas": alert_areas(alert.parsed),
                }
                for alert in session.scalars(query.limit(limit))
            ]

    @app.get("/api/v1/exercises", tags=["scenarios"])
    @limiter.limit(active_settings.rate_limit)
    async def list_exercises(request: Request) -> list[dict[str, object]]:
        with session_factory() as session:
            return [
                {
                    "id": exercise.id,
                    "name": exercise.name,
                    "description": exercise.description,
                    "incidents": len(cast(list[object], exercise.scenario["incidents"])),
                    "resources": len(cast(list[object], exercise.scenario["resources"])),
                    "scenario_sha256": exercise.scenario_sha256,
                }
                for exercise in session.scalars(select(Exercise).order_by(Exercise.id))
            ]

    @app.get("/api/v1/exercises/{exercise_id}", tags=["scenarios"])
    @limiter.limit(active_settings.rate_limit)
    async def get_exercise(request: Request, exercise_id: str) -> dict[str, object]:
        with session_factory() as session:
            exercise = session.get(Exercise, exercise_id)
            if exercise is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found."
                )
            return exercise.scenario

    @app.post("/api/v1/decisions", tags=["decisions"])
    async def create_decision(
        request: Request,
        request_body: ScenarioDecisionRequest,
        principal: Annotated[Principal, Depends(require_operator)],
        engine: Literal["solver", "rule_based", "llm_rag"] = "solver",
        traceparent: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        """Plan and verify. A ``traceparent`` header (e.g. from ``/intake/read``) puts this
        decision in the same trace as the report that led to it."""
        scenario: Scenario = (
            request_body.scenario or generate_scenario(seed=request_body.seed)
        )
        with step_span("plan", traceparent=traceparent, engine=engine) as span:
            outcome = decision_service.decide(scenario, engine, request_body.constraints)
            with session_factory.begin() as session:
                decision = record_decision(
                    session, scenario, outcome, proposer=principal.sub,
                    trace_parent=current_traceparent(),
                )
                span.set_attributes({"aegisops.decision_id": decision.id,
                                     "aegisops.status": decision.status})
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

    @app.post("/api/v1/decisions/{decision_id}/drafts", tags=["decisions"])
    async def draft_reports(
        request: Request,
        decision_id: int,
        principal: Annotated[Principal, Depends(require_operator)],
    ) -> dict[str, object]:
        """SITREP and CAP 1.2 drafts for a stored decision. Returned for review only: nothing is
        published, and each draft says whether every number in it passed the verifier."""
        with session_factory.begin() as session:
            decision = session.get(Decision, decision_id)
            if decision is None or decision.scenario is None or decision.travel_times is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found."
                )
            scenario = Scenario.model_validate(decision.scenario)
            plan = DecisionResult.model_validate(
                {
                    "scenario_id": decision.scenario_id,
                    "engine": decision.engine,
                    "status": decision.status,
                    "assignments": decision.assignments or [],
                    "unmet_requirements": decision.unmet_requirements or [],
                    "safety_findings": decision.safety_findings or [],
                    "coverage": decision.coverage,
                    "decision_trace": decision.decision_trace,
                }
            )
            with step_span("communicate", traceparent=decision.trace_parent,
                           decision_id=decision.id):
                drafts = reporter.draft(
                    plan, scenario, TravelTimeMatrix.model_validate(decision.travel_times)
                )
            append_event(
                session,
                actor=principal.sub,
                type="drafts_generated",
                payload={
                    "decision_id": decision.id,
                    "sitrep_sha256": sha256_hex(drafts.sitrep.document),
                    "cap_sha256": sha256_hex(drafts.cap.document),
                    "sitrep_numbers_verified": drafts.sitrep.numbers_verified,
                    "cap_numbers_verified": drafts.cap.numbers_verified,
                    "sources": [drafts.sitrep.source, drafts.cap.source],
                },
            )
        return {
            "decision_id": decision_id,
            "sitrep": drafts.sitrep.model_dump(mode="json"),
            "cap": drafts.cap.model_dump(mode="json"),
            "llm_calls": len(drafts.records),
            "cost_usd": sum(record.cost_usd for record in drafts.records),
        }

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
            with step_span("decide", traceparent=decision.trace_parent,
                           decision_id=decision.id, action=request_body.action):
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
                    reason_code=request_body.reason_code,
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
                        "reason_code": request_body.reason_code,
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
                    "reason_code": request_body.reason_code,
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


def _default_travel_provider(settings: Settings) -> TravelTimeProvider:
    if settings.osrm_url:
        return OSRMProvider(settings.osrm_url, profile=settings.osrm_profile)
    return StraightLineProvider()
