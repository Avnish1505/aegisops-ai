"""User roles for RBAC."""

from enum import IntEnum


class UserRole(IntEnum):
    """User roles in the system with hierarchical permissions."""

    VIEWER = 1
    OPERATOR = 2
    COMMANDER = 3
    ADMIN = 4

    def __ge__(self, other: "UserRole") -> bool:
        if isinstance(other, UserRole):
            return self.value >= other.value
        return NotImplemented

    def __gt__(self, other: "UserRole") -> bool:
        if isinstance(other, UserRole):
            return self.value > other.value
        return NotImplemented

    def __le__(self, other: "UserRole") -> bool:
        if isinstance(other, UserRole):
            return self.value <= other.value
        return NotImplemented

    def __lt__(self, other: "UserRole") -> bool:
        if isinstance(other, UserRole):
            return self.value < other.value
        return NotImplemented