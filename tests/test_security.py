"""
test_security.py  -  Tests for SentientOS security gateway and workspace tools.

Run with:
    python -m pytest tests/ -v
"""
import os
import sys
import time
import pytest
from pathlib import Path

# Ensure sentientos package is importable from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sentientos.security import (
    SecurityError,
    WORKSPACE_ROOT,
    MAX_FILE_SIZE,
    validate_read_file,
    validate_create_file,
    validate_list_workspace,
    safe_read_file,
    safe_create_file,
    describe_policy,
    create_approval_ticket,
    verify_and_consume_approval,
    revoke_approval_ticket,
    authorize_tool_invocation,
)
from sentientos.tools import (
    tool_list_workspace,
    tool_read_file,
    tool_create_file,
)
from sentientos.planner import parse_command
from sentientos.executor import execute_plan
from sentientos import database as db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def ensure_workspace(tmp_path, monkeypatch):
    """
    Override WORKSPACE_ROOT with a fresh tmp_path for each test so that
    tests are isolated and do not pollute the real workspace.
    """
    import sentientos.security as sec
    import sentientos.tools as tools_mod

    fake_ws = tmp_path / "workspace"
    fake_ws.mkdir()

    # Patch the module-level constant in both modules
    monkeypatch.setattr(sec, "WORKSPACE_ROOT", fake_ws.resolve())
    monkeypatch.setattr(tools_mod, "WORKSPACE_ROOT", fake_ws.resolve())

    # Create a sample file for read tests
    (fake_ws / "notes.txt").write_text("Hello from test workspace!")
    yield fake_ws


# ── Security: validate_list_workspace ────────────────────────────────────────

class TestValidateListWorkspace:
    def test_returns_workspace_path(self, ensure_workspace):
        result = validate_list_workspace()
        assert result == ensure_workspace


# ── Security: validate_read_file ─────────────────────────────────────────────

class TestValidateReadFile:
    def test_allows_valid_workspace_file(self, ensure_workspace):
        path = validate_read_file("notes.txt")
        assert path == ensure_workspace / "notes.txt"

    def test_rejects_missing_file(self, ensure_workspace):
        with pytest.raises(SecurityError, match="File not found"):
            validate_read_file("ghost.txt")

    def test_rejects_absolute_path(self):
        with pytest.raises(SecurityError, match="Absolute paths"):
            validate_read_file("/etc/passwd")

    def test_rejects_path_traversal(self):
        with pytest.raises(SecurityError, match="escapes the workspace"):
            validate_read_file("../../etc/passwd")

    def test_rejects_directory_target(self, ensure_workspace):
        (ensure_workspace / "sub").mkdir()
        with pytest.raises(SecurityError, match="Not a regular file"):
            validate_read_file("sub")

    def test_rejects_oversized_file(self, ensure_workspace):
        big = ensure_workspace / "huge.txt"
        big.write_bytes(b"A" * (64 * 1024 + 1))
        with pytest.raises(SecurityError, match="size limit"):
            validate_read_file("huge.txt")

    def test_allows_exact_max_size_file(self, ensure_workspace):
        exact = ensure_workspace / "exact.txt"
        exact.write_bytes(b"A" * (64 * 1024))
        path = validate_read_file("exact.txt")
        assert path == exact


# ── Security: validate_create_file ───────────────────────────────────────────

