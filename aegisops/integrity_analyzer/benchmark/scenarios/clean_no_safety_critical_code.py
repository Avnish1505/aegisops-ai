"""Format and truncate a display name."""


def format_display_name(first_name, last_name):
    return f"{first_name} {last_name}".strip()


def truncate_display_name(name, max_length=20):
    return name[:max_length]
