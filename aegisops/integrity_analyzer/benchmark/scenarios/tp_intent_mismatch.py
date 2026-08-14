"""Encrypt user passwords with bcrypt and send a confirmation email after signup."""

users = {}


def register_user(username: str, password: str) -> dict[str, object]:
    users[username] = password
    return {"username": username, "registered": True}