class TestValidateCreateFile:
    def test_allows_valid_create(self):
        path = validate_create_file("test.txt", "content")
        assert path.name == "test.txt"

    def test_allows_csv_extension(self):
        path = validate_create_file("data.csv", "a,b,c")
        assert path.name == "data.csv"

    def test_allows_md_extension(self):
        path = validate_create_file("readme.md", "# Hello")
        assert path.name == "readme.md"

    def test_allows_json_extension(self):
        path = validate_create_file("data.json", '{"key": "val"}')
        assert path.name == "data.json"

    def test_allows_log_extension(self):
        path = validate_create_file("run.log", "all good")
        assert path.name == "run.log"

    def test_rejects_absolute_path(self):
        with pytest.raises(SecurityError, match="Absolute paths"):
            validate_create_file("/tmp/escape.txt", "bad")

    def test_rejects_path_traversal(self):
        with pytest.raises(SecurityError, match="escapes the workspace"):
            validate_create_file("../escape.txt", "bad")

    def test_rejects_sh_extension(self):
        with pytest.raises(SecurityError, match="extension"):
            validate_create_file("script.sh", "#!/bin/bash\nrm -rf /")

    def test_rejects_py_extension(self):
        with pytest.raises(SecurityError, match="extension"):
            validate_create_file("evil.py", "import os; os.system('rm -rf /')")

    def test_rejects_exe_extension(self):
        with pytest.raises(SecurityError, match="extension"):
            validate_create_file("malware.exe", "")

    def test_rejects_oversized_content(self):
        big = "x" * (64 * 1024 + 1)
        with pytest.raises(SecurityError, match="size limit"):
            validate_create_file("big.txt", big)

    def test_rejects_unsafe_filename_chars(self):
        with pytest.raises(SecurityError, match="disallowed characters"):
            validate_create_file("file;rm -rf .txt", "content")

    def test_allows_max_size_content(self):
        ok_content = "x" * (64 * 1024)
        path = validate_create_file("maxsize.txt", ok_content)
        assert path is not None


# ── Tools: tool_list_workspace ────────────────────────────────────────────────

class TestToolListWorkspace:
    def test_returns_success(self, ensure_workspace):
        result = tool_list_workspace()
        assert result["success"] is True

    def test_lists_existing_file(self, ensure_workspace):
        result = tool_list_workspace()
        names = [f["name"] for f in result["data"]["files"]]
        assert "notes.txt" in names

    def test_empty_workspace(self, ensure_workspace):
        (ensure_workspace / "notes.txt").unlink()
        result = tool_list_workspace()
        assert result["success"] is True
        assert result["data"]["count"] == 0


# ── Tools: tool_read_file ─────────────────────────────────────────────────────

class TestToolReadFile:
    def test_reads_existing_file(self, ensure_workspace):
        result = tool_read_file("notes.txt")
        assert result["success"] is True
        assert "Hello from test workspace!" in result["data"]["content"]

    def test_fails_on_missing_file(self, ensure_workspace):
        result = tool_read_file("ghost.txt")
        assert result["success"] is False
        assert "error" in result

    def test_fails_on_traversal(self, ensure_workspace):
        result = tool_read_file("../../etc/passwd")
        assert result["success"] is False

    def test_fails_on_absolute_path(self, ensure_workspace):
        result = tool_read_file("/etc/passwd")
        assert result["success"] is False


# ── Tools: tool_create_file ───────────────────────────────────────────────────

class TestToolCreateFile:
    def test_creates_file(self, ensure_workspace):
        result = tool_create_file("hello.txt", "Hello, World!")
        assert result["success"] is True
        assert (ensure_workspace / "hello.txt").read_text() == "Hello, World!"

    def test_fails_traversal(self, ensure_workspace):
        result = tool_create_file("../escape.txt", "bad")
        assert result["success"] is False

    def test_fails_bad_extension(self, ensure_workspace):
        result = tool_create_file("bad.sh", "#!/bin/bash")
        assert result["success"] is False

    def test_reports_bytes_written(self, ensure_workspace):
        content = "Test content here."
        result = tool_create_file("test_output.txt", content)
        assert result["success"] is True
        assert result["data"]["bytes_written"] == len(content.encode())

    def test_overwrites_existing_file(self, ensure_workspace):
        tool_create_file("overwrite.txt", "original")
        result = tool_create_file("overwrite.txt", "updated")
        assert result["success"] is True
        assert (ensure_workspace / "overwrite.txt").read_text() == "updated"


# ── Security policy ───────────────────────────────────────────────────────────

