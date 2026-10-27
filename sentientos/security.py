"""
security.py  -  Security gateway for SentientOS.

All tool actions pass through this module before execution.
Rules are plain Python - independent of the planner or UI.
"""
import json
import os
import re
import secrets
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Set

WORKSPACE_ROOT = (Path(__file__).parent.parent / "workspace").resolve()

MAX_FILE_SIZE = 64 * 1024  # 64 KB

_SAFE_FILENAME = re.compile(r'^[\w\-. ]+$')
_WIN_DRIVE_RE = re.compile(r'^[a-zA-Z]:')
_UNC_PATH_RE = re.compile(r'^(?:[\\/]{2}|\\\\?\?\\)')

ALLOWED_EXTENSIONS: Set[str] = {".txt", ".md", ".csv", ".json", ".log"}
ALLOWED_WRITE_EXTENSIONS: Set[str] = ALLOWED_EXTENSIONS

STATE_CHANGING_TOOLS: Set[str] = {"create_file", "clear_log"}
READ_ONLY_TOOLS: Set[str] = {
    "list_workspace",
    "read_file",
    "system_metrics",
    "fetch_logs",
    "fetch_help",
    "fetch_policy",
    "security_check",
    "human_approval",
}
ALLOWED_TOOLS: Set[str] = STATE_CHANGING_TOOLS | READ_ONLY_TOOLS

# Parameter validation schemas: tool -> allowed param names
TOOL_PARAM_SCHEMAS: Dict[str, Set[str]] = {
    "list_workspace": set(),
    "read_file": {"path"},
    "create_file": {"path", "content"},
    "system_metrics": set(),
    "fetch_logs": {"limit"},
    "fetch_help": set(),
    "fetch_policy": set(),
    "clear_log": {"action", "keep"},
    "security_check": {"path", "mode", "content"},
    "human_approval": {"path", "content", "action"},
}


class SecurityError(Exception):
    """Raised when a requested action violates security policy."""


# ── Approval Store ───────────────────────────────────────────────────────────

@dataclass
class ApprovalTicket:
    token: str
    session_id: str
    task_id: str
    step_id: int
    action: str
    canonical_params: str
    created_at: float
    expires_at: float
    consumed: bool = False
    revoked: bool = False


_APPROVAL_STORE: Dict[str, ApprovalTicket] = {}
_APPROVAL_LOCK = threading.Lock()
APPROVAL_TTL_SECONDS = 300  # 5 minutes


def canonicalize_params(params: dict) -> str:
    """Return deterministic canonical JSON representation of tool arguments."""
    return json.dumps(params or {}, sort_keys=True, separators=(',', ':'))


def create_approval_ticket(
    session_id: str,
    task_id: str,
    step_id: int,
    action: str,
    params: dict,
    ttl_seconds: int = APPROVAL_TTL_SECONDS,
) -> str:
    """Generate a single-use approval ticket bound to action and arguments."""
    token = secrets.token_hex(20)
    now = time.time()
    ticket = ApprovalTicket(
        token=token,
        session_id=session_id,
        task_id=task_id,
        step_id=step_id,
        action=action,
        canonical_params=canonicalize_params(params),
        created_at=now,
        expires_at=now + ttl_seconds,
        consumed=False,
        revoked=False,
    )
    with _APPROVAL_LOCK:
        _APPROVAL_STORE[token] = ticket
    return token


def verify_and_consume_approval(
    token: Optional[str],
    action: str,
    params: dict,
    session_id: Optional[str] = None,
) -> bool:
    """
    Validate and consume an approval ticket.
    Binds approval strictly to exact action and arguments.
    Rejects missing, stale, modified, or reused approvals.
    """
    if not token or not isinstance(token, str):
        raise SecurityError("Approval required: missing approval token for state-changing operation.")

    with _APPROVAL_LOCK:
        ticket = _APPROVAL_STORE.get(token)
        if not ticket:
            raise SecurityError("Approval verification failed: invalid or unknown approval token.")

        if ticket.consumed:
            raise SecurityError(
                "Approval verification failed: approval token has already been consumed (replay rejected)."
            )

        if ticket.revoked:
            raise SecurityError("Approval verification failed: approval token has been revoked / denied.")

        now = time.time()
        if now > ticket.expires_at:
            raise SecurityError("Approval verification failed: approval token has expired.")

        if ticket.action != action:
            raise SecurityError(
                f"Approval verification failed: action mismatch (approved: '{ticket.action}', attempted: '{action}')."
            )

        current_canonical = canonicalize_params(params)
        if ticket.canonical_params != current_canonical:
            raise SecurityError(
                "Approval verification failed: parameters were altered after approval was issued (tampering detected)."
            )

        if session_id and ticket.session_id and ticket.session_id != session_id:
            raise SecurityError("Approval verification failed: session mismatch.")

        # Single-use consumption
        ticket.consumed = True
        return True


