"""Data types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from audit import AuditTrail

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
ApprovalMode = Literal["terminal", "dashboard", "queue"]
TicketStatus = Literal[
    "open", "in_progress", "waiting_on_customer", "waiting_on_vendor", "escalated", "resolved"
]


# ---------------------------------------------------------------------------
# Run state (agent dependencies)
# ---------------------------------------------------------------------------


@dataclass
class TeamRun:
    """State shared by every agent loop in one team run (one `python backend/main.py`)."""

    run_id: str
    audit: AuditTrail
    approver: str | None = None  # terminal mode only: the human typing 'yes' at the CLI
    # How a payment gets its human sign-off:
    #   terminal  - ask the approver at the CLI, per payment
    #   dashboard - queue it and wait for a human to approve/decline on the dashboard, then continue
    #   queue     - queue it for later approval and tell the agent it is pending (agent does not wait)
    approval_mode: ApprovalMode = "queue"
    delegations: int = 0  # ask_teammate calls so far (team-wide budget)
    total_tokens: int = 0  # tokens used by all agent loops so far (team-wide budget)
    agent_runs: int = 0  # number of agent loops started, used for agent_run_id


@dataclass
class AgentDeps:
    """Dependencies for one agent loop. `chain` is the delegation path that led here."""

    run: TeamRun
    agent: AgentName
    agent_run_id: str
    chain: tuple[AgentName, ...] = field(default_factory=tuple)

    @property
    def depth(self) -> int:
        return len(self.chain) - 1


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


class SpecialistReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service hands back to whoever asked."""

    ticket_ids: list[int] = Field(description="Tickets this report is about (empty if none).")
    summary: str = Field(description="Two to four sentences: what you found and what you did.")
    facts: list[str] = Field(
        description="Every number or fact you relied on, each with the MCP tool it came from, "
        "e.g. 'CC-TEE-WHITE S qty 0 (check_stock_for_sku_and_size)'."
    )
    actions_taken: list[str] = Field(
        description="Database changes you made through write tools, with their results. Empty if none."
    )
    recommended_status: TicketStatus | None = Field(
        description="The ticket status you recommend the Boss set, or null if not applicable."
    )
    needs_human: bool = Field(description="True if a human must approve or decide something before work continues.")
    human_action_needed: str | None = Field(description="Exactly what the human must do, if needs_human is true.")
    customer_message: str | None = Field(
        default=None, description="Customer Service only: the reply to send to the requester."
    )


class TicketOutcome(BaseModel):
    ticket_id: int
    final_status: TicketStatus
    handled_by: list[AgentName] = Field(description="Agents that worked on this ticket.")
    summary: str = Field(description="What was done and why, citing the facts from the specialists.")
    customer_reply: str | None = Field(description="Reply to send to the requester, if any.")
    human_action_needed: str | None = Field(description="What a human still has to do, if anything.")


class ShiftReport(BaseModel):
    """The Boss's final output for a team run."""

    tickets: list[TicketOutcome]
    desk_note: str = Field(description="The handoff summary also written to the desk notes.")


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

AuditEventType = Literal[
    "team_run_start",
    "team_run_end",
    "agent_run_start",
    "agent_step",
    "agent_run_end",
    "mcp_tool_call",
    "mcp_tool_result",
    "delegation",
    "human_approval",
    "db_reset",
]


class AuditEvent(BaseModel):
    """One entry appended to output/audit_trail.json."""

    timestamp: str
    run_id: str
    event: AuditEventType
    agent: AgentName | None = None
    agent_run_id: str | None = None
    chain: list[AgentName] = Field(default_factory=list)
    step: int | None = None
    data: dict[str, Any] = Field(default_factory=dict)
