"""Campus Customs desk API (FastAPI).

Run from the backend/ folder:

    ../.venv/bin/uvicorn main:app --reload --port 8000

Shop data is read and written through the campus-customs MCP server (the
same tools the agents use), never with direct SQL. The only exception is
/api/reset, which replaces the whole database file with the original copy.
Agent activity comes from output/audit_trail.json, which the agent team
appends to on every run.
"""

import asyncio
import importlib.util
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import Client
from pydantic import BaseModel, Field

import approvals
from audit import AUDIT_PATH, AuditTrail
from config import HW_DIR
from shop_agents import ALL_SPECS, build_team
from shop_agents.base import new_run_id

ORIGINAL_DB = HW_DIR / "data" / "campus_customs.db"
WORKING_DB = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or HW_DIR / "data" / "campus_customs_new.db")
SERVER_SCRIPT = HW_DIR / "mcp_server" / "server.py"

# Load the MCP server module once and talk to it in-process over the MCP protocol.
_spec = importlib.util.spec_from_file_location("campus_customs_mcp_server", SERVER_SCRIPT)
_mcp_server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mcp_server)

AGENT_TITLES = {s.name: s.title for s in ALL_SPECS}
audit = AuditTrail()
_decision_lock = asyncio.Lock()  # one approval decision at a time, so a double click cannot pay twice

app = FastAPI(
    title="Campus Customs Desk API",
    description="Tickets, agent activity, payment approvals, cash, and DB reset for the Campus Customs agent team.",
)
# The Vite dev server (npm run dev) serves the dashboard on port 5173; other local ports are allowed for previews.
VITE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=VITE_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def call_mcp(tool: str, **args: Any) -> dict:
    async with Client(_mcp_server.mcp) as client:
        result = await client.call_tool(tool, args)
    return result.structured_content or {}


def load_audit_events() -> list[dict]:
    if not AUDIT_PATH.exists() or AUDIT_PATH.stat().st_size == 0:
        return []
    try:
        events = json.loads(AUDIT_PATH.read_text())
    except json.JSONDecodeError:
        raise HTTPException(500, "output/audit_trail.json is not valid JSON")
    for i, e in enumerate(events):
        e["id"] = i  # stable cursor: the trail is append-only
    return events


def active_run_ids(events: list[dict]) -> list[str]:
    started = [e["run_id"] for e in events if e["event"] == "team_run_start"]
    ended = {e["run_id"] for e in events if e["event"] == "team_run_end"}
    return [r for r in started if r not in ended]


def ticket_state(status: str) -> str:
    return "resolved" if status == "resolved" else "open"


def _mentions_ticket(text: Any, ticket_id: int) -> bool:
    return isinstance(text, str) and re.search(rf"\b(?:ticket|#)\s*#?\s*{ticket_id}\b", text, re.I) is not None


def _output_mentions_ticket(output: Any, ticket_id: int) -> list[str]:
    """Agents named in a run's final output as working this ticket (empty list = not mentioned)."""
    if not isinstance(output, dict):
        return []
    if ticket_id in (output.get("ticket_ids") or []):
        return ["self"]
    for t in output.get("tickets") or []:
        if t.get("ticket_id") == ticket_id:
            return ["self", *(t.get("handled_by") or [])]
    return []


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


@app.get("/api/tickets")
async def list_tickets() -> dict:
    """All tickets with their current status from the database."""
    data = await call_mcp("list_all_tickets")
    desk = await call_mcp("get_business_date")
    tickets = [
        {**t, "state": ticket_state(t["status"]), "is_resolved": t["status"] == "resolved"}
        for t in data.get("tickets", [])
    ]
    return {
        "business_date": desk.get("date_today"),
        "active_run": current_run_info(),
        "count": len(tickets),
        "open": sum(not t["is_resolved"] for t in tickets),
        "resolved": sum(t["is_resolved"] for t in tickets),
        "tickets": tickets,
    }


