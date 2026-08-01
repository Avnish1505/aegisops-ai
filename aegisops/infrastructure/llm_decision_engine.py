"""NVIDIA NIM-backed decision engine with a safe blocked fallback."""

from __future__ import annotations

import json
import os

import httpx
from pydantic import ValidationError

from aegisops.application.ports import RetrievalPort
from aegisops.domain.models import DecisionResult, DecisionStatus, SafetyFinding, Scenario
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
        snippets = self._retrieval_engine.retrieve(query)
        if not self._api_key:
            return self._blocked_result(
                scenario, len(snippets), "NVIDIA API credentials are unavailable."
            )

        for _ in range(2):
            try:
                return self._request_decision(scenario, snippets)
            except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError):
                continue
        return self._blocked_result(
            scenario, len(snippets), "NVIDIA NIM response validation failed."
        )

    def _request_decision(self, scenario: Scenario, snippets: list[str]) -> DecisionResult:
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
                            "describe dispatch execution."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "scenario": scenario.model_dump(mode="json"),
                                "knowledge_snippets": snippets,
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
            evidence_ids=result.evidence_ids,
        )

    def _blocked_result(
        self, scenario: Scenario, snippet_count: int, reason: str
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
                f"Retrieved {snippet_count} local knowledge snippets.",
                reason,
                "No decision was produced; recommendation is blocked pending human review.",
            ],
        )
