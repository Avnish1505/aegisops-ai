"""Format and truncate a display name."""


def format_display_name(first_name: str, last_name: str) -> str:
    return f"{first_name} {last_name}".strip()


def truncate_display_name(name: str, max_length: int = 20) -> str:
    return name[:max_length]
