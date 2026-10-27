"""
executor.py  -  Executes TaskPlan steps for SentientOS.

Enforces that state-changing steps only run after explicit human approval.
Never executes shell commands or arbitrary code.
All tool invocations are routed through the independent security gateway.
Goal satisfaction is verified before reporting task success.
"""
import platform
import uuid
from datetime import datetime
from typing import Any, Optional

from sentientos import database as db
from sentientos.planner import TaskPlan, TaskStep
from sentientos.security import (
    SecurityError,
    STATE_CHANGING_TOOLS,
    create_approval_ticket,
    authorize_tool_invocation,
    describe_policy,
)
from sentientos.tools import (
    tool_list_workspace,
    tool_read_file,
    tool_create_file,
    get_workspace_summary,
)


def _new_task_id() -> str:
    return f"task-{uuid.uuid4().hex[:8]}"


def get_system_metrics() -> dict:
    """Return safe, read-only system info. No shell commands."""
    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "node": platform.node(),
        "arch": platform.machine(),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


HELP_TEXT = """
## SentientOS — Supported Commands

| Command | Example |
|---|---|
| List workspace files | `list workspace files` |
| Read a file | `read notes.txt` |
| Create a file | `create file hello.txt with content 'Hi!'` |
| System status | `show system status` |
| Security policy | `show security policy` |
| Help | `help` |

**Note:** File creation requires your explicit approval before any disk write occurs.
"""

COMMAND_PRIMARY_TOOLS = {
    "read_file": "read_file",
    "create_file": "create_file",
    "list_files": "list_workspace",
    "clear_log": "clear_log",
    "system_status": "system_metrics",
    "show_policy": "fetch_policy",
    "show_help": "fetch_help",
}


def verify_goal_satisfaction(command: str, steps_summary: list, final_output: Any) -> tuple[bool, str]:
    """
    Verify that the requested goal was genuinely satisfied by actual execution outcomes.
    Ensures false-success is prevented:
    - Verifies all executed steps succeeded without failure or skip.
    - Verifies the primary requested action tool was executed with status 'done'.
    - Verifies execution result contains expected verifiable data.
    """
    if not steps_summary:
        return False, "Task failed: No execution steps were performed."

    # Check that no step failed or was skipped
    if any(s.get("status") in ("failed", "skipped", "denied", "pending", "pending_approval") for s in steps_summary):
        return False, "Task failed: One or more steps did not complete successfully."

    expected_tool = COMMAND_PRIMARY_TOOLS.get(command)
    if expected_tool:
        executed_tools = [s.get("tool") for s in steps_summary if s.get("status") == "done"]
        if expected_tool not in executed_tools:
            return False, f"Task verification failed: requested action '{expected_tool}' for command '{command}' was never executed."

    # Outcome data verification
    if command == "read_file":
        if not isinstance(final_output, dict) or "content" not in final_output:
            return False, "Task verification failed: file content was not retrieved."
    elif command == "create_file":
        if not isinstance(final_output, dict) or "bytes_written" not in final_output:
            return False, "Task verification failed: file creation did not confirm bytes written."
    elif command == "list_files":
        if not isinstance(final_output, dict) or "files" not in final_output:
            return False, "Task verification failed: workspace file listing was not retrieved."

    return True, "Goal verified successfully."


