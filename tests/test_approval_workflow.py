"""Tests for approval workflow functionality."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aegisops.domain.models import (
    ApprovalStatus,
    DecisionResult,
    Evidence,
)


def make_minimal_scenario() -> dict:
    """Create a minimal valid scenario for testing."""
    now = int(datetime.now(tz=UTC).timestamp())
    return {
        "scenario_id": "test-scenario-1",
        "incidents": [
            {
                "id": "inc-1",
                "type": "medical",
                "severity": "high",
                "location": [40.7128, -74.0060],
                "people_affected": 10,
                "reported_at_min": now - 60,
                "resources_needed": {"ambulance": 2},
            }
        ],
        "resources": [
            {
                "id": "res-1",
                "type": "ambulance",
                "location": [40.7138, -74.0050],
                "available": True,
            }
        ],
        "sim_start_min": now,
    }


def make_minimal_decision_result() -> dict:
    """Create a minimal valid decision result for testing."""
    scenario = make_minimal_scenario()
    return {
        "scenario_id": scenario["scenario_id"],
        "engine": "rule_based",
        "status": "requires_human_approval",
        "assignments": [
            {
                "incident_id": "inc-1",
                "resource_id": "res-1",
                "resource_type": "ambulance",
                "travel_minutes": 5.0,
            }
        ],
        "unmet_requirements": [],
        "safety_findings": [],
        "advisory_confidence": 0.85,
        "decision_trace": ["rule1", "rule2"],
        "evidence_ids": [],
    }


def test_approval_status_enum():
    """Test ApprovalStatus enum values."""
    assert ApprovalStatus.PENDING == "pending"
    assert ApprovalStatus.APPROVED == "approved"
    assert ApprovalStatus.REJECTED == "rejected"


def test_decision_result_default_approval_status():
    """Test that DecisionResult defaults to PENDING approval status."""
    decision_data = make_minimal_decision_result()
    decision = DecisionResult(**decision_data)
    assert decision.approval_status == ApprovalStatus.PENDING
    assert decision.approver_id is None
    assert decision.approved_at is None
    assert decision.rejection_reason is None


def test_decision_result_can_be_approved():
    """Test that DecisionResult can be set to APPROVED with required fields."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "approved",
            "approver_id": "op-123",
            "approved_at": "2023-01-01T12:00:00Z",
        }
    )
    decision = DecisionResult(**decision_data)
    assert decision.approval_status == ApprovalStatus.APPROVED
    assert decision.approver_id == "op-123"
    assert decision.approved_at == "2023-01-01T12:00:00Z"
    assert decision.rejection_reason is None


def test_decision_result_can_be_rejected():
    """Test that DecisionResult can be set to REJECTED with required fields."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "rejected",
            "approver_id": "op-123",
            "approved_at": "2023-01-01T12:00:00Z",
            "rejection_reason": "Insufficient resources",
        }
    )
    decision = DecisionResult(**decision_data)
    assert decision.approval_status == ApprovalStatus.REJECTED
    assert decision.approver_id == "op-123"
    assert decision.approved_at == "2023-01-01T12:00:00Z"
    assert decision.rejection_reason == "Insufficient resources"


def test_approved_decision_requires_approver_id():
    """Test that APPROVED status requires approver_id."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "approved",
            # Missing approver_id
            "approved_at": "2023-01-01T12:00:00Z",
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "approver_id must be set when approval_status is approved" in str(
        exc_info.value
    )


def test_approved_decision_requires_approved_at():
    """Test that APPROVED status requires approved_at."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "approved",
            "approver_id": "op-123",
            # Missing approved_at
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "approved_at must be set when approval_status is approved" in str(
        exc_info.value
    )


def test_approved_decision_rejection_reason_must_be_none():
    """Test that APPROVED status requires rejection_reason to be None."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "approved",
            "approver_id": "op-123",
            "approved_at": "2023-01-01T12:00:00Z",
            "rejection_reason": "Some reason",  # Should be None
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "rejection_reason must be None when approval_status is approved" in str(
        exc_info.value
    )


def test_rejected_decision_requires_rejection_reason():
    """Test that REJECTED status requires rejection_reason."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "rejected",
            "approver_id": "op-123",
            "approved_at": "2023-01-01T12:00:00Z",
            # Missing rejection_reason
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "rejection_reason must be set when approval_status is rejected" in str(
        exc_info.value
    )


def test_rejected_decision_requires_approver_id():
    """Test that REJECTED status requires approver_id."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "rejected",
            # Missing approver_id
            "approved_at": "2023-01-01T12:00:00Z",
            "rejection_reason": "Insufficient resources",
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "approver_id must be set when approval_status is rejected" in str(
        exc_info.value
    )


def test_rejected_decision_requires_approved_at():
    """Test that REJECTED status requires approved_at."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "rejected",
            "approver_id": "op-123",
            # Missing approved_at
            "rejection_reason": "Insufficient resources",
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    assert "approved_at must be set when approval_status is rejected" in str(
        exc_info.value
    )


def test_pending_decision_requires_none_for_approval_fields():
    """Test that pending decisions cannot contain disposition fields."""
    decision_data = make_minimal_decision_result()
    decision_data.update(
        {
            "approval_status": "pending",
            "approver_id": "op-123",  # Should be None
            "approved_at": "2023-01-01T12:00:00Z",  # Should be None
            "rejection_reason": "Some reason",  # Should be None
        }
    )
    with pytest.raises(ValidationError) as exc_info:
        DecisionResult(**decision_data)
    error_msg = str(exc_info.value)
    # Pydantic stops validation after first error, so we check for the first error that occurs.
    # The order is not guaranteed, but at least one field must be invalid.
    assert (
        "approver_id must be None when approval_status is pending" in error_msg
        or "approved_at must be None when approval_status is pending" in error_msg
        or "rejection_reason must be None when approval_status is pending" in error_msg
    )


def test_evidence_model():
    """Test that Evidence model works as expected."""
    evidence_data = {
        "id": "ev-1",
        "description": "Witness testimony",
        "source": "eyewitness-account",
        "confidence": 0.8,
        "timestamp": "2023-01-01T12:00:00Z",
        "incident_id": "inc-1",
    }
    evidence = Evidence(**evidence_data)
    assert evidence.id == "ev-1"
    assert evidence.description == "Witness testimony"
    assert evidence.source == "eyewitness-account"
    assert evidence.confidence == 0.8
    assert evidence.timestamp == "2023-01-01T12:00:00Z"
    assert evidence.incident_id == "inc-1"

    # Test without incident_id (should be optional)
    evidence_data_no_incident = evidence_data.copy()
    evidence_data_no_incident["incident_id"] = None
    evidence_no_incident = Evidence(**evidence_data_no_incident)
    assert evidence_no_incident.incident_id is None

    # Test with empty incident_id (should fail)
    evidence_data_no_incident = evidence_data.copy()
    evidence_data_no_incident["incident_id"] = ""
    with pytest.raises(ValidationError):
        Evidence(**evidence_data_no_incident)