class TestDescribePolicy:
    def test_returns_dict(self):
        policy = describe_policy()
        assert isinstance(policy, dict)

    def test_shell_execution_disabled(self):
        policy = describe_policy()
        assert policy["shell_execution"] == "DISABLED"

    def test_network_disabled(self):
        policy = describe_policy()
        assert policy["network_access"] == "DISABLED"

    def test_absolute_paths_rejected(self):
        policy = describe_policy()
        assert policy["absolute_paths"] == "REJECTED"

    def test_path_traversal_rejected(self):
        policy = describe_policy()
        assert policy["path_traversal"] == "REJECTED"


# ── Execution & Validation Halting ───────────────────────────────────────────

class TestReadFileExecution:
    def test_execute_read_notes_txt_success(self, ensure_workspace):
        plan = parse_command("read notes.txt")
        result = execute_plan(plan, "test-session")
        assert result["status"] == "done"
        assert result["steps"][0]["status"] == "done"
        assert result["steps"][1]["status"] == "done"
        assert "Hello from test workspace!" in result["output"]["content"]

    def test_execute_read_file_with_spaces_quoted(self, ensure_workspace):
        (ensure_workspace / "my document.txt").write_text("Space file content")
        plan = parse_command('read "my document.txt"')
        result = execute_plan(plan, "test-session")
        assert result["status"] == "done"
        assert result["steps"][0]["status"] == "done"
        assert result["steps"][1]["status"] == "done"
        assert result["output"]["content"] == "Space file content"

    def test_execute_read_file_with_spaces_unquoted(self, ensure_workspace):
        (ensure_workspace / "project plan.txt").write_text("Project plan content")
        plan = parse_command("read project plan.txt")
        result = execute_plan(plan, "test-session")
        assert result["status"] == "done"
        assert result["steps"][0]["status"] == "done"
        assert result["steps"][1]["status"] == "done"
        assert result["output"]["content"] == "Project plan content"

    def test_execute_read_missing_file_stops_execution_without_pending(self, ensure_workspace):
        plan = parse_command("read missing_file.txt")
        result = execute_plan(plan, "test-session")
        assert result["status"] == "failed"
        assert "File not found" in result["message"]
        # Step 1 should fail
        assert result["steps"][0]["status"] == "failed"
        # Step 2 must NOT be left as pending
        assert result["steps"][1]["status"] != "pending"
        assert result["steps"][1]["status"] == "skipped"
        assert all(s["status"] != "pending" for s in result["steps"])

    def test_execute_read_path_traversal_stops_execution_without_pending(self, ensure_workspace):
        plan = parse_command("read ../../etc/passwd")
        result = execute_plan(plan, "test-session")
        assert result["status"] == "failed"
        assert "escapes the workspace" in result["message"]
        assert result["steps"][0]["status"] == "failed"
        assert result["steps"][1]["status"] != "pending"
        assert result["steps"][1]["status"] == "skipped"
        assert all(s["status"] != "pending" for s in result["steps"])

    def test_execute_read_absolute_path_stops_execution_without_pending(self, ensure_workspace):
        plan = parse_command("read /etc/passwd")
        result = execute_plan(plan, "test-session")
        assert result["status"] == "failed"
        assert "Absolute paths" in result["message"]
        assert result["steps"][0]["status"] == "failed"
        assert result["steps"][1]["status"] != "pending"
        assert result["steps"][1]["status"] == "skipped"
        assert all(s["status"] != "pending" for s in result["steps"])


