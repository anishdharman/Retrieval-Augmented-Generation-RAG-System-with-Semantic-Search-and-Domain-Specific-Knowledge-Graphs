import secrets
from typing import Any

# Local-development stores. Replace with persistent database and encrypted token storage in production.
PROJECTS: dict[str, dict[str, Any]] = {}
GITHUB_TOKENS: dict[str, str] = {}

def ensure_session_id(session: dict) -> str:
    if not session.get("sid"):
        session["sid"] = secrets.token_urlsafe(32)
    return session["sid"]