def revoke_approval_ticket(token: str) -> bool:
    """Revoke an active approval ticket (e.g. on user denial)."""
    with _APPROVAL_LOCK:
        ticket = _APPROVAL_STORE.get(token)
        if ticket:
            ticket.revoked = True
            return True
        return False


def get_approval_ticket(token: str) -> Optional[ApprovalTicket]:
    with _APPROVAL_LOCK:
        return _APPROVAL_STORE.get(token)


# ── Path Resolution & Validation ─────────────────────────────────────────────

def _resolve_safe(relative_path: str, check_extension: bool = True, for_write: bool = False) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise SecurityError("Path must be a non-empty string.")

    # 1. Null byte injection check
    if "\0" in relative_path:
        raise SecurityError(f"Path contains null byte: '{relative_path}'")

    # 2. Windows drive paths: C:, D:, etc.
    if _WIN_DRIVE_RE.match(relative_path):
        raise SecurityError(f"Windows drive paths are not allowed: '{relative_path}'")

    # 3. UNC and device paths
    if _UNC_PATH_RE.match(relative_path) or relative_path.startswith(("//", "\\\\")):
        raise SecurityError(f"UNC/network paths are not allowed: '{relative_path}'")

    # 4. Backslashes are rejected (enforce Unix standard forward slashes)
    if "\\" in relative_path:
        raise SecurityError(f"Backslashes are not allowed in paths: '{relative_path}'")

    # 5. PurePosixPath absolute path check
    p = PurePosixPath(relative_path)
    if p.is_absolute():
        raise SecurityError(f"Absolute paths are not allowed: '{relative_path}'")

    # 6. Path traversal checks
    for part in p.parts:
        if part == "..":
            raise SecurityError(f"Path traversal is not allowed (escapes the workspace sandbox): '{relative_path}'")
        if not _SAFE_FILENAME.match(part):
            raise SecurityError(f"Filename contains disallowed characters: '{part}'")

    # 7. Resolve against WORKSPACE_ROOT (dynamic resolution for monkeypatch support in tests)
    ws_root = WORKSPACE_ROOT.resolve()
    target = (ws_root / relative_path)

    # 8. Symlink check for write operations
    if for_write and target.is_symlink():
        raise SecurityError(f"Writing to symlinks is prohibited: '{relative_path}'")

    # 9. Workspace sandbox boundary check
    resolved = target.resolve()
    try:
        resolved.relative_to(ws_root)
    except ValueError:
        raise SecurityError(f"Path escapes the workspace sandbox: '{relative_path}'")

    # 10. Regular file check: disallow reading directories
    if target.is_dir() or resolved.is_dir():
        raise SecurityError(f"Not a regular file: '{relative_path}'")

    # 11. Extension check
    if check_extension:
        suffix = p.suffix.lower()
        if not suffix or suffix not in ALLOWED_EXTENSIONS:
            raise SecurityError(
                f"File extension '{suffix}' is not allowed. "
                f"Permitted: {sorted(ALLOWED_EXTENSIONS)}"
            )

    return resolved


def validate_list_workspace() -> Path:
    ws_root = WORKSPACE_ROOT.resolve()
    if not ws_root.exists():
        raise SecurityError("Workspace directory does not exist.")
    return ws_root


def validate_read_file(relative_path: str) -> Path:
    resolved = _resolve_safe(relative_path, check_extension=True, for_write=False)
    if not resolved.exists():
        raise SecurityError(f"File not found: '{relative_path}'")
    if not resolved.is_file():
        raise SecurityError(f"Not a regular file: '{relative_path}'")

    # Ensure symlink target does not escape workspace
    ws_root = WORKSPACE_ROOT.resolve()
    try:
        resolved.resolve().relative_to(ws_root)
    except ValueError:
        raise SecurityError(f"Path escapes the workspace sandbox: '{relative_path}'")

    if resolved.stat().st_size > MAX_FILE_SIZE:
        raise SecurityError(f"File exceeds size limit ({MAX_FILE_SIZE} bytes): '{relative_path}'")
    return resolved


