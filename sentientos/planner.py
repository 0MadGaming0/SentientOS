"""
planner.py  -  Rule-based natural-language command planner for SentientOS.

Converts user text commands into structured task plans.
No LLM / API required - pure keyword matching and pattern rules.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TaskStep:
    step_id: int
    description: str
    tool: str                      # e.g. "list_workspace", "read_file", "create_file"
    params: dict = field(default_factory=dict)
    requires_approval: bool = False
    status: str = "pending"        # pending | running | done | failed | denied | skipped


@dataclass
class TaskPlan:
    command: str
    steps: list
    understood: bool = True
    rejection_reason: str = ""


# ── Intent patterns ──────────────────────────────────────────────────────────
# Ordered carefully so specific commands (like status, policy, help, clear_log)
# and explicit file operations (create_file, read_file) take precedence over
# generic file listing and summary queries.
_PATTERNS = [
    # 1. System status, dashboard, health, info
    (re.compile(r'\b(status|dashboard|health|info)\b', re.I), "system_status"),
    # 2. Help, commands reference
    (re.compile(r'\b(help|commands|demo|what can)\b', re.I), "show_help"),
    # 3. Security policy, rules, permissions
    (re.compile(r'\b(security|policy|rules|permissions)\b', re.I), "show_policy"),
    # 4. Clear/trim activity log
    (re.compile(r'\b(clear|clean|reset)\b.*\blog\b', re.I), "clear_log"),
    # 5. Create/write/make file
    (re.compile(r'\b(create|make|write|new)\b.*file\b', re.I), "create_file"),
    # 6. Read/open/view/cat file
    (re.compile(r'\b(read|open|view|cat)\b', re.I), "read_file"),
    (re.compile(r'\bshow\b\s+.*(?:\.\w+|["\'])', re.I), "read_file"),
    # 7. List workspace files / workspace summary (specific list/summary requests)
    (re.compile(r'\b(list|ls)\b.*\b(files?|workspace|folders?|dirs?)\b', re.I), "list_files"),
    (re.compile(r'^\s*ls\s*$', re.I), "list_files"),
    (re.compile(r'\bshow\s+(?:all\s+)?(?:files?|workspace|folders?|dirs?)\b', re.I), "list_files"),
    (re.compile(r'\b(?:workspace|folder)\s+(?:summary|overview|files?|contents?)\b', re.I), "list_files"),
    (re.compile(r'\b(?:summary|overview)\s+of\s+(?:the\s+)?workspace\b', re.I), "list_files"),
    (re.compile(r'^\s*(workspace|summary|overview)\s*$', re.I), "list_files"),
]


def _extract_read_filename(text: str) -> Optional[str]:
    """
    Extract the filename from a read/open/view/cat/show command.
    Handles quotes (e.g. read "my notes.txt"), unquoted files with spaces,
    nested paths, trailing prepositional workspace phrases, and path traversal attempts.
    """
    text = text.strip()
    if not text:
        return None

    # 1. Look for explicit quotes after verb: read "my notes.txt" or read 'my notes.txt'
    m_quoted = re.search(r'\b(?:read|open|view|cat|show)\b.*?["\']([^"\']+)["\']', text, re.I)
    if m_quoted:
        return m_quoted.group(1).strip()

    # 2. Extract string after the command verb
    m_verb = re.search(
        r'\b(?:read|open|view|cat|show)\s+(?:the\s+)?(?:file\s+)?(.+)',
        text,
        re.I
    )
    if m_verb:
        candidate = m_verb.group(1).strip()
        # Remove trailing punctuation (., !, ?)
        candidate = re.sub(r'[\.!\?]+$', '', candidate).strip()
        # Remove trailing prepositional phrases specifying workspace location
        candidate = re.sub(
            r'\s+(?:from|in|of|inside|at)\s+(?:my\s+|the\s+)?workspace\s*$',
            '',
            candidate,
            flags=re.I
        ).strip()
        # Remove trailing conversational words like "please"
        candidate = re.sub(r'\s+please\s*$', '', candidate, flags=re.I).strip()
        candidate = candidate.strip('"\'')
        if candidate:
            return candidate

    # 3. Fallback: check if entire string contains a filename match
    m_fallback = re.search(r'["\']?([\w\-./\\]+\.\w+)["\']?', text)
    if m_fallback:
        return m_fallback.group(1).strip()

    return None


def _extract_create_filename(text: str) -> Optional[str]:
    """Extract filename for file creation requests."""
    # Prefix before "with content" / "content:"
    prefix = re.split(r'\b(?:with\s+content|content:)', text, flags=re.I)[0]
    # Check for quotes in prefix: create file "my file.txt"
    m_quote = re.search(r'["\']([^"\']+)["\']', prefix)
    if m_quote:
        return m_quote.group(1).strip()
    # Strip leading verb + file
    cleaned = re.sub(
        r'^\s*(?:please\s+)?(?:create|make|write|new)\s+(?:a\s+)?(?:new\s+)?file\s+',
        '',
        prefix,
        flags=re.I
    ).strip()
    # Strip trailing punctuation and workspace location phrases
    cleaned = re.sub(r'[\.!\?]+$', '', cleaned).strip()
    cleaned = re.sub(
        r'\s+(?:in|into|inside|to|at)\s+(?:my\s+|the\s+)?workspace\s*$',
        '',
        cleaned,
        flags=re.I
    ).strip()
    if cleaned:
        m = re.match(r'^[^\s]+', cleaned)
        return m.group(0).strip() if m else cleaned
    return None


def _extract_filename(text: str) -> Optional[str]:
    """General filename extractor (backward-compatible)."""
    return _extract_read_filename(text)


def _extract_content(text: str) -> str:
    """Extract quoted content or everything after 'content:' / 'with:'."""
    # Quoted block
    m = re.search(r'["\'](.+?)["\']', text, re.S)
    if m:
        return m.group(1)
    # After 'content:' or 'with content'
    m = re.search(r'(?:content[:\s]+|with\s+content\s+)(.*)', text, re.I | re.S)
    if m:
        return m.group(1).strip()
    return "Hello from SentientOS!"


def _make_plan_list_files() -> TaskPlan:
    return TaskPlan(
        command="list_files",
        steps=[
            TaskStep(1, "Validate workspace access", "security_check"),
            TaskStep(2, "List workspace files", "list_workspace"),
        ],
    )


def _make_plan_read_file(filename: Optional[str]) -> TaskPlan:
    if not filename:
        return TaskPlan(
            command="read_file",
            steps=[],
            understood=False,
            rejection_reason="Please specify a filename to read (e.g., 'read notes.txt')."
        )
    return TaskPlan(
        command="read_file",
        steps=[
            TaskStep(1, f"Validate path: {filename}", "security_check",
                     {"path": filename, "mode": "read"}),
            TaskStep(2, f"Read file: {filename}", "read_file",
                     {"path": filename}),
        ],
    )


def _make_plan_create_file(filename: Optional[str], content: str) -> TaskPlan:
    fname = filename or "new_file.txt"
    return TaskPlan(
        command="create_file",
        steps=[
            TaskStep(1, f"Validate path & content for: {fname}", "security_check",
                     {"path": fname, "content": content, "mode": "write"}),
            TaskStep(2, f"Request human approval to create: {fname}",
                     "human_approval",
                     {"path": fname, "content": content},
                     requires_approval=True),
            TaskStep(3, f"Write file: {fname}", "create_file",
                     {"path": fname, "content": content},
                     requires_approval=True),
        ],
    )


def _make_plan_system_status() -> TaskPlan:
    return TaskPlan(
        command="system_status",
        steps=[
            TaskStep(1, "Gather system metrics", "system_metrics"),
            TaskStep(2, "Gather workspace summary", "list_workspace"),
            TaskStep(3, "Retrieve recent activity", "fetch_logs"),
        ],
    )


def _make_plan_show_help() -> TaskPlan:
    return TaskPlan(
        command="show_help",
        steps=[
            TaskStep(1, "Retrieve demo commands list", "fetch_help"),
        ],
    )


def _make_plan_show_policy() -> TaskPlan:
    return TaskPlan(
        command="show_policy",
        steps=[
            TaskStep(1, "Load security policy description", "fetch_policy"),
        ],
    )


def _make_plan_clear_log() -> TaskPlan:
    return TaskPlan(
        command="clear_log",
        steps=[
            TaskStep(1, "Request approval to trim old log entries",
                     "human_approval",
                     {"action": "clear_old_logs"},
                     requires_approval=True),
            TaskStep(2, "Trim activity log (keep last 200 entries)", "clear_log",
                     {"action": "clear_old_logs"},
                     requires_approval=True),
        ],
    )


def _make_plan_unknown(command: str) -> TaskPlan:
    return TaskPlan(
        command=command,
        steps=[],
        understood=False,
        rejection_reason=(
            "Command not recognised. Try: 'list files', 'read notes.txt', "
            "'create file report.txt', 'show status', or 'help'."
        ),
    )


# ── Public API ───────────────────────────────────────────────────────────────

def parse_command(text: str) -> TaskPlan:
    """
    Parse a natural-language command and return a TaskPlan.
    Matching is rule-based (regex) — no LLM or external service used.
    """
    text = text.strip()
    if not text:
        return _make_plan_unknown("")

    for pattern, handler in _PATTERNS:
        if pattern.search(text):
            if handler == "list_files":
                return _make_plan_list_files()
            elif handler == "read_file":
                fname = _extract_read_filename(text)
                return _make_plan_read_file(fname)
            elif handler == "create_file":
                fname = _extract_create_filename(text)
                content = _extract_content(text)
                return _make_plan_create_file(fname, content)
            elif handler == "system_status":
                return _make_plan_system_status()
            elif handler == "show_help":
                return _make_plan_show_help()
            elif handler == "show_policy":
                return _make_plan_show_policy()
            elif handler == "clear_log":
                return _make_plan_clear_log()

    return _make_plan_unknown(text)


DEMO_COMMANDS = [
    "list workspace files",
    "read notes.txt",
    "read readme.md",
    "create file hello.txt with content 'Hello, SentientOS!'",
    "show system status",
    "show security policy",
    "help",
]