def execute_plan(
    plan: TaskPlan,
    session_id: str,
    approval_token: Optional[str] = None,
    approval_granted: bool = False,
) -> dict:
    """
    Execute each step of *plan* and return a result dict.

    Parameters
    ----------
    plan            : TaskPlan from planner.parse_command()
    session_id      : Unique session identifier for log correlation
    approval_token  : Cryptographic single-use token binding action and arguments
    approval_granted: Deprecated boolean flag; cannot bypass token requirement
    """
    task_id = _new_task_id()
    steps_summary = [
        {"step_id": s.step_id, "description": s.description,
         "tool": s.tool, "status": "pending"}
        for s in plan.steps
    ]

    if not plan.understood or not plan.steps:
        reason = plan.rejection_reason or "Unsupported command or action not planned."
        db.log_activity(
            session_id, f"Command rejected: '{plan.command}'",
            category="planner", status="warning",
            details=reason,
        )
        db.upsert_task(session_id, task_id, plan.command, "failed",
                       result=reason)
        return {
            "task_id": task_id,
            "status": "failed",
            "message": reason,
            "steps": steps_summary,
            "output": None,
        }

    db.log_activity(
        session_id, f"Plan created for: '{plan.command}'",
        category="planner", status="info",
        details=f"{len(plan.steps)} steps planned",
    )
    db.upsert_task(session_id, task_id, plan.command, "running",
                   steps=str([s.description for s in plan.steps]))

    final_output = None

    for step in plan.steps:
        steps_summary[step.step_id - 1]["status"] = "running"
        db.log_activity(
            session_id, f"Step {step.step_id}: {step.description}",
            category="executor", status="info",
        )

        # ── State-changing & Human-approval Security Gate ────────────────────
        is_state_changing = step.tool in STATE_CHANGING_TOOLS
        needs_approval = step.requires_approval or is_state_changing

        if needs_approval:
            if not approval_token:
                # If a caller attempts to use boolean approval_granted without a token, reject as bypass attempt
                if approval_granted:
                    err_msg = "Security violation: Missing approval token. Boolean approval flags cannot bypass authorization."
                    steps_summary[step.step_id - 1]["status"] = "failed"
                    for idx in range(step.step_id, len(steps_summary)):
                        if steps_summary[idx]["status"] == "pending":
                            steps_summary[idx]["status"] = "skipped"
                    db.log_activity(
                        session_id, f"AUTH BLOCKED: {err_msg}",
                        category="security", status="error",
                    )
                    db.upsert_task(session_id, task_id, plan.command, "failed", result=err_msg)
                    return {
                        "task_id": task_id,
                        "status": "failed",
                        "message": err_msg,
                        "steps": steps_summary,
                        "output": None,
                    }

                # Normal pending approval: issue a bound approval ticket
                target_action = step.tool
                target_params = dict(step.params)
                if step.tool == "human_approval":
                    subsequent_ops = [s for s in plan.steps[step.step_id:] if s.tool in STATE_CHANGING_TOOLS]
                    if subsequent_ops:
                        target_action = subsequent_ops[0].tool
                        target_params = dict(subsequent_ops[0].params)

                token = create_approval_ticket(
                    session_id=session_id,
                    task_id=task_id,
                    step_id=step.step_id,
                    action=target_action,
                    params=target_params,
                )

                steps_summary[step.step_id - 1]["status"] = "pending_approval"
                db.log_activity(
                    session_id,
                    f"Awaiting human approval for step {step.step_id}: {step.description}",
                    category="security", status="pending",
                )
                db.upsert_task(session_id, task_id, plan.command,
                               "pending_approval",
                               result="Waiting for human approval.")
                return {
                    "task_id": task_id,
                    "status": "pending_approval",
                    "approval_token": token,
                    "message": (
                        f"Step '{step.description}' requires your approval. "
                        "Click **Approve & Execute** to proceed."
                    ),
                    "steps": steps_summary,
                    "output": None,
                    "pending_step": step,
                }

        # ── Tool dispatch through Security Gateway ───────────────────────────
        # Pass approval token if this step is a state-changing tool
        token_for_step = approval_token if is_state_changing else None
        result = _dispatch_step(step, session_id, approval_token=token_for_step)

        if result.get("success") is False:
            steps_summary[step.step_id - 1]["status"] = "failed"
            # Immediately mark all remaining dependent steps as skipped (not left pending)
            for idx in range(step.step_id, len(steps_summary)):
                if steps_summary[idx]["status"] == "pending":
                    steps_summary[idx]["status"] = "skipped"

            err_msg = result.get("error", "Unknown error")
            db.log_activity(
                session_id, f"Step {step.step_id} FAILED: {err_msg}",
                category="executor", status="error",
            )
            db.upsert_task(session_id, task_id, plan.command, "failed",
                           result=err_msg)
            return {
                "task_id": task_id,
                "status": "failed",
                "message": err_msg,
                "steps": steps_summary,
                "output": result.get("data"),
            }

        steps_summary[step.step_id - 1]["status"] = "done"
        db.log_activity(
            session_id, f"Step {step.step_id} completed",
            category="executor", status="success",
        )
        final_output = result.get("data")

    # ── Post-execution Goal Verification ─────────────────────────────────────
    verified, v_msg = verify_goal_satisfaction(plan.command, steps_summary, final_output)
    if not verified:
        db.log_activity(
            session_id, f"TASK VERIFICATION FAILED: {v_msg}",
            category="executor", status="error",
        )
        db.upsert_task(session_id, task_id, plan.command, "failed", result=v_msg)
        return {
            "task_id": task_id,
            "status": "failed",
            "message": v_msg,
            "steps": steps_summary,
            "output": None,
        }

    db.upsert_task(session_id, task_id, plan.command, "done",
                   result=str(final_output)[:500])
    return {
        "task_id": task_id,
        "status": "done",
        "message": "All steps completed successfully.",
        "steps": steps_summary,
        "output": final_output,
    }


def _dispatch_step(step: TaskStep, session_id: str, approval_token: Optional[str] = None) -> dict:
    """Route a TaskStep through the independent security gateway."""
    t = step.tool
    params = step.params or {}

    # 1. Independent Security Gateway check
    try:
        authorize_tool_invocation(
            tool_name=t,
            params=params,
            session_id=session_id,
            approval_token=approval_token,
        )
    except SecurityError as exc:
        db.log_activity(
            session_id,
            f"AUTH BLOCKED: tool '{t}' rejected: {exc}",
            category="security",
            status="error",
        )
        return {"success": False, "error": f"Security violation: {exc}"}

    db.log_activity(
        session_id,
        f"AUTH GRANTED: tool '{t}' authorized",
        category="security",
        status="info",
    )

    # 2. Tool Execution
    if t == "security_check":
        path = params.get("path")
        mode = params.get("mode", "read")
        if path:
            try:
                if mode == "write":
                    from sentientos.security import validate_create_file
                    validate_create_file(path, params.get("content", ""))
                else:
                    from sentientos.security import validate_read_file
                    validate_read_file(path)
            except SecurityError as exc:
                return {"success": False, "error": str(exc)}
        return {"success": True, "data": "Security check passed"}

    elif t == "list_workspace":
        return tool_list_workspace()

    elif t == "read_file":
        return tool_read_file(params.get("path", ""))

    elif t == "create_file":
        return tool_create_file(
            params.get("path", ""),
            params.get("content", ""),
        )

    elif t == "human_approval":
        return {"success": True, "data": "Approval confirmed"}

    elif t == "system_metrics":
        return {"success": True, "data": get_system_metrics()}

    elif t == "fetch_logs":
        limit = params.get("limit", 10)
        logs = db.get_recent_activity(limit=limit)
        return {"success": True, "data": logs}

    elif t == "fetch_help":
        return {"success": True, "data": HELP_TEXT}

    elif t == "fetch_policy":
        return {"success": True, "data": describe_policy()}

    elif t == "clear_log":
        keep = params.get("keep", 200)
        db.clear_old_logs(keep=keep)
        return {"success": True, "data": "Activity log trimmed."}

    else:
        return {"success": False, "error": f"Unknown tool: '{t}'"}