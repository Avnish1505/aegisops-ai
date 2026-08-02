"""User roles for RBAC."""

from enum import IntEnum


class UserRole(IntEnum):
    """User roles in the system with hierarchical permissions."""

    VIEWER = 1
    OPERATOR = 2
    COMMANDER = 3
    ADMIN = 4

    
