"""NVIDIA NIM-backed decision engine with a safe blocked fallback."""

from __future__ import annotations

import json
import os

import httpx
from pydantic import ValidationError

from aegisops.application.ports import RetrievalPort
from aegisops.domain.models import (
    Assignment,
    DecisionResult,
    DecisionStatus,
    Evidence,
    SafetyFinding,
    Scenario,
)
from aegisops.domain.policy import validate_llm_recommendation

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
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self._client = client or httpx.Client(timeout=10.0)
        self._model = model or os.getenv("NVIDIA_NIM_MODEL", DEFAULT_NIM_MODEL)

    def recommend(self, scenario: Scenario) -> DecisionResult:
        """Return a validated NIM result or block after one retry."""
        query = " ".join(
            f"{incident.severity} {incident.type}"
            for incident in scenario.incidents
        )
        snippets, evidence = self._retrieve_with_provenance(query)
        if not self._api_key:
            return self._blocked_result(
                scenario, evidence, "NVIDIA API credentials are unavailable."
            )

        for _ in range(2):
            try:
                return self._request_decision(scenario, snippets, evidence)
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
        self, scenario: Scenario, snippets: list[str], evidence: list[Evidence]
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
                        "content": (
                            "Return JSON only. The JSON must validate as an AegisOps "
                            "DecisionResult. It must require human approval and must never "
                            "describe dispatch execution. Reference only supplied evidence IDs "
                            "in DecisionResult.evidence_ids and Assignment.evidence_ids."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "scenario": scenario.model_dump(mode="json"),
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
        result = DecisionResult.model_validate(json.loads(content))
        if result.scenario_id != scenario.scenario_id:
            raise ValueError("NIM response scenario_id does not match the request")
        assignments, unmet, findings, blocked = validate_llm_recommendation(
            result.assignments, result.requires_human_approval, scenario
        )
        assignments = self._map_assignment_evidence(assignments, evidence)
        coverage = 1 - (
            sum(item.quantity for item in unmet)
            / max(1, len(assignments) + sum(item.quantity for item in unmet))
        )
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            engine=self.name,
            status=(
                DecisionStatus.BLOCKED
                if blocked
                else DecisionStatus.REQUIRES_HUMAN_APPROVAL
            ),
            requires_human_approval=True,
            assignments=assignments,
            unmet_requirements=unmet,
            safety_findings=findings,
            advisory_confidence=round(max(0.0, min(1.0, coverage)), 2),
            decision_trace=result.decision_trace
            + ["Revalidated LLM assignments and safety state against the scenario."],
            evidence_ids=[item.id for item in evidence],
            evidence=evidence,
        )

    @staticmethod
    def _map_assignment_evidence(
        assignments: list[Assignment], evidence: list[Evidence]
    ) -> list[Assignment]:
        """Retain valid model citations, with all retrieved evidence as a legacy fallback."""
        available_ids = {item.id for item in evidence}
        fallback_ids = [item.id for item in evidence]
        return [
            assignment.model_copy(
                update={
                    "evidence_ids": [
                        evidence_id
                        for evidence_id in assignment.evidence_ids
                        if evidence_id in available_ids
                    ]
                    or fallback_ids
                }
            )
            for assignment in assignments
        ]

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
            advisory_confidence=0.0,
            decision_trace=[
                f"Retrieved {len(evidence)} local knowledge snippets.",
                reason,
                "No decision was produced; recommendation is blocked pending human review.",
            ],
            evidence_ids=[item.id for item in evidence],
            evidence=evidence,
        )