def validate_create_file(relative_path: str, content: str) -> Path:
    resolved = _resolve_safe(relative_path, check_extension=True, for_write=True)
    filename = resolved.name
    if not _SAFE_FILENAME.match(filename):
        raise SecurityError(f"Filename contains disallowed characters: '{filename}'")

    suffix = resolved.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise SecurityError(
            f"File extension '{suffix}' is not allowed. "
            f"Permitted: {sorted(ALLOWED_EXTENSIONS)}"
        )

    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_SIZE:
        raise SecurityError(f"Content exceeds size limit ({MAX_FILE_SIZE} bytes).")

    ws_root = WORKSPACE_ROOT.resolve()
    parent = resolved.parent
    try:
        parent.resolve().relative_to(ws_root)
    except ValueError:
        raise SecurityError("Target directory is outside the workspace.")

    return resolved


def safe_read_file(relative_path: str) -> str:
    """
    Safely read file enforcing regular file check, O_NOFOLLOW where possible,
    and size limit enforcement during chunk reading (preventing TOCTOU).
    """
    resolved = validate_read_file(relative_path)
    target_path = str(resolved)

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(target_path, flags)
    except OSError as exc:
        raise SecurityError(f"Cannot open file: {exc}")

    try:
        st_res = os.fstat(fd)
        if not stat.S_ISREG(st_res.st_mode):
            raise SecurityError(f"Not a regular file: '{relative_path}'")

        chunks = []
        total_read = 0
        chunk_size = 8192
        while True:
            chunk = os.read(fd, chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > MAX_FILE_SIZE:
                raise SecurityError(f"File exceeds size limit ({MAX_FILE_SIZE} bytes): '{relative_path}'")
            chunks.append(chunk)

        content = b"".join(chunks).decode("utf-8", errors="replace")
        return content
    finally:
        os.close(fd)


def safe_create_file(relative_path: str, content: str) -> int:
    """
    Safely create or overwrite file, ensuring parent directories exist,
    prohibiting symlink overwrite attacks, and writing bounded content.
    """
    resolved = validate_create_file(relative_path, content)
    resolved.parent.mkdir(parents=True, exist_ok=True)

    target_path = str(resolved)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(target_path, flags, 0o644)
    except OSError as exc:
        raise SecurityError(f"Cannot open file for writing: {exc}")

    try:
        data = content.encode("utf-8")
        total_written = 0
        while total_written < len(data):
            written = os.write(fd, data[total_written:])
            if written == 0:
                raise SecurityError("Write failed prematurely.")
            total_written += written
        return total_written
    finally:
        os.close(fd)


# ── Centralized Tool Gateway ─────────────────────────────────────────────────

def authorize_tool_invocation(
    tool_name: str,
    params: dict,
    session_id: str,
    approval_token: Optional[str] = None,
) -> bool:
    """
    Independent security gateway check before any tool execution.
    Denies shell execution, code evaluation, network access, unknown tools,
    unauthorized parameters, and state-changing actions without approval.
    """
    if tool_name not in ALLOWED_TOOLS:
        raise SecurityError(
            f"Execution denied: tool '{tool_name}' is not in the security allowlist. "
            "Shell commands, code evaluation, and network access are strictly forbidden."
        )

    allowed_keys = TOOL_PARAM_SCHEMAS.get(tool_name, set())
    actual_keys = set((params or {}).keys())
    unexpected_keys = actual_keys - allowed_keys
    if unexpected_keys:
        raise SecurityError(
            f"Execution denied: unexpected parameters {sorted(unexpected_keys)} for tool '{tool_name}'."
        )

    # Check if this tool changes state
    if tool_name in STATE_CHANGING_TOOLS:
        verify_and_consume_approval(approval_token, tool_name, params, session_id)

    return True


def describe_policy() -> dict:
    return {
        "workspace": str(WORKSPACE_ROOT),
        "max_file_size_kb": MAX_FILE_SIZE // 1024,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "allowed_write_extensions": sorted(ALLOWED_WRITE_EXTENSIONS),
        "shell_execution": "DISABLED",
        "network_access": "DISABLED",
        "absolute_paths": "REJECTED",
        "path_traversal": "REJECTED",
        "windows_paths": "REJECTED",
        "symlink_escapes": "REJECTED",
        "approval_binding": "ENFORCED",
    }