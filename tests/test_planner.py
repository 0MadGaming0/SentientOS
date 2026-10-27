"""
test_planner.py  -  Unit tests for the SentientOS rule-based planner.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from sentientos.planner import parse_command, TaskPlan


class TestParsedCommands:
    def test_list_files_recognised(self):
        plan = parse_command("list workspace files")
        assert plan.understood is True
        assert any(s.tool == "list_workspace" for s in plan.steps)

    def test_list_files_ls_alias(self):
        plan = parse_command("ls files")
        assert plan.understood is True

    def test_read_file_recognised(self):
        plan = parse_command("read notes.txt")
        assert plan.understood is True
        assert plan.command == "read_file"
        assert any(s.tool == "read_file" for s in plan.steps)

    def test_read_notes_txt_parses_argument(self):
        plan = parse_command("read notes.txt")
        assert plan.understood is True
        assert plan.command == "read_file"
        # Verify only notes.txt is passed as argument, not the full command
        for step in plan.steps:
            if "path" in step.params:
                assert step.params["path"] == "notes.txt"

    def test_read_file_extracts_filename(self):
        plan = parse_command("open report.md")
        steps = {s.tool: s for s in plan.steps}
        assert steps["read_file"].params["path"] == "report.md"

    def test_read_file_with_spaces_quoted(self):
        plan = parse_command('read "project notes.txt"')
        assert plan.understood is True
        steps = {s.tool: s for s in plan.steps}
        assert steps["read_file"].params["path"] == "project notes.txt"

    def test_read_file_with_spaces_unquoted(self):
        plan = parse_command("read project notes.txt")
        assert plan.understood is True
        steps = {s.tool: s for s in plan.steps}
        assert steps["read_file"].params["path"] == "project notes.txt"

    def test_read_path_traversal_preserved_for_security_gateway(self):
        plan = parse_command("read ../../etc/passwd")
        assert plan.understood is True
        steps = {s.tool: s for s in plan.steps}
        assert steps["read_file"].params["path"] == "../../etc/passwd"
        assert steps["security_check"].params["path"] == "../../etc/passwd"

    def test_read_missing_filename(self):
        plan = parse_command("read")
        assert plan.understood is False

    def test_create_file_recognised(self):
        plan = parse_command("create file hello.txt with content 'Hi!'")
        assert plan.understood is True
        assert any(s.tool == "create_file" for s in plan.steps)

    def test_create_file_requires_approval(self):
        plan = parse_command("create file test.txt")
        approval_steps = [s for s in plan.steps if s.requires_approval]
        assert len(approval_steps) >= 1

    def test_create_file_extracts_filename(self):
        plan = parse_command("create file output.txt")
        create_steps = [s for s in plan.steps if s.tool == "create_file"]
        assert len(create_steps) == 1
        assert create_steps[0].params["path"] == "output.txt"

    def test_create_file_with_spaces(self):
        plan = parse_command('create file "my report.txt" with content \'hello\'')
        create_steps = [s for s in plan.steps if s.tool == "create_file"]
        assert len(create_steps) == 1
        assert create_steps[0].params["path"] == "my report.txt"

    def test_system_status_recognised(self):
        plan = parse_command("show system status")
        assert plan.understood is True
        assert any(s.tool == "system_metrics" for s in plan.steps)

    def test_help_recognised(self):
        plan = parse_command("help")
        assert plan.understood is True
        assert any(s.tool == "fetch_help" for s in plan.steps)

    def test_policy_recognised(self):
        plan = parse_command("show security policy")
        assert plan.understood is True
        assert any(s.tool == "fetch_policy" for s in plan.steps)

    def test_empty_command_not_understood(self):
        plan = parse_command("")
        assert plan.understood is False

    def test_gibberish_not_understood(self):
        plan = parse_command("xyzzy frobulate the quantum core")
        assert plan.understood is False
        assert len(plan.steps) == 0

    def test_plan_has_step_ids(self):
        plan = parse_command("list files")
        for i, step in enumerate(plan.steps, 1):
            assert step.step_id == i

    def test_clear_log_requires_approval(self):
        plan = parse_command("clear log")
        approval_steps = [s for s in plan.steps if s.requires_approval]
        assert len(approval_steps) >= 1


class TestPlannerRegressionIntentMatching:
    """Verifies that requested intents match planned actions and prepositional workspace phrases don't substitute actions."""

    def test_read_file_from_workspace_phrase_matches_read_file(self):
        cmd = "Read the file test_script.py from my workspace."
        plan = parse_command(cmd)
        assert plan.understood is True
        assert plan.command == "read_file"
        tools = [s.tool for s in plan.steps]
        assert tools == ["security_check", "read_file"]
        assert "list_workspace" not in tools
        assert plan.steps[0].params["path"] == "test_script.py"
        assert plan.steps[1].params["path"] == "test_script.py"

    def test_read_quoted_file_from_workspace_phrase(self):
        cmd = 'Read the file "test_script.py" from my workspace.'
        plan = parse_command(cmd)
        assert plan.understood is True
        assert plan.command == "read_file"
        assert plan.steps[1].params["path"] == "test_script.py"

    def test_read_notes_txt_from_workspace(self):
        plan = parse_command("read notes.txt from my workspace")
        assert plan.understood is True
        assert plan.command == "read_file"
        assert plan.steps[1].params["path"] == "notes.txt"

    def test_unsupported_intent_rejected(self):
        plan = parse_command("execute arbitrary python code now")
        assert plan.understood is False
        assert len(plan.steps) == 0