"""The single UserRole enum is shared by authorization and persistence."""

from aegisops.application.roles import UserRole
from backend.db import models


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
