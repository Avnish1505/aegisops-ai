"""LLM-direct allocation engine (the experiment arm), with a safe blocked fallback.

Under the target pipeline the LLM does not allocate; the CP-SAT solver does. This engine stays as
the comparison arm for ``evals/llm_vs_solver.py`` and as the ``llm_rag`` option in the API, where
every proposal goes through the verifier and a failure blocks. It calls the model through the one
shared client (``aegisops.llm.client``), with the output constrained to ``LLMAllocation``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from aegisops.application.ports import RetrievalPort
from aegisops.core.config import Settings
from aegisops.domain.models import (
    Assignment,
    DecisionResult,
    DecisionStatus,
    Evidence,
    SafetyFinding,
    Scenario,
    UnmetRequirement,
)
from aegisops.infrastructure.prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    PromptTemplate,
    get_prompt_template,
)
from aegisops.llm.client import LLMClient, LLMError, LLMOutputError, Prompt
from aegisops.planning.constraints import PlanningConstraint
from aegisops.planning.travel import StraightLineProvider, TravelTimeMatrix


class LLMAllocation(BaseModel):
    """What the model is asked for. Status, findings and coverage are never taken from it."""

    model_config = ConfigDict(extra="ignore")

    scenario_id: str
    requires_human_approval: bool
    assignments: list[Assignment]
    unmet_requirements: list[UnmetRequirement]
    decision_trace: list[str]


class LLMDecisionEngine:
    """Create human-approved advisory results from an LLM's allocation."""

    name = "nvidia_nim_v1"
    attempts = 2

    def __init__(
        self,
        retrieval_engine: RetrievalPort,
        *,
        llm: LLMClient | None = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        max_tokens: int = 4_096,
    ) -> None:
        self._retrieval_engine = retrieval_engine
        self._llm = llm or LLMClient(Settings())
        self._prompt: PromptTemplate = get_prompt_template(prompt_version)
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._llm.model

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
        if not self._llm.available:
            return self._blocked_result(
                scenario, evidence, "No LLM credentials are configured."
            )
        matrix = travel_times or StraightLineProvider().matrix(scenario)
        for _ in range(self.attempts):
            try:
                return self._request_decision(scenario, snippets, evidence, matrix, constraints)
            except (LLMError, LLMOutputError, ValueError):
                continue
        return self._blocked_result(
            scenario, evidence, "LLM response validation failed."
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
        user = json.dumps(
            {
                "scenario": scenario.model_dump(mode="json"),
                "travel_minutes": travel_times.minutes,
                "constraints": [item.model_dump(mode="json") for item in constraints],
                "knowledge_snippets": snippets,
                "evidence": [item.model_dump(mode="json") for item in evidence],
            }
        )
        proposal = self._llm.complete_json(
            Prompt("allocation", self._prompt.version, self._prompt.system_message, user),
            LLMAllocation,
            max_tokens=self._max_tokens,
        ).value
        if proposal.scenario_id != scenario.scenario_id:
            raise ValueError("LLM response scenario_id does not match the request")
        # No repair here: every claim (units, travel times, citations, the approval flag) is
        # judged by verification.verifier, and the operator sees what the model actually said.
        return DecisionResult(
            scenario_id=scenario.scenario_id,
            engine=self.name,
            # The model's own status and findings are never asked for; the verifier and the
            # safety gates decide both. Its approval flag is kept so the verifier can flag it.
            status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
            requires_human_approval=proposal.requires_human_approval,
            assignments=proposal.assignments,
            unmet_requirements=proposal.unmet_requirements,
            safety_findings=[],
            coverage=0.0,  # recomputed by DecisionService from the assignments
            decision_trace=[
                *proposal.decision_trace,
                "Proposal returned unmodified for deterministic verification.",
            ],
            evidence_ids=[item.id for item in evidence],
            evidence=evidence,
            prompt_version=self._prompt.version,
            model_version=self.model,
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
                    message="LLM decision generation failed; human escalation is required.",
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
            model_version=self.model,
        )
