"""Inventory: stock levels, shelf locations, restock planning, and pulling stock for confirmed orders."""

from config import SPECIALIST_LIMITS, SPECIALIST_SETTINGS
from models import SpecialistReport

from .base import AgentSpec

SPEC = AgentSpec(
    name="inventory",
    title="Stock manager",
    role="Stock on hand by SKU/size, shelf locations, restock vendors and dates, pulls stock for confirmed orders.",
    mcp_tools=frozenset({
        "get_business_date",
        "get_ticket_details",
        "check_stock_for_sku_and_size",
        "list_vendors",
        "get_invoice_details",
        "decrement_inventory_for_order",
    }),
    output_type=SpecialistReport,
    limits=SPECIALIST_LIMITS,
    settings=SPECIALIST_SETTINGS,
)
