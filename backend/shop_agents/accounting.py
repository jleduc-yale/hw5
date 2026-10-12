"""Accounting: cash, vendor invoices, rent payments (with human approval), and price/discount decisions."""

from config import SPECIALIST_LIMITS, SPECIALIST_SETTINGS
from models import SpecialistReport

from .base import AgentSpec

SPEC = AgentSpec(
    name="accounting",
    title="Bookkeeper",
    role="Cash balances, vendor invoices, rent and invoice payments (human-approved), pricing and discount decisions.",
    mcp_tools=frozenset({
        "get_business_date",
        "get_ticket_details",
        "get_cash_account_balances",
        "get_invoice_details",
        "get_rent_due_and_cash_balance",
        "get_price_and_cost_for_sku",
        "list_vendors",
        "record_payment",
    }),
    output_type=SpecialistReport,
    limits=SPECIALIST_LIMITS,
    settings=SPECIALIST_SETTINGS,
)
