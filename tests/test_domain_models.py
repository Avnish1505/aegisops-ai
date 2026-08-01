"""Unit tests for domain models."""

import pytest
from pydantic import ValidationError

from aegisops.domain.models import (
    Assignment,
    DecisionResult,
    DecisionStatus,
    Evidence,
    Incident,
    IncidentType,
    Resource,
    ResourceType,
    SafetyFinding,
    Scenario,
    Severity,
    UnmetRequirement,
)


def test_evidence_valid():
    """Test that a valid Evidence instance can be created."""
    evidence = Evidence(
        id="ev1",
        description="Witness report",
        source="Eyewitness",
        confidence=0.9,
        timestamp="2024-01-01T12:00:00Z",
        incident_id="inc1",
    )
    assert evidence.id == "ev1"
    assert evidence.description == "Witness report"
    assert evidence.source == "Eyewitness"
    assert evidence.confidence == 0.9
    assert evidence.timestamp == "2024-01-01T12:00:00Z"
    assert evidence.incident_id == "inc1"


def test_evidence_incident_id_validation():
    """Test that incident_id cannot be an empty string if provided."""
    with pytest.raises(ValidationError, match="incident_id must not be empty if provided"):
        Evidence(
            id="ev1",
            description="Witness report",
            source="Eyewitness",
            confidence=0.9,
            incident_id="",  # empty string
        )

    # None is allowed
    evidence = Evidence(
        id="ev1",
        description="Witness report",
        source="Eyewitness",
        confidence=0.9,
        incident_id=None,
    )
    assert evidence.incident_id is None


def test_evidence_confidence_bounds():
    """Test that confidence must be between 0 and 1 inclusive."""
    with pytest.raises(ValidationError):
        Evidence(
            id="ev1",
            description="Witness report",
            source="Eyewitness",
            confidence=1.5,  # too high
        )

    with pytest.raises(ValidationError):
        Evidence(
            id="ev1",
            description="Witness report",
            source="Eyewitness",
            confidence=-0.1,  # too low
        )

    # boundaries are allowed
    Evidence(id="ev1", description="Witness", source="Eyewitness", confidence=0.0)
    Evidence(id="ev1", description="Witness", source="Eyewitness", confidence=1.0)


def test_evidence_id_and_description_validation():
    """Test that id and description must be non-empty and match pattern."""
    with pytest.raises(ValidationError):
        Evidence(id="", description="Witness", source="Eyewitness", confidence=0.5)

    with pytest.raises(ValidationError):
        Evidence(id="ev1", description="", source="Eyewitness", confidence=0.5)

    with pytest.raises(ValidationError):
        Evidence(
            id="ev1@", description="Witness", source="Eyewitness", confidence=0.5
        )  # invalid char


def test_decision_result_evidence_ids_default():
    """Test that DecisionResult evidence_ids defaults to an empty list."""
    assignment = Assignment(
        incident_id="inc1",
        resource_id="res1",
        resource_type=ResourceType.AMBULANCE,
        travel_minutes=5.0,
    )
    unmet = UnmetRequirement(
        incident_id="inc1",
        resource_type=ResourceType.FIRE_UNIT,
        quantity=1,
        severity=Severity.HIGH,
    )
    safety = SafetyFinding(
        code="SF001",
        severity="medium",
        message="Test safety finding",
        incident_id="inc1",
    )
    decision = DecisionResult(
        scenario_id="sc1",
        engine="test_engine",
        status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
        assignments=[assignment],
        unmet_requirements=[unmet],
        safety_findings=[safety],
        advisory_confidence=0.8,
        decision_trace=["step1", "step2"],
    )
    assert decision.evidence_ids == []
    assert decision.evidence == []


def test_decision_result_evidence_ids_can_be_set():
    """Test that DecisionResult evidence_ids can be provided and are stored."""
    assignment = Assignment(
        incident_id="inc1",
        resource_id="res1",
        resource_type=ResourceType.AMBULANCE,
        travel_minutes=5.0,
    )
    decision = DecisionResult(
        scenario_id="sc1",
        engine="test_engine",
        status=DecisionStatus.REQUIRES_HUMAN_APPROVAL,
        assignments=[assignment],
        unmet_requirements=[],
        safety_findings=[],
        advisory_confidence=0.8,
        decision_trace=["step1"],
        evidence_ids=["ev1", "ev2"],
    )
    assert decision.evidence_ids == ["ev1", "ev2"]


def test_assignment_evidence_ids_default_for_compatibility():
    assignment = Assignment(
        incident_id="inc1",
        resource_id="res1",
        resource_type=ResourceType.AMBULANCE,
        travel_minutes=5.0,
    )

    assert assignment.evidence_ids == []


# Existing model tests to ensure we didn't break anything
def test_incident_valid():
    incident = Incident(
        id="inc1",
        type=IncidentType.MEDICAL,
        severity=Severity.MEDIUM,
        location=(10.0, 20.0),
        people_affected=10,
        reported_at_min=0,
        resources_needed={ResourceType.AMBULANCE: 2},
    )
    assert incident.id == "inc1"


def test_resource_valid():
    resource = Resource(
        id="res1",
        type=ResourceType.AMBULANCE,
        location=(10.0, 20.0),
    )
    assert resource.id == "res1"


def test_scenario_valid():
    incident = Incident(
        id="inc1",
        type=IncidentType.MEDICAL,
        severity=Severity.MEDIUM,
        location=(10.0, 20.0),
        people_affected=10,
        reported_at_min=0,
        resources_needed={ResourceType.AMBULANCE: 2},
    )
    resource = Resource(
        id="res1",
        type=ResourceType.AMBULANCE,
        location=(30.0, 40.0),
    )
    scenario = Scenario(
        scenario_id="sc1",
        incidents=[incident],
        resources=[resource],
    )
    assert scenario.scenario_id == "sc1"
