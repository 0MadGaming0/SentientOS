"""
database.py  -  SQLite activity-log store for SentientOS.
"""
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent.parent / "sentientos.db"

_local = threading.local()


def _sanitize_log_text(val: Any, max_len: int = 500) -> str:
    """
    Sanitize text before storing in audit logs.
    Replaces newlines, carriage returns, tabs, and non-printable characters
    to prevent log injection, line spoofing, and formatting attacks.
    """
    if val is None:
        return ""
    s = str(val)
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = "".join(ch for ch in s if ch.isprintable() or ch == " ")
    return s.strip()[:max_len]


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10.0)
        _local.conn.row_factory = sqlite3.Row
        _create_schema(_local.conn)
    return _local.conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            session_id  TEXT    NOT NULL,
            action      TEXT    NOT NULL,
            category    TEXT    NOT NULL DEFAULT 'general',
            status      TEXT    NOT NULL DEFAULT 'info',
            details     TEXT
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            task_id     TEXT    NOT NULL UNIQUE,
            command     TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'pending',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL,
            steps       TEXT,
            result      TEXT
        );
    """)
    conn.commit()


def log_activity(session_id: str, action: str, category: str = "general",
                 status: str = "info", details: str = "") -> int:
    ts = datetime.now().isoformat(timespec="seconds")
    safe_session = _sanitize_log_text(session_id, max_len=100)
    safe_action = _sanitize_log_text(action, max_len=300)
    safe_category = _sanitize_log_text(category, max_len=50)
    safe_status = _sanitize_log_text(status, max_len=50)
    safe_details = _sanitize_log_text(details, max_len=1000)

    conn = _conn()
    cur = conn.execute(
        "INSERT INTO activity_log (timestamp, session_id, action, category, status, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, safe_session, safe_action, safe_category, safe_status, safe_details),
    )
    conn.commit()
    return cur.lastrowid


def get_recent_activity(limit: int = 50) -> list:
    rows = _conn().execute(
        "SELECT * FROM activity_log ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_task(session_id: str, task_id: str, command: str,
                status: str, steps: str = "", result: str = "") -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    safe_session = _sanitize_log_text(session_id, max_len=100)
    safe_task_id = _sanitize_log_text(task_id, max_len=100)
    safe_cmd = _sanitize_log_text(command, max_len=500)
    safe_status = _sanitize_log_text(status, max_len=50)
    safe_steps = _sanitize_log_text(steps, max_len=2000)
    safe_result = _sanitize_log_text(result, max_len=1000)

    conn = _conn()
    conn.execute(
        """INSERT INTO tasks (session_id, task_id, command, status, created_at, updated_at, steps, result)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(task_id) DO UPDATE SET
              status=excluded.status,
              updated_at=excluded.updated_at,
              steps=excluded.steps,
              result=excluded.result""",
        (safe_session, safe_task_id, safe_cmd, safe_status, ts, ts, safe_steps, safe_result),
    )
    conn.commit()


def get_tasks(limit: int = 20) -> list:
    rows = _conn().execute(
        "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def clear_old_logs(keep: int = 200) -> None:
    conn = _conn()
    conn.execute(
        "DELETE FROM activity_log WHERE id NOT IN "
        "(SELECT id FROM activity_log ORDER BY id DESC LIMIT ?)",
        (keep,),
    )
    conn.commit()