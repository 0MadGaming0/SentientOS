"""
tools.py  -  Restricted workspace tools for SentientOS.
"""
from pathlib import Path
from sentientos.security import (
    SecurityError,
    WORKSPACE_ROOT,
    ALLOWED_EXTENSIONS,
    validate_list_workspace,
    validate_read_file,
    validate_create_file,
    safe_read_file,
    safe_create_file,
)


def _ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


def _err(msg: str) -> dict:
    return {"success": False, "data": None, "error": msg}


def tool_list_workspace() -> dict:
    try:
        workspace = validate_list_workspace()
        files = []
        for p in sorted(workspace.iterdir()):
            if p.is_file() and not p.is_symlink():
                # Enforce supported text extension visibility
                if p.suffix.lower() in ALLOWED_EXTENSIONS:
                    stat = p.stat()
                    files.append({"name": p.name, "size_bytes": stat.st_size, "modified": stat.st_mtime})
        return _ok({"files": files, "count": len(files)})
    except SecurityError as exc:
        return _err(f"Security violation: {exc}")
    except OSError as exc:
        return _err(f"OS error: {exc}")


def tool_read_file(relative_path: str) -> dict:
    try:
        content = safe_read_file(relative_path)
        size_bytes = len(content.encode("utf-8"))
        return _ok({"path": relative_path, "content": content, "size_bytes": size_bytes})
    except SecurityError as exc:
        return _err(f"Security violation: {exc}")
    except OSError as exc:
        return _err(f"OS error: {exc}")


def tool_create_file(relative_path: str, content: str) -> dict:
    try:
        bytes_written = safe_create_file(relative_path, content)
        ws_root = WORKSPACE_ROOT.resolve()
        abs_path = str(ws_root / relative_path)
        return _ok({"path": relative_path, "abs_path": abs_path, "bytes_written": bytes_written})
    except SecurityError as exc:
        return _err(f"Security violation: {exc}")
    except OSError as exc:
        return _err(f"OS error: {exc}")


def get_workspace_summary() -> dict:
    try:
        workspace = WORKSPACE_ROOT.resolve()
        if not workspace.exists():
            return {"exists": False, "file_count": 0, "total_bytes": 0}
        files = [p for p in workspace.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in ALLOWED_EXTENSIONS]
        total = sum(p.stat().st_size for p in files)
        return {"exists": True, "file_count": len(files), "total_bytes": total}
    except OSError:
        return {"exists": False, "file_count": 0, "total_bytes": 0}