# ═══════════════════════════════════════════════════════════════════════════════
# NEW SECURITY HARDENING TESTS (ATTACKS & ADVERSARIAL CASES)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityWindowsAndUNCPaths:
    """Verifies that Windows drive, UNC, and device paths are strictly rejected."""

    def test_rejects_windows_drive_backslash(self):
        with pytest.raises(SecurityError, match="Windows drive"):
            validate_read_file(r"C:\Windows\System32\drivers\etc\hosts")

    def test_rejects_windows_drive_forward_slash(self):
        with pytest.raises(SecurityError, match="Windows drive"):
            validate_read_file("C:/Windows/System32/drivers/etc/hosts")

    def test_rejects_windows_drive_relative(self):
        with pytest.raises(SecurityError, match="Windows drive"):
            validate_read_file("D:notes.txt")

    def test_rejects_unc_path_backslashes(self):
        with pytest.raises(SecurityError, match="UNC/network"):
            validate_read_file(r"\\server\share\file.txt")

    def test_rejects_unc_path_forward_slashes(self):
        with pytest.raises(SecurityError, match="UNC/network"):
            validate_read_file("//server/share/file.txt")

    def test_rejects_extended_device_path(self):
        with pytest.raises(SecurityError, match="UNC/network|Windows drive"):
            validate_read_file(r"\\?\C:\boot.ini")

    def test_rejects_backslashes_in_path(self):
        with pytest.raises(SecurityError, match="Backslashes are not allowed"):
            validate_read_file(r"sub\dir\notes.txt")

    def test_rejects_null_byte_injection(self):
        with pytest.raises(SecurityError, match="null byte"):
            validate_read_file("notes.txt\0.exe")


class TestSecuritySymlinkEscapes:
    """Verifies that symlinks escaping workspace are blocked for read and write."""

    def test_rejects_symlink_reading_outside_workspace(self, ensure_workspace):
        target = Path("/etc/passwd")
        if target.exists():
            symlink_path = ensure_workspace / "evil_link.txt"
            symlink_path.symlink_to(target)
            with pytest.raises(SecurityError, match="escapes the workspace"):
                validate_read_file("evil_link.txt")

    def test_rejects_writing_through_symlink(self, ensure_workspace):
        target = Path("/tmp/target_file.txt")
        target.write_text("initial")
        symlink_path = ensure_workspace / "link_write.txt"
        symlink_path.symlink_to(target)
        try:
            with pytest.raises(SecurityError, match="symlinks is prohibited"):
                validate_create_file("link_write.txt", "tampered")
        finally:
            if target.exists():
                target.unlink()

    def test_rejects_directory_symlink_escape(self, ensure_workspace):
        dir_sym = ensure_workspace / "etc_dir"
        dir_sym.symlink_to(Path("/etc"))
        with pytest.raises(SecurityError, match="escapes the workspace"):
            validate_read_file("etc_dir/passwd")


class TestSecurityExtensionEnforcement:
    """Verifies that only explicitly supported text extensions are allowed for reading and writing."""

    def test_rejects_reading_py_file(self, ensure_workspace):
        (ensure_workspace / "script.py").write_text("print('evil')")
        with pytest.raises(SecurityError, match="extension"):
            validate_read_file("script.py")

    def test_rejects_reading_exe_file(self, ensure_workspace):
        (ensure_workspace / "binary.exe").write_bytes(b"\x7fELF")
        with pytest.raises(SecurityError, match="extension"):
            validate_read_file("binary.exe")

    def test_rejects_reading_file_without_extension(self, ensure_workspace):
        (ensure_workspace / "noext").write_text("data")
        with pytest.raises(SecurityError, match="extension"):
            validate_read_file("noext")

    def test_rejects_reading_database_file(self, ensure_workspace):
        (ensure_workspace / "secret.db").write_bytes(b"SQLite format 3\0")
        with pytest.raises(SecurityError, match="extension"):
            validate_read_file("secret.db")


class TestSecurityOversizedReadEnforcement:
    """Verifies chunk-level file size enforcement during reading."""

    def test_rejects_oversized_file_during_read(self, ensure_workspace):
        big_file = ensure_workspace / "oversized.txt"
        big_file.write_bytes(b"X" * (MAX_FILE_SIZE + 1024))
        with pytest.raises(SecurityError, match="size limit"):
            safe_read_file("oversized.txt")

    def test_reads_exact_max_file_size(self, ensure_workspace):
        exact_file = ensure_workspace / "max_read.txt"
        exact_file.write_bytes(b"Z" * MAX_FILE_SIZE)
        content = safe_read_file("max_read.txt")
        assert len(content) == MAX_FILE_SIZE


