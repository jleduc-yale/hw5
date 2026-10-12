"""Boss: reads the ticket queue, routes each ticket to the right specialist, owns ticket status."""

from config import BOSS_LIMITS, BOSS_SETTINGS
from models import ShiftReport

from .base import AgentSpec

SPEC = AgentSpec(
    name="boss",
    title="Shop manager",
    role="Owns the ticket queue: triages tickets, delegates, sets ticket status, writes the shift handoff.",
    mcp_tools=frozenset({
        "get_business_date",
        "list_open_tickets",
        "get_ticket_details",
        "update_ticket_status",
        "add_desk_note",
    }),
    output_type=ShiftReport,
    limits=BOSS_LIMITS,
    settings=BOSS_SETTINGS,
)
