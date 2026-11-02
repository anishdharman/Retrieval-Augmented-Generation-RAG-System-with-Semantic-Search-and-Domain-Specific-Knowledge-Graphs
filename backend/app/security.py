import re
from pathlib import PurePosixPath

BLOCKED_PARTS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
                 ".pytest_cache", ".mypy_cache", ".ruff_cache"}
BLOCKED_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
SECRET_PATTERNS = [
    re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['"][^'"]+['"]"""),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")
]

def safe_relative_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw) > 240:
        raise ValueError("Invalid file path")
    path = PurePosixPath(raw.replace("\\", "/"))
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Unsafe file path")
    if any(part.lower() in BLOCKED_PARTS for part in path.parts):
        raise ValueError("Blocked directory")
    if path.name.lower() in BLOCKED_NAMES or (path.name.lower().startswith(".env.") and path.name.lower() != ".env.example"):
        raise ValueError("Credential files cannot be included")
    return str(path)

def clean_generated_files(files: dict) -> dict[str, str]:
    if not isinstance(files, dict) or not files:
        raise ValueError("AI returned no project files")
    if len(files) > 150:
        raise ValueError("Generated project contains too many files")
    clean, total = {}, 0
    for name, content in files.items():
        path = safe_relative_path(name)
        if not isinstance(content, str):
            raise ValueError(f"File content must be text: {path}")
        if len(content.encode("utf-8")) > 500_000:
            raise ValueError(f"File is too large: {path}")
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Potential secret detected in {path}; generation rejected")
        total += len(content.encode("utf-8"))
        clean[path] = content
    if total > 5_000_000:
        raise ValueError("Generated project is too large")
    return clean

def publishable_files(files: dict[str, str]) -> dict[str, str]:
    result = {}
    for name, content in files.items():
        try:
            path = safe_relative_path(name)
        except ValueError:
            continue
        if path.lower().endswith((".pyc", ".log", ".sqlite", ".db")):
            continue
        result[path] = content
    return result