class TestApprovalSecurityAndBinding:
    """Verifies approval security: cryptographic binding, argument tampering, replay, and bypass protection."""

    def test_approval_ticket_created_and_verified(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        assert isinstance(token, str) and len(token) > 10
        # Verification succeeds with matching params
        verified = verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "Hi"}, "sess-1")
        assert verified is True

    def test_approval_replay_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        # First use succeeds
        verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "Hi"}, "sess-1")
        # Second use (replay) must be rejected
        with pytest.raises(SecurityError, match="already been consumed"):
            verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "Hi"}, "sess-1")

    def test_approval_altered_arguments_path_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        with pytest.raises(SecurityError, match="parameters were altered|tampering detected"):
            verify_and_consume_approval(token, "create_file", {"path": "altered.txt", "content": "Hi"}, "sess-1")

    def test_approval_altered_arguments_content_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        with pytest.raises(SecurityError, match="parameters were altered|tampering detected"):
            verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "MALICIOUS"}, "sess-1")

    def test_approval_action_mismatch_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        with pytest.raises(SecurityError, match="action mismatch"):
            verify_and_consume_approval(token, "clear_log", {"action": "clear_old_logs"}, "sess-1")

    def test_approval_expired_token_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
            ttl_seconds=-1,
        )
        with pytest.raises(SecurityError, match="expired"):
            verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "Hi"}, "sess-1")

    def test_revoked_token_rejected(self):
        token = create_approval_ticket(
            session_id="sess-1",
            task_id="task-1",
            step_id=2,
            action="create_file",
            params={"path": "hello.txt", "content": "Hi"},
        )
        revoke_approval_ticket(token)
        with pytest.raises(SecurityError, match="revoked / denied"):
            verify_and_consume_approval(token, "create_file", {"path": "hello.txt", "content": "Hi"}, "sess-1")

    def test_execute_plan_rejects_boolean_flag_bypass_attempt(self, ensure_workspace):
        plan = parse_command("create file bypassed.txt with content 'evil'")
        result = execute_plan(plan, "session-test", approval_granted=True, approval_token=None)
        assert result["status"] == "failed"
        assert "Boolean approval flags cannot bypass authorization" in result["message"]
        assert not (ensure_workspace / "bypassed.txt").exists()

    def test_execute_plan_rejects_fake_token(self, ensure_workspace):
        plan = parse_command("create file hacked.txt with content 'evil'")
        result = execute_plan(plan, "session-test", approval_token="fake-forged-token-12345")
        assert result["status"] == "failed"
        assert not (ensure_workspace / "hacked.txt").exists()

    def test_execute_plan_full_valid_approval_lifecycle(self, ensure_workspace):
        plan = parse_command("create file approved.txt with content 'Good content'")
        # First execution: must return pending_approval with approval_token
        result1 = execute_plan(plan, "session-test")
        assert result1["status"] == "pending_approval"
        token = result1.get("approval_token")
        assert token is not None

        # Second execution: with valid approval_token
        result2 = execute_plan(plan, "session-test", approval_token=token)
        assert result2["status"] == "done"
        assert (ensure_workspace / "approved.txt").exists()
        assert (ensure_workspace / "approved.txt").read_text() == "Good content"

        # Third execution with same token: must fail (replay blocked)
        result3 = execute_plan(plan, "session-test", approval_token=token)
        assert result3["status"] == "failed"
        assert "already been consumed" in result3["message"]


class TestToolExecutionGateway:
    """Verifies that all tool calls are gated by allowlists and argument schemas."""

    def test_rejects_arbitrary_shell_tool(self):
        with pytest.raises(SecurityError, match="not in the security allowlist"):
            authorize_tool_invocation("bash", {"command": "id"}, "sess")

    def test_rejects_eval_tool(self):
        with pytest.raises(SecurityError, match="not in the security allowlist"):
            authorize_tool_invocation("eval", {"expr": "1+1"}, "sess")

    def test_rejects_unexpected_tool_parameters(self):
        with pytest.raises(SecurityError, match="unexpected parameters"):
            authorize_tool_invocation("read_file", {"path": "notes.txt", "extra_bad_arg": "true"}, "sess")

    def test_state_changing_tool_requires_approval_token_in_gateway(self):
        with pytest.raises(SecurityError, match="missing approval token"):
            authorize_tool_invocation("create_file", {"path": "a.txt", "content": "hello"}, "sess")


