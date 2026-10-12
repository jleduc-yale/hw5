# Campus Customs MCP Server

An [MCP](https://modelcontextprotocol.io) server built with [FastMCP](https://gofastmcp.com) that gives our Campus Customs agents tools for working with the shop's back-office database. Every agent in later problems connects to this server instead of querying SQLite directly, so all database access goes through one small, reviewable set of tools.

## Main uses

- Give agents the facts they need to work through the open tickets: the ticket queue, stock levels, vendors, rent, invoices, cash, and product pricing.
- Let agents record the outcome of their work (pull stock for an order, pay a bill, update a ticket, leave a handoff note) through write tools that enforce the shop's hard rules on the server.
- Make sure every number an agent quotes or acts on comes **directly from the database**. Tools return only database values (and `found: false` when a lookup misses). They never fill in or guess data.
- Keep database access safe. Read tools open the database **read-only**. Write tools run in one transaction and refuse anything that breaks a shop rule: stock never goes negative; payments must match the bill exactly, name a human approver, not double-pay, and not overdraw; tickets accept only valid statuses.

## Database

- **File:** `data/campus_customs_new.db` (SQLite). The path is resolved relative to this folder, so the server works from any working directory.
- This is the working copy of `data/campus_customs.db`. The original is never touched.
- Tables: `desk`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, `invoices`, `tickets`. See `output/harness.md` for every field and how the tables relate.

## Tools

| Tool | Arguments | Reads | Returns |
|---|---|---|---|
| `check_stock_for_sku_and_size` | `sku: str`, `size: str` | `inventory` | Product name, quantity on hand, in-stock flag, aisle location, and the quantity for every size of that SKU. |
| `get_rent_due_and_cash_balance` | `lease_id: int` | `leases`, `cash_accounts`, `payments`, `desk` | Landlord, monthly rent, next due date, today's business date, cash account balances, and any rent payments already recorded for the lease. |
| `get_price_and_cost_for_sku` | `sku: str` | `pricing` | List price and unit cost (the floor for any discount). |
| `get_business_date` | none | `desk` | The shop's business date (`date_today`) and the shared desk notes. |
| `list_open_tickets` | none | `tickets` | Count and full rows of every ticket that is not resolved, oldest first. |
| `list_all_tickets` | none | `tickets` | Count and full rows of every ticket, resolved or not, oldest first (used by the desk API's ticket list). |
| `get_ticket_details` | `ticket_id: int` | `tickets` | One ticket in full: type, requester, subject, SKU/size/qty, `lease_id`, `invoice_id`, status, notes, created time. |
| `list_vendors` | none | `vendors` | Every vendor's id, name, specialty, and lead time in days. |
| `get_invoice_details` | `invoice_id: int` | `invoices`, `vendors`, `payments`, `desk` | Invoice amount, due date, status, and description; the vendor; days overdue relative to the business date; and any payments already recorded. |
| `get_cash_account_balances` | none | `cash_accounts` | Every cash account's name, balance, and last-updated date. |

### Write tools

| Tool | Arguments | Reads / writes | Returns |
|---|---|---|---|
| `decrement_inventory_for_order` | `ticket_id: int`, `sku: str`, `size: str`, `qty: int` | `tickets`, `inventory` (writes `inventory.qty` and appends a ticket note) | `ok` with qty before and after, or a refusal reason if qty ≤ 0, the SKU/size doesn't match the ticket, qty exceeds the request, or stock is short. |
| `record_payment` | `kind: str` (`rent` or `invoice`), `ref_id: int`, `amount: float`, `account: str`, `approved_by: str` | `invoices` or `leases`, `payments`, `cash_accounts`, `desk` (writes a `payments` row, the account balance, and the invoice status or the lease's next due date) | `ok` with payment id, balance before and after, and the updated bill; or a refusal if the approver is missing or an agent, the amount is not exactly the bill, the bill is already paid or rent isn't due within 14 days, or funds are insufficient. |
| `update_ticket_status` | `ticket_id: int`, `status: str`, `note: str`, `author: str` | `tickets` (writes status and appends a dated note) | Old and new status, or a refusal for an invalid status, an empty note, or an already-resolved ticket. |
| `add_desk_note` | `note: str`, `author: str` | `desk` (appends a dated note) | `ok`, or a refusal for an empty note. |

The agent backend fills in `author` and `approved_by` itself (the calling agent's name, and the human who confirmed the payment), so the model never chooses them.

## Setup

From the `HW 5` folder:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Running

```bash
.venv/bin/python mcp_server/server.py
```

This starts the server over stdio, the default transport that MCP clients and agents connect to. You normally don't start it by hand: Claude Code launches it from `.mcp.json`, the agent team (`backend/cli.py`) launches it automatically for each run, and the desk API (`backend/main.py`) talks to it in-process.
