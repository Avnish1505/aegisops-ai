"""NVIDIA NIM-backed decision engine with a safe blocked fallback."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from aegisops.application.ports import RetrievalPort
from aegisops.domain.models import (
    DecisionResult,
    DecisionStatus,
    Evidence,
    SafetyFinding,
    Scenario,
)
from aegisops.infrastructure.prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    PromptTemplate,
    get_prompt_template,
)
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.travel import EuclideanProvider, TravelTimeMatrix

NIM_CHAT_COMPLETIONS_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_NIM_MODEL = "meta/llama-3.1-8b-instruct"


class LLMDecisionEngine:
    """Create human-approved advisory results through NVIDIA NIM."""

    name = "nvidia_nim_v1"

    def __init__(
        self,
        retrieval_engine: RetrievalPort,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        model: str | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self._client = client or httpx.Client(timeout=10.0)
        self._model = model or os.getenv("NVIDIA_NIM_MODEL", DEFAULT_NIM_MODEL)
        self._prompt: PromptTemplate = get_prompt_template(prompt_version)

    def recommend(
        self,
        scenario: Scenario,
        travel_times: TravelTimeMatrix | None = None,
        constraints: Sequence[PlanningConstraint] = (),
    ) -> DecisionResult:
        """Return the model's proposal as-is for verification, or block after one retry."""
        query = " ".join(
            f"{incident.severity} {incident.type}"
            for incident in scenario.incidents
        )
        snippets, evidence = self._retrieve_with_provenance(query)
        if not self._api_key:
            return self._blocked_result(
                scenario, evidence, "NVIDIA API credentials are unavailable."
            )
        matrix = travel_times or EuclideanProvider().matrix(scenario)
        for _ in range(2):
            try:
                return self._request_decision(scenario, snippets, evidence, matrix, constraints)
            except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError):
                continue
        return self._blocked_result(
            scenario, evidence, "NVIDIA NIM response validation failed."
        )

    def _retrieve_with_provenance(self, query: str) -> tuple[list[str], list[Evidence]]:
        """Use structured retrieval when available, retaining legacy port compatibility."""
        retrieve_evidence = getattr(self._retrieval_engine, "retrieve_evidence", None)
        if callable(retrieve_evidence):
            evidence = retrieve_evidence(query)
            return [item.description for item in evidence], evidence
        snippets = self._retrieval_engine.retrieve(query)
        return snippets, [
            Evidence(
                id=f"retrieved-{index}",
                description=snippet,
                source="legacy_retrieval",
                confidence=1.0,
            )
            for index, snippet in enumerate(snippets, start=1)
        ]

    def _request_decision(
        self,
        scenario: Scenario,
        snippets: list[str],
        evidence: list[Evidence],
        travel_times: TravelTimeMatrix,
        constraints: Sequence[PlanningConstraint],
    ) -> DecisionResult:
        response = self._client.post(
            NIM_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
            },
            json={
                "model": self._model,
                "stream": False,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": self._prompt.system_message,
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "scenario": scenario.model_dump(mode="json"),
                                "travel_minutes": travel_times.minutes,
                                "constraints": [
                                    item.model_dump(mode="json") for item in constraints
                                ],
                                "knowledge_snippets": snippets,
                                "evidence": [item.model_dump(mode="json") for item in evidence],
                            }
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        proposal = DecisionResult.model_validate(json.loads(content))
        if proposal.scenario_id != scenario.scenario_id:
            raise ValueError("NIM response scenario_id does not match the request")
        # No repair here: every claim (units, travel times, citations, the approval flag) is
        # judged by verification.verifier, and the operator sees what the model actually said.
        return proposal.model_copy(
            update={
                "engine": self.name,
                # The model's own status and findings are untrusted text; the verifier and the
                # safety gates decide both.
                "status": DecisionStatus.REQUIRES_HUMAN_APPROVAL,
                "safety_findings": [],
                "decision_trace": [
                    *proposal.decision_trace,
                    "Proposal returned unmodified for deterministic verification.",
                ],
                "evidence_ids": [item.id for item in evidence],
                "evidence": evidence,
                "prompt_version": self._prompt.version,
                "model_version": self._model,
            }
        )

    def _blocked_result(
        self, scenario: Scenario, evidence: list[Evidence], reason: str
    ) -> DecisionResult:
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            engine=self.name,
            status=DecisionStatus.BLOCKED,
            assignments=[],
            unmet_requirements=[],
            safety_findings=[
                SafetyFinding(
                    code="NIM_DECISION_UNAVAILABLE",
                    severity="critical",
                    message="NVIDIA NIM decision generation failed; human escalation is required.",
                )
            ],
            coverage=0.0,
            decision_trace=[
                f"Retrieved {len(evidence)} local knowledge snippets.",
                reason,
                "No decision was produced; recommendation is blocked pending human review.",
            ],
            evidence_ids=[item.id for item in evidence],
            evidence=evidence,
            prompt_version=self._prompt.version,
            model_version=self._model,
        )