class TestAuditLogSecurityAndSanitization:
    """Verifies log sanitization against log injection and line spoofing."""

    def test_strips_newlines_from_log_actions(self):
        injected = "Normal command\nINJECTED LOG ENTRY: Admin granted all permissions\rAnother line"
        row_id = db.log_activity("sess-inject", injected, category="user", status="info")
        recent = db.get_recent_activity(limit=5)
        logged_entry = next(e for e in recent if e["id"] == row_id)
        assert "\n" not in logged_entry["action"]
        assert "\r" not in logged_entry["action"]

    def test_misleading_task_status_does_not_grant_authorization(self, ensure_workspace):
        # Insert a task record marked 'done' or 'approved' into DB
        db.upsert_task("fake-sess", "fake-task", "create file trick.txt", "done")
        # Attempting to call state-changing tool without approval token still strictly fails
        plan = parse_command("create file trick.txt with content 'trick'")
        result = execute_plan(plan, "fake-sess", approval_token=None)
        assert result["status"] == "pending_approval"
        assert not (ensure_workspace / "trick.txt").exists()

class TestTaskVerificationAndFalseSuccessPrevention:
    """Verifies that tasks fail when actions are unsupported, denied, substituted, or unexecuted."""

    def test_regression_read_test_script_py_fails_via_security_gateway(self, ensure_workspace):
        cmd = "Read the file test_script.py from my workspace."
        plan = parse_command(cmd)
        assert plan.command == "read_file"
        tools = [s.tool for s in plan.steps]
        assert "list_workspace" not in tools
        assert tools == ["security_check", "read_file"]

        result = execute_plan(plan, "regression-session")
        assert result["status"] == "failed"
        assert "extension '.py' is not allowed" in result["message"]
        # Step 1 fails
        assert result["steps"][0]["tool"] == "security_check"
        assert result["steps"][0]["status"] == "failed"
        # Step 2 skipped
        assert result["steps"][1]["tool"] == "read_file"
        assert result["steps"][1]["status"] == "skipped"
        # Never substituted or reported done
        assert all(s["tool"] != "list_workspace" for s in result["steps"])

    def test_unsupported_intent_marks_task_failed(self):
        plan = parse_command("run unauthorized root exploit")
        result = execute_plan(plan, "session-test")
        assert result["status"] == "failed"
        assert "not recognised" in result["message"] or "rejected" in result["message"]

    def test_substituted_or_missing_primary_action_fails_verification(self, ensure_workspace):
        # A plan claiming to be 'read_file' but only running 'list_workspace'
        from sentientos.planner import TaskPlan, TaskStep
        fake_plan = TaskPlan(
            command="read_file",
            steps=[
                TaskStep(1, "List files instead", "list_workspace"),
            ],
            understood=True,
        )
        result = execute_plan(fake_plan, "session-test")
        assert result["status"] == "failed"
        assert "Task verification failed" in result["message"]

    def test_plan_with_no_steps_marks_task_failed(self):
        from sentientos.planner import TaskPlan
        empty_plan = TaskPlan(command="read_file", steps=[], understood=True)
        result = execute_plan(empty_plan, "session-test")
        assert result["status"] == "failed"

    def test_denied_read_traversal_marks_task_failed(self, ensure_workspace):
        plan = parse_command("read ../../etc/shadow")
        result = execute_plan(plan, "session-test")
        assert result["status"] == "failed"
        assert "escapes the workspace" in result["message"]
        assert result["steps"][0]["status"] == "failed"
        assert result["steps"][1]["status"] == "skipped"

    def test_verified_read_reports_success_only_with_content(self, ensure_workspace):
        plan = parse_command("read notes.txt")
        result = execute_plan(plan, "session-test")
        assert result["status"] == "done"
        assert result["output"] is not None
        assert "content" in result["output"]
        assert all(s["status"] == "done" for s in result["steps"])