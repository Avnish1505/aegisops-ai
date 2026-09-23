"""The single user-role enum shared by the API (authorization) and the database (Role.name)."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """User roles, lowest privilege first. Compare privilege with ``rank``, never ``<``."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        """Position in the privilege hierarchy; a higher rank includes every lower one."""
        return list(UserRole).index(self)

    def at_least(self, minimum: UserRole) -> bool:
        """Return whether this role holds at least ``minimum``'s privileges."""
        return self.rank >= minimum.rank
