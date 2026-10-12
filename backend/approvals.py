"""Payments waiting for a human, stored in output/pending_approvals.json.

An agent's `record_payment` call never pays on its own. The payment is queued
here and a human decides:

- dashboard runs: the agent's tool call *waits* (in this process) until a human
  approves or declines on the dashboard. On approval the agent's own call goes
  through to the MCP server with the human's name as `approved_by`, and the
  agent sees the real result and carries on.
- queue runs (CLI without a terminal approver): the agent is told the payment is
  pending and moves on; a human approving later makes the payment directly.
"""

import asyncio
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import HW_DIR

# CAMPUS_CUSTOMS_APPROVALS overrides the path for sandbox testing only.
APPROVALS_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_APPROVALS") or HW_DIR / "output" / "pending_approvals.json")
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> list[dict]:
    if not APPROVALS_PATH.exists() or APPROVALS_PATH.stat().st_size == 0:
        return []
    return json.loads(APPROVALS_PATH.read_text())


def _save(items: list[dict]) -> None:
    APPROVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = APPROVALS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=2))
    os.replace(tmp, APPROVALS_PATH)


def _update(approval_id: int, **fields) -> dict:
    with _lock:
        items = _load()
        item = next(i for i in items if i["approval_id"] == approval_id)
        item.update(fields)
        _save(items)
    return item


def queue_payment(args: dict, run_id: str, agent: str, agent_run_id: str, waiting: bool = False) -> dict:
    """Record a payment an agent asked for; nothing is paid yet."""
    with _lock:
        items = _load()
        item = {
            "approval_id": max((i["approval_id"] for i in items), default=0) + 1,
            "status": "pending",
            "tool": "record_payment",
            "args": {k: args[k] for k in ("kind", "ref_id", "amount", "account") if k in args},
            "requested_by": agent,
            "agent_run_id": agent_run_id,
            "run_id": run_id,
            "agent_waiting": waiting,
            "requested_at": _now(),
            "decided_by": None,
            "decided_at": None,
            "result": None,
        }
        items.append(item)
        _save(items)
    return item


def list_approvals(status: str | None = None) -> list[dict]:
    with _lock:
        items = _load()
    return [i for i in items if status is None or i["status"] == status]


def get_approval(approval_id: int) -> dict | None:
    return next((i for i in list_approvals() if i["approval_id"] == approval_id), None)


def mark_decided(approval_id: int, status: str, decided_by: str, result: dict | None) -> dict:
    """status: approved (payment made), rejected (human said no), or failed (server refused the payment)."""
    return _update(approval_id, status=status, decided_by=decided_by, decided_at=_now(), result=result,
                   agent_waiting=False)


def clear_all() -> int:
    """Used by DB reset: queued payments refer to the old database state."""
    with _lock:
        n = len(_load())
        _save([])
    return n


# ---------------------------------------------------------------------------
# Live hand-off between a waiting agent (dashboard runs) and the approve/reject routes
# ---------------------------------------------------------------------------


@dataclass
class Decision:
    approved: bool
    approver: str
    reason: str | None = None


_waiting_agents: dict[int, asyncio.Future] = {}  # approval_id -> future the agent awaits (Decision)
_payment_results: dict[int, asyncio.Future] = {}  # approval_id -> future the route awaits (payment result)


def agent_is_waiting(approval_id: int) -> bool:
    fut = _waiting_agents.get(approval_id)
    return fut is not None and not fut.done()


async def wait_for_decision(approval_id: int, timeout: float) -> Decision | None:
    """Called by the agent's tool call. Returns None if nobody decided in time."""
    fut = asyncio.get_running_loop().create_future()
    _waiting_agents[approval_id] = fut
    try:
        return await asyncio.wait_for(fut, timeout)
    except asyncio.TimeoutError:
        _update(approval_id, agent_waiting=False)  # still pending; a later approval pays directly
        return None
    finally:
        _waiting_agents.pop(approval_id, None)


async def hand_decision_to_agent(approval_id: int, decision: Decision, timeout: float = 60) -> dict | None:
    """Called by a route. Wakes the waiting agent; on approval, waits for the agent's payment result."""
    result_fut = asyncio.get_running_loop().create_future()
    if decision.approved:
        _payment_results[approval_id] = result_fut
    _waiting_agents[approval_id].set_result(decision)
    if not decision.approved:
        return None
    try:
        return await asyncio.wait_for(result_fut, timeout)
    finally:
        _payment_results.pop(approval_id, None)


def finish_payment(approval_id: int, approver: str, result: dict) -> dict:
    """Called by the agent's tool call after the MCP server answered."""
    item = mark_decided(approval_id, "approved" if result.get("ok") else "failed", approver, result)
    fut = _payment_results.get(approval_id)
    if fut is not None and not fut.done():
        fut.set_result(result)
    return item