@app.get("/api/tickets/{ticket_id}/agents")
async def agents_on_ticket(
    ticket_id: int,
    run_id: str | None = Query(None, description="Team run to inspect; default is the latest run that touched this ticket. Use 'all' for every run."),
) -> dict:
    """Which agents worked (or are working) on a ticket, from the audit trail."""
    ticket = await call_mcp("get_ticket_details", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(404, f"ticket {ticket_id} not found")

    events = load_audit_events()

    # 1. Agent runs that touched this ticket: their prompt names it, they called a tool with its id,
    #    or their final output lists it. A "dedicated" run was started specifically for this ticket.
    touching: dict[str, dict] = {}  # agent_run_id -> {agent, run_id, dedicated}
    extra_agents: dict[str, set[str]] = {}  # run_id -> agents named in a Boss outcome's handled_by
    for e in events:
        arid, data = e.get("agent_run_id"), e.get("data", {})
        hit, dedicated = False, False
        if e["event"] == "agent_run_start" and _mentions_ticket(data.get("prompt"), ticket_id):
            hit = dedicated = True
        elif e["event"] == "mcp_tool_call" and (data.get("args") or {}).get("ticket_id") == ticket_id:
            hit = True
        elif e["event"] == "agent_run_end":
            named = _output_mentions_ticket(data.get("output"), ticket_id)
            if named:
                hit = True
                extra_agents.setdefault(e["run_id"], set()).update(a for a in named if a != "self")
        if hit and arid:
            info = touching.setdefault(arid, {"agent": e["agent"], "run_id": e["run_id"], "dedicated": False})
            info["dedicated"] |= dedicated

    run_ids = [info["run_id"] for info in touching.values()]
    if not run_ids:
        return {"ticket_id": ticket_id, "status": ticket["status"], "state": ticket_state(ticket["status"]),
                "run_id": None, "agents": []}
    selected = run_ids[-1] if run_id is None else run_id
    if selected != "all" and selected not in run_ids:
        raise HTTPException(404, f"run {selected} did not touch ticket {ticket_id}")

    # 2. Summarize each agent: its runs, the MCP tools it used for this ticket, whether it is still running.
    ended = {e["agent_run_id"]: e for e in events if e["event"] == "agent_run_end"}
    agents: dict[str, dict] = {}
    for arid, info in touching.items():
        if selected != "all" and info["run_id"] != selected:
            continue
        a = agents.setdefault(info["agent"], {
            "agent": info["agent"], "title": AGENT_TITLES.get(info["agent"]),
            "agent_run_ids": [], "tools_used": [], "active": False, "first_seen": None, "last_seen": None,
        })
        a["agent_run_ids"].append(arid)
        a["active"] |= arid not in ended
        for e in events:
            if e.get("agent_run_id") != arid:
                continue
            a["first_seen"] = a["first_seen"] or e["timestamp"]
            a["last_seen"] = e["timestamp"]
            # A payment queued for approval never reaches the MCP server, so count its approval event too.
            if e["event"] == "mcp_tool_call" or (e["event"] == "human_approval" and e["data"].get("tool")):
                args = e["data"].get("args") or {}
                about_this = args.get("ticket_id") == ticket_id or ("ticket_id" not in args and info["dedicated"])
                if about_this and e["data"]["tool"] not in a["tools_used"]:
                    a["tools_used"].append(e["data"]["tool"])

    for rid, names in extra_agents.items():
        if selected in ("all", rid):
            for name in names:
                agents.setdefault(name, {"agent": name, "title": AGENT_TITLES.get(name), "agent_run_ids": [],
                                         "tools_used": [], "active": False, "first_seen": None, "last_seen": None})

    return {
        "ticket_id": ticket_id,
        "status": ticket["status"],
        "state": ticket_state(ticket["status"]),
        "run_id": selected,
        "agents": list(agents.values()),
    }


# ---------------------------------------------------------------------------
# Agent activity feed
# ---------------------------------------------------------------------------


def _feed_items(e: dict) -> list[dict]:
    """Turn one audit event into zero or more feed items (tool use and what agents said)."""
    base = {"id": e["id"], "timestamp": e["timestamp"], "run_id": e["run_id"],
            "agent": e.get("agent"), "chain": e.get("chain", [])}
    d, ev = e.get("data", {}), e["event"]

    if ev == "team_run_start":
        return [{**base, "kind": "run_started", "text": d.get("prompt"), "detail": d}]
    if ev == "team_run_end":
        return [{**base, "kind": "run_finished", "text": f"{d.get('agent_runs')} agent runs, "
                 f"{d.get('delegations')} delegations, {d.get('total_tokens')} tokens", "detail": d}]
    if ev == "agent_run_start":
        return [{**base, "kind": "agent_started", "text": d.get("prompt"),
                 "detail": {"requested_by": d.get("requested_by")}}]
    if ev == "agent_step" and d.get("node") == "model_response":
        kinds = {"text": "agent_said", "thinking": "agent_thought"}
        return [{**base, "kind": kinds[p["part_kind"]], "text": p["content"], "detail": {"step": e.get("step")}}
                for p in d.get("parts", []) if p.get("part_kind") in kinds and p.get("content")]
    if ev == "mcp_tool_call":
        return [{**base, "kind": "tool_call", "tool": d.get("tool"), "text": f"called {d.get('tool')}",
                 "detail": {"args": d.get("args")}}]
    if ev == "mcp_tool_result":
        return [{**base, "kind": "tool_result", "tool": d.get("tool"), "text": f"{d.get('tool')} returned",
                 "detail": {"result": d.get("result"), "error": d.get("error")}}]
    if ev == "delegation":
        verb = "asked" if d.get("accepted") else "was refused asking"
        return [{**base, "kind": "delegation", "text": f"{e.get('agent')} {verb} {d.get('to')}: {d.get('request')}",
                 "detail": d}]
    if ev == "human_approval":
        status = d.get("status") or ("approved" if d.get("approved") else "declined")
        args = d.get("args") or {}
        what = f"{args.get('kind')} #{args.get('ref_id')} for ${args.get('amount')}" if args else ""
        text = {"waiting": f"waiting for a human to approve {what}", "queued": f"queued {what} for human approval",
                "timed_out": "approval timed out; payment stays queued"}.get(status, f"payment {what} {status}")
        return [{**base, "kind": "approval", "text": text,
                 "detail": d}]
    if ev == "agent_run_end":
        out = d.get("output") or {}
        said = out.get("summary") or out.get("desk_note") if isinstance(out, dict) else None
        items = [{**base, "kind": "agent_finished", "text": said or d.get("error"),
                  "detail": {"status": d.get("status"), "output": out, "usage": d.get("usage"), "seconds": d.get("seconds")}}]
        if isinstance(out, dict) and out.get("customer_message"):
            items.append({**base, "kind": "customer_reply", "text": out["customer_message"], "detail": {}})
        return items
    if ev == "db_reset":
        return [{**base, "kind": "db_reset", "text": "database reset to the original", "detail": d}]
    return []


@app.get("/api/events")
async def recent_events(
    after: int | None = Query(None, description="Only events with id greater than this (poll with the last latest_id)."),
    limit: int = Query(100, ge=1, le=1000),
    run_id: str | None = Query(None, description="Only this team run; 'latest' for the most recent run."),
    agent: str | None = Query(None),
) -> dict:
    """Recent agent activity: tools used, what agents said, delegations, approvals."""
    events = load_audit_events()
    if run_id == "latest":
        starts = [e["run_id"] for e in events if e["event"] == "team_run_start"]
        run_id = starts[-1] if starts else None
    selected = [e for e in events
                if (after is None or e["id"] > after)
                and (run_id is None or e["run_id"] == run_id)
                and (agent is None or e.get("agent") == agent)]
    items = [item for e in selected for item in _feed_items(e)]
    items = items[:limit] if after is not None else items[-limit:]
    return {
        "latest_id": events[-1]["id"] if events else -1,
        "active_runs": active_run_ids(events),
        "count": len(items),
        "events": items,
    }


# ---------------------------------------------------------------------------
# Payment approvals
# ---------------------------------------------------------------------------


class ApprovalDecision(BaseModel):
    approver: str = Field(min_length=1, description="Full name of the human approving or rejecting.")
    confirm: bool = Field(description="Must be true: the human has reviewed the payment and confirms the decision.")
    reason: str | None = None


@app.get("/api/approvals")
async def get_approvals(status: str | None = Query("pending", description="pending, approved, rejected, failed, or all")) -> dict:
    """Payments the agents asked for, waiting on (or decided by) a human."""
    items = approvals.list_approvals(None if status == "all" else status)
    return {"count": len(items), "approvals": [{**i, "details": await _payment_details(i["args"])} for i in items]}


async def _payment_details(args: dict) -> dict:
    """Who is being paid and for what, looked up through MCP so the human can check it."""
    kind, ref = args.get("kind"), args.get("ref_id")
    if kind == "invoice":
        inv = await call_mcp("get_invoice_details", invoice_id=ref)
        if inv.get("found"):
            return {"payee": (inv.get("vendor") or {}).get("name"), "label": "Vendor invoice",
                    "description": inv.get("description"), "amount_due": inv.get("amount"),
                    "due_date": inv.get("due_date"), "days_overdue": inv.get("days_overdue"), "bill_status": inv.get("status")}
    if kind == "rent":
        lease = await call_mcp("get_rent_due_and_cash_balance", lease_id=ref)
        if lease.get("found"):
            return {"payee": lease.get("landlord"), "label": "Rent", "description": f"Monthly rent, {lease.get('space_name')}",
                    "amount_due": lease.get("monthly_rent"), "due_date": lease.get("next_due")}
    return {"payee": None, "label": kind, "description": None}


async def _pending_or_error(approval_id: int, body: ApprovalDecision) -> dict:
    item = approvals.get_approval(approval_id)
    if item is None:
        raise HTTPException(404, f"approval {approval_id} not found")
    if item["status"] != "pending":
        raise HTTPException(409, f"approval {approval_id} is already {item['status']}")
    if not body.confirm:
        raise HTTPException(400, "a human must confirm the decision (confirm: true)")
    if not body.approver.strip():
        raise HTTPException(400, "approver name is required")
    return item


@app.post("/api/approvals/{approval_id}/approve")
async def approve_payment(approval_id: int, body: ApprovalDecision) -> dict:
    """Human confirms a queued payment; it is made through the MCP server with their name as approver."""
    async with _decision_lock:
        item = await _pending_or_error(approval_id, body)
        approver = body.approver.strip()
        if approvals.agent_is_waiting(approval_id):
            # A dashboard run is paused on this payment: hand the decision to the agent, which pays and carries on.
            result = await approvals.hand_decision_to_agent(approval_id, approvals.Decision(True, approver))
            item = approvals.get_approval(approval_id)
            status = item["status"]
        else:
            result = await call_mcp("record_payment", **item["args"], approved_by=approver)
            status = "approved" if result.get("ok") else "failed"
            item = approvals.mark_decided(approval_id, status, approver, result)
        audit.record(item["run_id"], "human_approval", tool="record_payment", approval_id=approval_id,
                     status=status, approver=approver, args=item["args"], result=result, via="dashboard")
    if status == "failed":
        raise HTTPException(409, {"message": "the MCP server refused the payment", "approval": item})
    return item


@app.post("/api/approvals/{approval_id}/reject")
async def reject_payment(approval_id: int, body: ApprovalDecision) -> dict:
    """Human declines a queued payment; nothing is paid."""
    async with _decision_lock:
        item = await _pending_or_error(approval_id, body)
        approver = body.approver.strip()
        waiting = approvals.agent_is_waiting(approval_id)
        item = approvals.mark_decided(approval_id, "rejected", approver, {"reason": body.reason})
        if waiting:
            await approvals.hand_decision_to_agent(approval_id, approvals.Decision(False, approver, body.reason))
        audit.record(item["run_id"], "human_approval", tool="record_payment", approval_id=approval_id,
                     status="rejected", approver=approver, args=item["args"], reason=body.reason, via="dashboard")
    return item


# ---------------------------------------------------------------------------
# Starting the agent team
# ---------------------------------------------------------------------------

_current_run: dict | None = None  # the one team run this server is executing (runs are one at a time)


def current_run_info() -> dict | None:
    if _current_run is None:
        return None
    task: asyncio.Task = _current_run["task"]
    info = {k: v for k, v in _current_run.items() if k != "task"}
    info["running"] = not task.done()
    if task.done():
        exc = task.exception() if not task.cancelled() else None
        info["error"] = f"{type(exc).__name__}: {exc}" if exc else None
        info["ok"] = exc is None and bool((task.result() or {}).get("ok"))
    return info


@app.post("/api/tickets/{ticket_id}/run")
async def start_ticket_run(ticket_id: int) -> dict:
    """Start the agent team (Boss first) on one ticket, in the background. Payments wait for dashboard approval."""
    global _current_run
    if _current_run is not None and not _current_run["task"].done():
        raise HTTPException(409, {"message": "the agent team is already working", "run": current_run_info()})
    ticket = await call_mcp("get_ticket_details", ticket_id=ticket_id)
    if not ticket.get("found"):
        raise HTTPException(404, f"ticket {ticket_id} not found")
    if ticket["status"] == "resolved":
        raise HTTPException(409, f"ticket {ticket_id} is already resolved")

    run_id = new_run_id()
    prompt = (f"Work ticket {ticket_id} from start to finish following the shop rules. "
              f"Handle only ticket {ticket_id}; leave the other tickets alone.")
    team = build_team(audit=audit)
    task = asyncio.create_task(team.run(prompt, run_id=run_id, approval_mode="dashboard", ticket_id=ticket_id))
    _current_run = {"run_id": run_id, "ticket_id": ticket_id,
                    "started_at": datetime.now(timezone.utc).isoformat(), "task": task}
    return current_run_info()


@app.get("/api/runs/current")
async def get_current_run() -> dict:
    """The team run this server started most recently (running or finished), or null."""
    return {"run": current_run_info()}


# ---------------------------------------------------------------------------
# Cash
# ---------------------------------------------------------------------------


@app.get("/api/cash/checking")
async def checking_balance() -> dict:
    """Current balance of the checking account (cash_accounts)."""
    data = await call_mcp("get_cash_account_balances")
    acct = next((a for a in data.get("cash_accounts", []) if a["name"] == "checking"), None)
    if acct is None:
        raise HTTPException(404, "no 'checking' account in cash_accounts")
    return {"account": acct["name"], "balance": acct["balance"], "as_of": acct["date"]}


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class ResetRequest(BaseModel):
    confirm: bool = Field(description="Must be true. Replaces campus_customs_new.db with the original.")
    force: bool = Field(False, description="Reset even if the audit trail shows an agent run still in progress.")


@app.post("/api/reset")
async def reset_database(body: ResetRequest) -> dict:
    """Restore data/campus_customs_new.db from data/campus_customs.db for a fresh run."""
    if not body.confirm:
        raise HTTPException(400, "set confirm: true to reset the database")
    if _current_run is not None and not _current_run["task"].done():
        raise HTTPException(409, {"message": "the agent team is working right now; wait for it to finish"})
    running = active_run_ids(load_audit_events())
    if running and not body.force:
        raise HTTPException(409, {"message": "an agent run may still be in progress; retry with force: true",
                                  "active_runs": running})

    tmp = WORKING_DB.with_suffix(".db.tmp")
    shutil.copy2(ORIGINAL_DB, tmp)
    os.replace(tmp, WORKING_DB)  # atomic swap: readers never see a half-copied file
    for suffix in ("-wal", "-shm", "-journal"):
        stale = WORKING_DB.with_name(WORKING_DB.name + suffix)
        if stale.exists():
            stale.unlink()
    cleared = approvals.clear_all()

    reset_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-reset-" + uuid.uuid4().hex[:4]
    audit.record(reset_id, "db_reset", source=ORIGINAL_DB.name, target=WORKING_DB.name,
                 cleared_pending_approvals=cleared, forced=body.force)

    tickets = await list_tickets()
    cash = await checking_balance()
    return {
        "ok": True,
        "reset_id": reset_id,
        "cleared_pending_approvals": cleared,
        "checking": cash,
        "tickets": [{"id": t["id"], "status": t["status"]} for t in tickets["tickets"]],
    }
