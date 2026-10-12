"""The single path from the agents to the database: the campus-customs MCP server.

Agents never open SQLite themselves. One MCPToolset (one stdio server process)
is shared by the whole team; each agent gets a filtered view of only the tools
its role allows. Every MCP call passes through `_process_tool_call`, which
writes the call and result to the audit trail and fills in fields the model
must not control (who wrote a note, which human approved a payment).
"""

import asyncio
import json
import os
import sys
from dataclasses import replace

from fastmcp.client.transports import PythonStdioTransport
from pydantic_ai import RunContext
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import AbstractToolset

from approvals import finish_payment, queue_payment, wait_for_decision
from config import APPROVAL_TIMEOUT_SECONDS, HW_DIR
from models import AgentDeps

SERVER_SCRIPT = HW_DIR / "mcp_server" / "server.py"

# Arguments filled in by the system, hidden from the model's view of the tool.
SYSTEM_FILLED_ARGS = {
    "update_ticket_status": ("author",),
    "add_desk_note": ("author",),
    "record_payment": ("approved_by",),
}


def _refusal(reason: str) -> dict:
    return {"ok": False, "refused": True, "reason": reason}


async def _ask_human_to_approve(deps: AgentDeps, args: dict) -> bool:
    """Per-payment human sign-off at the terminal (interactive CLI runs only)."""
    question = (
        f"\n[APPROVAL NEEDED] {deps.agent} wants to pay {args.get('kind')} #{args.get('ref_id')}: "
        f"${args.get('amount')} from '{args.get('account')}'.\n"
        f"Approve as {deps.run.approver}? Type 'yes' to approve: "
    )
    answer = await asyncio.to_thread(input, question)
    return answer.strip().lower() == "yes"


async def _pay_after_dashboard_approval(deps: AgentDeps, call_tool: CallToolFunc, args: dict):
    """Queue the payment, wait for a human on the dashboard, then pay with their name (or report the refusal)."""
    audit, run_id = deps.run.audit, deps.run.run_id
    item = queue_payment(args, run_id, deps.agent, deps.agent_run_id, waiting=True)
    approval_id = item["approval_id"]
    audit.record(run_id, "human_approval", deps, tool="record_payment", args=args,
                 status="waiting", approval_id=approval_id)

    decision = await wait_for_decision(approval_id, APPROVAL_TIMEOUT_SECONDS)
    if decision is None:
        audit.record(run_id, "human_approval", deps, tool="record_payment", approval_id=approval_id,
                     status="timed_out")
        return {"ok": False, "pending_approval": True, "approval_id": approval_id,
                "reason": f"No human decided within {APPROVAL_TIMEOUT_SECONDS // 60} minutes. NOT paid; it stays "
                "queued. Do not retry; report needs_human with this approval id."}
    if not decision.approved:
        return _refusal(f"{decision.approver} declined this payment"
                        + (f" ({decision.reason})" if decision.reason else "") + ". NOT paid. Do not retry; escalate.")

    args = {**args, "approved_by": decision.approver}
    audit.record(run_id, "mcp_tool_call", deps, tool="record_payment", args=args)
    try:
        result = await call_tool("record_payment", args)
    except Exception as exc:
        audit.record(run_id, "mcp_tool_result", deps, tool="record_payment", error=repr(exc))
        finish_payment(approval_id, decision.approver, {"ok": False, "error": repr(exc)})
        raise
    audit.record(run_id, "mcp_tool_result", deps, tool="record_payment", result=result)
    finish_payment(approval_id, decision.approver, result if isinstance(result, dict) else {"ok": False, "raw": str(result)})
    return result


async def _process_tool_call(ctx: RunContext[AgentDeps], call_tool: CallToolFunc, name: str, args: dict):
    deps = ctx.deps
    audit = deps.run.audit
    args = dict(args)

    if name in ("update_ticket_status", "add_desk_note"):
        args["author"] = deps.agent

    if name == "record_payment":
        mode = deps.run.approval_mode
        if mode == "dashboard":
            return await _pay_after_dashboard_approval(deps, call_tool, args)
        if not (mode == "terminal" and deps.run.approver):
            # No human at the terminal: queue it for approval through the API instead of paying.
            item = queue_payment(args, deps.run.run_id, deps.agent, deps.agent_run_id)
            audit.record(deps.run.run_id, "human_approval", deps, tool=name, args=args,
                         status="queued", approval_id=item["approval_id"])
            return {
                "ok": False,
                "pending_approval": True,
                "approval_id": item["approval_id"],
                "reason": f"Payment queued for human approval (approval id {item['approval_id']}). It has NOT "
                "been paid. Do not retry; report needs_human with this approval id.",
            }
        approved = await _ask_human_to_approve(deps, args)
        audit.record(deps.run.run_id, "human_approval", deps, tool=name, args=args,
                     approver=deps.run.approver, approved=approved)
        if not approved:
            return _refusal(f"{deps.run.approver} did not approve this payment. Escalate; do not retry.")
        args["approved_by"] = deps.run.approver

    audit.record(deps.run.run_id, "mcp_tool_call", deps, tool=name, args=args)
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        audit.record(deps.run.run_id, "mcp_tool_result", deps, tool=name, error=repr(exc))
        raise
    audit.record(deps.run.run_id, "mcp_tool_result", deps, tool=name, result=result)
    return result


def _hide_system_filled_args(ctx: RunContext[AgentDeps], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    out = []
    for td in tool_defs:
        hidden = SYSTEM_FILLED_ARGS.get(td.name)
        if hidden:
            schema = json.loads(json.dumps(td.parameters_json_schema))
            for arg in hidden:
                schema.get("properties", {}).pop(arg, None)
                if arg in schema.get("required", []):
                    schema["required"].remove(arg)
            td = replace(td, parameters_json_schema=schema)
        out.append(td)
    return out


def create_mcp_toolset() -> MCPToolset:
    """One connection to the campus-customs MCP server, launched with this venv's Python."""
    # Forward the scratch-DB override (offline tests only); otherwise the server uses campus_customs_new.db.
    env = {"CAMPUS_CUSTOMS_DB": os.environ["CAMPUS_CUSTOMS_DB"]} if "CAMPUS_CUSTOMS_DB" in os.environ else None
    transport = PythonStdioTransport(SERVER_SCRIPT, python_cmd=sys.executable, cwd=str(HW_DIR), env=env)
    return MCPToolset(transport, id="campus-customs", process_tool_call=_process_tool_call)


def tools_for_agent(shared: MCPToolset, allowed: frozenset[str]) -> AbstractToolset[AgentDeps]:
    """The subset of MCP tools one agent may see and call."""
    return shared.filtered(lambda ctx, td: td.name in allowed).prepared(_hide_system_filled_args)
