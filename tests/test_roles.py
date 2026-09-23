"""The single UserRole enum is shared by authorization and persistence."""

import pytest
from fastapi.testclient import TestClient

from aegisops.api.app import create_app
from aegisops.application.roles import UserRole
from aegisops.core.config import Settings
from backend.db import models


def _client() -> TestClient:
    return TestClient(
        create_app(Settings(environment="test", database_url="sqlite://"))
    )


def test_role_values_are_the_four_supported_roles() -> None:
    assert [role.value for role in UserRole] == ["viewer", "operator", "approver", "admin"]


def test_database_role_column_uses_the_shared_enum() -> None:
    assert models.UserRole is UserRole
    assert models.Role.__table__.c.name.type.enum_class is UserRole


def test_privilege_is_ordered_by_rank_not_string_value() -> None:
    # As strings, "admin" < "viewer"; privilege must not depend on alphabetical order.
    assert UserRole.ADMIN.at_least(UserRole.VIEWER)
    assert UserRole.APPROVER.at_least(UserRole.OPERATOR)
    assert not UserRole.VIEWER.at_least(UserRole.OPERATOR)
    assert not UserRole.OPERATOR.at_least(UserRole.APPROVER)


@pytest.mark.parametrize(
    ("token", "expected_status"),
    [
        ("role:viewer", 403),
        ("role:operator", 200),
        ("role:approver", 200),
        ("admin", 200),
        ("role:commander", 401),
        ("role:superuser", 401),
    ],
)
def test_decision_creation_requires_operator_or_higher(token: str, expected_status: int) -> None:
    response = _client().post(
        "/api/v1/decisions", json={"seed": 1}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == expected_status
