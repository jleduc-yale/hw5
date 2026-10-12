"""Facilities: the shop premises, the lease and landlord, and local courier logistics."""

from config import SPECIALIST_LIMITS, SPECIALIST_SETTINGS
from models import SpecialistReport

from .base import AgentSpec

SPEC = AgentSpec(
    name="facilities",
    title="Facilities manager",
    role="The shop lease and landlord (verifies rent notices against the lease), premises, local courier logistics.",
    mcp_tools=frozenset({
        "get_business_date",
        "get_ticket_details",
        "get_rent_due_and_cash_balance",
        "list_vendors",
    }),
    output_type=SpecialistReport,
    limits=SPECIALIST_LIMITS,
    settings=SPECIALIST_SETTINGS,
)
