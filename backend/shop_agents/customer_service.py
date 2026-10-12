"""Customer Service: understands what the customer wants and writes the reply they receive."""

from config import SPECIALIST_LIMITS, SPECIALIST_SETTINGS
from models import SpecialistReport

from .base import AgentSpec

SPEC = AgentSpec(
    name="customer_service",
    title="Customer service lead",
    role="Talks to customers and student groups: checks what they asked for and drafts the reply they receive.",
    mcp_tools=frozenset({
        "get_business_date",
        "get_ticket_details",
        "check_stock_for_sku_and_size",
    }),
    output_type=SpecialistReport,
    limits=SPECIALIST_LIMITS,
    settings=SPECIALIST_SETTINGS,
)
