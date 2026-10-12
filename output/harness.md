# Campus Customs Agent Desk: Project Harness

This file describes the whole HW 5 project: the database, the MCP server and its tools, the agent team, the API routes, the dashboard, the safety rules, and the final results. Sections were added problem by problem; the overview below is the map.

## Project at a glance

```
 Dashboard (frontend/, React+Vite+TS)  ──HTTP──▶  Desk API (backend/main.py, FastAPI :8000)
   http://localhost:5173                              │  starts team runs, approvals, cash, reset, event feed
                                                      ▼
                                   Agent team (backend/shop_agents/, PydanticAI, gpt-6-luna via Portkey)
                                   Boss ─▶ Inventory · Accounting · Facilities · Customer Service  (ask_teammate)
                                                      │  filtered MCP tools only (no direct SQL)
                                                      ▼
                                   campus-customs MCP server (mcp_server/server.py, FastMCP, 14 tools)
                                                      │
                                                      ▼
                       data/campus_customs_new.db   (working copy; data/campus_customs.db is the pristine original)

 Every run appends to output/audit_trail.json · payments wait in output/pending_approvals.json for a human
```

| Part | Where | Section in this file |
|---|---|---|
| Database tables and fields | `data/campus_customs_new.db` | *Campus Customs Database Harness* (Problem 2) |
| MCP server and all 14 tools (tables each one touches) | `mcp_server/server.py`, `mcp_server/README.md` | Problem 3, plus *All MCP tools* in Problem 5 |
| Agent team, prompts, data types, audit trail | `backend/shop_agents/`, `backend/prompts/`, `backend/models.py`, `backend/audit.py` | *Agent Team and Full MCP Toolset* (Problem 5) |
| API routes | `backend/main.py` | *Backend API Routes* (Problem 7) and *Dashboard and Run Routes* (Problem 8) |
| Dashboard | `frontend/` (`npm run dev`), design notes in `output/design.md` | Problem 8 |
| Safety rules | server, backend, prompts | *Safety rules enforced in this build* (Problem 9), plus *Safety for a real business* (Problem 5) |
| Results | `output/desk_tickets.html`, `output/resolved_tickets.json`, `output/resolved_board.html` | *Final Results* (Problem 9) |

**How to run it**

```bash
# from HW 5/ : one-time setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd frontend && npm install && cd ..
# terminal 1: API (also starts agent runs)
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000
# terminal 2: dashboard
cd frontend && npm run dev          # http://localhost:5173
```

Pick a ticket and click **Start agent team**. Approve or decline payments in the approval card. **Reset data** restores the original database. The agents can also be run headless with `.venv/bin/python backend/cli.py --ticket 101`.

---

# Campus Customs Database Harness (Problem 2)

Source: `data/campus_customs.db` (SQLite, read-only reference copy).
Working copy: `data/campus_customs_new.db`. All later problems write only to this file.

**Context:** Campus Customs is a small Yale merchandise shop. The database is the shop's back office for one business day (`desk.date_today` = **2026-08-31**). It holds stock, prices, vendors, the shop lease, cash, bills, and a queue of incoming **tickets**. Our agents will work through that ticket queue. They read the other tables to decide what to do and write their results back (stock changes, payments, ticket status).

## Overview

| Table | Rows | Purpose |
|---|---|---|
| `desk` | 1 | The shop's "today" date plus a free-text notes field. |
| `inventory` | 10 | Stock on hand for each SKU and size, with the shelf location. |
| `pricing` | 4 | Unit cost and list price for each SKU. |
| `vendors` | 3 | Suppliers and couriers, with their lead times. |
| `leases` | 1 | The shop's rented space and when the next rent payment is due. |
| `cash_accounts` | 1 | Cash available to pay bills. |
| `payments` | 0 | Log of money paid out, including who approved each payment. Empty so far. |
| `invoices` | 1 | Bills from vendors. |
| `tickets` | 3 | The work queue: customer orders, bills and notices, and pricing requests. All 3 are `open`. |

Relationships (declared FK = written into the schema as a `FOREIGN KEY`; implicit = only matched by value):

- `tickets.lease_id` → `leases.id` (declared FK)
- `tickets.invoice_id` → `invoices.id` (declared FK)
- `invoices.vendor_id` → `vendors.id` (declared FK)
- `tickets.(sku, size)` → `inventory.(sku, size)` (implicit)
- `tickets.sku` / `inventory.sku` → `pricing.sku` (implicit)
- `payments.ref_id` → `invoices.id` or `leases.id`, depending on `payments.kind` (implicit, polymorphic)
- `payments.account` → `cash_accounts.name` (implicit)

`PRAGMA foreign_keys` is **off** by default in SQLite, so even the declared FKs are not enforced at write time. Our agents' tools must check references themselves before they write.

---

## `desk`

The shop's clock and scratchpad.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `date_today` | TEXT, NOT NULL | `2026-08-31` (ISO date) | The "now" for every date calculation: whether an invoice is overdue, how many days until rent is due, when a vendor reprint would arrive. Agents must use this value and not the real system clock. |
| `notes` | TEXT | Currently empty | A shared place for agents to leave a handoff or end-of-day summary. |

**Why it matters for agents:** it gives every agent the same idea of "today", so date-based decisions are consistent across agents and can be reproduced.

---

## `inventory`

Physical stock, one row per SKU and size. Primary key is `(sku, size)`.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `sku` | TEXT, NOT NULL, PK part | 4 SKUs: `CC-HOOD-NAVY`, `CC-TEE-WHITE`, `CC-HAT-BLUE`, `CC-MUG-CREST` | Joins to `pricing` and to the `sku` on a ticket. |
| `name` | TEXT, NOT NULL | Display name, e.g. "Classic Bulldog Tee" | Lets the agent refer to the item by name when replying to a customer. |
| `size` | TEXT, NOT NULL, PK part | Apparel: S/M/L/XL. Hat and mug: `OS` (one size) | Together with `sku`, identifies the exact item a ticket asks for. |
| `qty` | INTEGER, NOT NULL | 0–40. Out of stock: `CC-TEE-WHITE` S and `CC-MUG-CREST` OS | Decides whether an order can be filled now, filled in part, or has to wait for a restock. Agents decrement it when they fulfil an order and must never let it go below 0. |
| `location` | TEXT, NOT NULL | Aisle A–D | Pick location to include in fulfilment instructions. |

**Why it matters for agents:** it is the source of truth for "can we sell this right now?" for both the order ticket and the bulk-pricing ticket.

---

## `pricing`

Cost and price for each SKU (not per size).

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `sku` | TEXT, PRIMARY KEY | Same 4 SKUs as `inventory` | Join key. |
| `unit_cost` | REAL, NOT NULL | Hoodie $22, Tee $8, Hat $6, Mug $3.50 | Sets the floor for any discount. A pricing agent must not approve a price below cost, and should keep a margin above it. |
| `list_price` | REAL, NOT NULL | Hoodie $58, Tee $28, Hat $22, Mug $14 | The default sale price, and the starting point for working out a discount and the margin it leaves. |

**Why it matters for agents:** a discount decision (ticket 103) depends on both list price and cost. Prices are stored as floats, so round money to cents.

---

## `vendors`

Outside suppliers.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `id` | INTEGER, PRIMARY KEY | 1–3 | Referenced by `invoices.vendor_id`. |
| `name` | TEXT, NOT NULL | Bulldog Print Co, Elm City Gifts, QuickShip CT | Who to pay or contact. |
| `specialty` | TEXT, NOT NULL | apparel reprint / mugs and small goods / local courier | Lets an agent choose the right vendor to restock a SKU, e.g. apparel goes to Bulldog Print Co and mugs to Elm City Gifts. |
| `lead_days` | INTEGER, NOT NULL | 5 / 3 / 1 | Used to give customers a realistic restock or delivery date (`date_today` + `lead_days`). |

**Why it matters for agents:** without this table an agent cannot tell when out-of-stock items will be back, or which vendor sent a given invoice.

---

## `leases`

The shop's rented space.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `id` | INTEGER, PRIMARY KEY | 1 | Referenced by `tickets.lease_id` and, for rent payments, by `payments.ref_id`. |
| `space_name` | TEXT, NOT NULL | Chapel Street shop | Human-readable label. |
| `landlord` | TEXT, NOT NULL | Elm City Properties | The payee. Agents should check that it matches the ticket's `requester` before paying anything. |
| `monthly_rent` | REAL, NOT NULL | $2,400.00 | The amount to pay. Agents should take it from this table, not from the ticket text. |
| `next_due` | TEXT, NOT NULL | 2026-09-02 (2 days after `date_today`) | Sets how urgent the rent is. After a payment, an agent would move this date forward one month. |
| `notes` | TEXT | Empty | Space for payment remarks. |

**Why it matters for agents:** rent is the largest fixed bill. A finance agent must confirm the amount and payee here instead of trusting the incoming email.

---

## `cash_accounts`

Money available to spend.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `name` | TEXT, PRIMARY KEY | `checking` | Matched to `payments.account`. |
| `balance` | REAL, NOT NULL | $3,400.00 | The hard limit on spending. Paying both open bills (rent $2,400 + invoice $840 = $3,240) would leave only **$160**. Agents must check the balance before each payment and decrease it afterwards. |
| `date` | TEXT, NOT NULL | 2026-08-31 | Date the balance was last updated. Should be updated whenever the balance changes. |

**Why it matters for agents:** it stops agents from paying more than the shop has, and forces them to decide which bill to pay first.

---

## `payments`

Audit log of money paid out. Currently empty.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `id` | INTEGER, PRIMARY KEY | | Payment record ID. |
| `kind` | TEXT, NOT NULL | Expected values such as `rent` / `invoice` | Says which table `ref_id` points to. |
| `ref_id` | INTEGER | No FK; either `leases.id` or `invoices.id` | Links the payment to the bill it settles. Agents must set it correctly, because the schema will not check it. |
| `amount` | REAL, NOT NULL | | Amount paid. Should equal the bill amount and be subtracted from `cash_accounts.balance`. |
| `account` | TEXT, NOT NULL | e.g. `checking` | Which cash account the money came from. |
| `paid_at` | TEXT, NOT NULL | ISO timestamp | When the payment was made. |
| `approved_by` | TEXT, NOT NULL | Required | **Human-in-the-loop gate.** Every payment needs a named approver, so agents should propose payments and record who approved them, not move money on their own. |

**Why it matters for agents:** this is where agents record what they did with money. Before writing a payment, an agent should check here that the bill has not already been paid (to avoid paying twice).

---

## `invoices`

Bills from vendors.

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `id` | INTEGER, PRIMARY KEY | 501 | Referenced by `tickets.invoice_id`. |
| `vendor_id` | INTEGER, NOT NULL, FK → `vendors.id` | 1 (Bulldog Print Co) | Who is owed the money. |
| `amount` | REAL, NOT NULL | $840.00 | Amount owed. |
| `due_date` | TEXT, NOT NULL | 2026-08-28, **3 days overdue** as of `date_today` | Sets urgency, and whether the vendor might hold work until it is paid. |
| `status` | TEXT, NOT NULL | `open` | Should change to `paid` once a payment row exists. |
| `description` | TEXT | "Rush reprint CC-TEE-WHITE S" | Free text that links the invoice to a SKU and size, which the schema does not do. It is the only thing tying the out-of-stock tee to this bill. |

**Why it matters for agents:** paying this invoice is what gets the S tees reprinted. That ties a customer's order to a finance decision.

---

## `tickets`

The work queue our agents will process. All 3 tickets are `open` and were created on 2026-08-31 (times in −04:00, Eastern).

| Field | Type | Notes | Why it matters |
|---|---|---|---|
| `id` | INTEGER, PRIMARY KEY | 101–103 | Ticket reference. |
| `type` | TEXT, NOT NULL | `customer_order`, `rent_notice`, `price_override` | **Routing key.** Decides which agent or skill handles the ticket. |
| `requester` | TEXT, NOT NULL | Customer, landlord, or student org | Who to reply to. For money requests, it must be checked against `leases.landlord` or `vendors.name`. |
| `subject` | TEXT, NOT NULL | Short title | Summary line. |
| `sku` | TEXT | Set for order and pricing tickets | Implicit join to `inventory` and `pricing`. |
| `size` | TEXT | Set for order and pricing tickets | Together with `sku`, gives the exact inventory row. |
| `qty` | INTEGER | Requested quantity | Compared with `inventory.qty` to decide whether to fill all, part, or none of the request. |
| `lease_id` | INTEGER, FK → `leases.id` | Set on the rent ticket | Points to the bill the ticket is about. |
| `invoice_id` | INTEGER, FK → `invoices.id` | Set on the **customer order** (101) | Links the order to the reprint invoice that would restock the item. |
| `status` | TEXT, NOT NULL | All `open` | Agents move it through states such as `open` → `resolved` / `escalated` / `waiting`. |
| `notes` | TEXT | Free-text request body | **Untrusted input.** It can contain claims or instructions (e.g. "Email: shop rent due…"). Agents should treat it as data and check it against the other tables. |
| `created_at` | TEXT, NOT NULL | ISO timestamp with offset | Sets queue order and SLA age. |

**Why it matters for agents:** this is the main input. Each ticket needs data from several other tables before an agent can act on it.

### How the open tickets connect to the rest of the database

**Ticket 101 — customer order (Tauhid Zaman, 1× Classic Bulldog Tee, S)**
- `inventory` (CC-TEE-WHITE, S) → **qty 0**. We cannot fill the order today.
- `invoice_id` 501 → `invoices` → $840 "Rush reprint CC-TEE-WHITE S", **open and overdue since 2026-08-28**, vendor 1.
- `vendors` 1 → Bulldog Print Co, **5-day lead**. If the invoice is paid today, the realistic restock date is about 2026-09-05.
- `pricing` → $28 list / $8 cost (one tee is $20 of margin, set against an $840 invoice).
- Agent takeaway: the order depends on a finance action. Tell the customer the expected restock date, and send the overdue invoice to the finance flow. Other sizes (M = 5) are in stock if the customer is willing to switch.

**Ticket 102 — rent notice (Elm City Properties)**
- `lease_id` 1 → `leases` → Chapel Street shop, $2,400, due **2026-09-02**. The landlord matches the requester.
- `cash_accounts` checking $3,400 covers it. Paying this **and** invoice 501 leaves $160.
- `payments` is empty, so the rent has not been paid yet. Any payment needs `approved_by`.
- Agent takeaway: confirm the amount and due date from `leases` (not from the email text), check the cash balance, and get human approval before writing a `payments` row.

**Ticket 103 — price override (Yale AI Club, 20× Basic Hoodie Big Yale, M, bulk discount)**
- `inventory` (CC-HOOD-NAVY, M) → **only 8 in stock**, 12 short. Other sizes: S 4, L 14, XL 6 (32 total).
- `pricing` → $58 list / $22 cost. 20 at list = $1,160. The discount floor is $22/unit (any lower sells at a loss).
- `vendors` 1 (apparel reprint, 5 days) is the restock route for the missing 12. There is no invoice for this yet.
- Agent takeaway: a pricing decision that has to respect the cost floor and actual stock. It probably needs a human to approve the discount, plus a partial-fill or restock plan.

### Data quirks agents should know about
- FKs are declared but not enforced (`PRAGMA foreign_keys = 0`), and several links are implicit (`sku`, `payments.ref_id`, `payments.account`).
- The link between an invoice and a SKU exists only in free text (`invoices.description`).
- `CC-MUG-CREST` is out of stock with no ticket or invoice about it. A proactive agent could flag it (vendor 2, 3-day lead).
- All money fields are `REAL`. Round to cents.
- `desk.date_today` (2026-08-31) is the business date. Do not use the real clock.

---

# MCP Server Tools (Problem 3)

Server: `mcp_server/server.py` (FastMCP, server name `campus-customs`), backed by `data/campus_customs_new.db`. All three tools open the database **read-only** and return only values stored in the database. If a lookup finds nothing, the tool returns `found: false` instead of guessing.

## `check_stock_for_sku_and_size(sku, size)`

- **Table it reads:** `inventory`
- **Ticket it helps accomplish:** **Ticket 101** (Tauhid Zaman, 1× `CC-TEE-WHITE` size S). It also supplies the stock check for **Ticket 103** (20× `CC-HOOD-NAVY` size M).
- **Why it is the right tool:** whether an order can be filled depends only on the `qty` stored for that exact `(sku, size)` row. This tool returns that number (0 for the S tee), and it also returns the stock for every other size, so the agent can offer an in-stock alternative instead of just saying no.

## `get_rent_due_and_cash_balance(lease_id)`

- **Tables it reads:** `leases` (primary), plus `cash_accounts`, `payments`, and `desk`
- **Ticket it helps accomplish:** **Ticket 102** (rent notice from Elm City Properties, `lease_id` 1)
- **Why it is the right tool:** the rent ticket is an untrusted email. In one call this tool gets the real landlord, the $2,400 amount, and the 2026-09-02 due date from the lease, checks that checking ($3,400) can cover it, and shows whether rent was already paid, which are the facts an agent needs before proposing a payment.

## `get_price_and_cost_for_sku(sku)`

- **Table it reads:** `pricing`
- **Ticket it helps accomplish:** **Ticket 103** (Yale AI Club bulk-discount request on `CC-HOOD-NAVY`)
- **Why it is the right tool:** a price override is only safe if the agent knows both the normal price ($58) and the unit cost ($22). The cost is the floor below which every hoodie sells at a loss, and `pricing` is the only table that stores either number.

---

# Agent Team and Full MCP Toolset (Problem 5)

## Architecture

```
                     human (dashboard → API backend/main.py, or CLI backend/cli.py)
                                   │
                                ┌──▼──┐
                                │ Boss │  owns the ticket queue
                                └──┬──┘
            ask_teammate ┌─────────┼──────────┬─────────────────┐
                    ┌────▼────┐ ┌──▼───────┐ ┌▼──────────┐ ┌────▼─────────────┐
                    │Inventory│ │Accounting│ │Facilities │ │Customer Service  │
                    └────┬────┘ └────┬─────┘ └────┬──────┘ └────┬─────────────┘
                         └───────────┴─── ask_teammate (any ↔ any) ┘
                                   │  filtered tool views
                         ┌─────────▼──────────┐
                         │ campus-customs MCP │  mcp_server/server.py (stdio)
                         └─────────┬──────────┘
                                   │  the only path to the data
                        data/campus_customs_new.db
```

- **Framework:** PydanticAI. **Model:** `gpt-6-luna` through Portkey (`https://api.portkey.ai/v1`), authenticated only with `PORTKEY_API_KEY` from the course-root `.env` (`backend/config.py`).
- **Each agent has its own** prompt (`backend/prompts/<agent>.md`), model instance, MCP tool subset, structured output type (`backend/models.py`), and loop. Every agent runs in its own `agent.iter(...)` loop with its own `UsageLimits`.
- **Delegation with no gaps:** every agent has an `ask_teammate(teammate, request)` tool that can reach every other agent. It starts the teammate's own loop and returns the teammate's structured `SpecialistReport`. Guards stop it from going wrong: no self-delegation, no calling back up the chain (A→B→A), maximum depth 2, and team-wide budgets for delegations and tokens.
- **No back door to the DB:** agents have no SQLite code. Their only data tools come from one shared `MCPToolset` connection to the `campus-customs` server (`backend/mcp_connection.py`), filtered per agent.
- **Audit:** every team run appends to `output/audit_trail.json` (see "Audit trail" below).

| File | Purpose |
|---|---|
| `backend/cli.py` | CLI entry point (`--ticket`, `--agent`, `--prompt`, `--approver`). *(Was `backend/main.py` in Problem 5; moved in Problem 7 when `main.py` became the FastAPI app.)* |
| `backend/shop_agents/base.py` | `Team`: builds the agents, runs each agent loop, handles `ask_teammate`, records each loop step. |
| `backend/shop_agents/{boss,inventory,accounting,facilities,customer_service}.py` | One file per agent: role, allowed MCP tools, output type, limits. |
| `backend/prompts/*.md` | One detailed prompt per agent: role, scope, tools, shop rules, output format. |
| `backend/models.py` | Data types: `TeamRun`, `AgentDeps`, `SpecialistReport`, `TicketOutcome`, `ShiftReport`, `AuditEvent`. |
| `backend/mcp_connection.py` | Shared MCP connection, per-agent tool filter, audit and approval hook on every MCP call. |
| `backend/audit.py` | Append-only writer for `output/audit_trail.json`. |
| `backend/config.py` | Model, Portkey key, and all cost limits. |

## The agents

### Boss (shop manager): `backend/shop_agents/boss.py`, `prompts/boss.md`
Entry point for every run. Reads the business date and the open-ticket queue, routes each ticket to the right specialist (customer orders → Customer Service, rent and landlord → Facilities then Accounting, price overrides → Accounting + Inventory + Customer Service), checks their reports, and is the **only agent that changes ticket status**. It finishes by writing a desk handoff note. Output: `ShiftReport` (one `TicketOutcome` per ticket plus the desk note).
**MCP tools:** `get_business_date`, `list_open_tickets`, `get_ticket_details`, `update_ticket_status`, `add_desk_note` (+ `ask_teammate`).

### Inventory (stock manager): `inventory.py`, `prompts/inventory.md`
Says what is on the shelf for an exact SKU and size, offers other in-stock sizes, plans restocks (vendor by specialty, date = business date + `lead_days`), checks whether a linked reprint invoice is paid, and pulls stock **only for confirmed orders** with enough units. Output: `SpecialistReport`.
**MCP tools:** `get_business_date`, `get_ticket_details`, `check_stock_for_sku_and_size`, `list_vendors`, `get_invoice_details`, `decrement_inventory_for_order`.

### Accounting (bookkeeper): `accounting.py`, `prompts/accounting.md`
Owns cash, invoices, rent payment, and pricing. Pays only the exact amount in the database, never twice, never more than the balance, and only with a human approver. If cash is tight, rent comes first. Applies the discount policy: unit cost is a hard floor, and up to 15% off list for 10+ units of one SKU; anything deeper is escalated. Output: `SpecialistReport`.
**MCP tools:** `get_business_date`, `get_ticket_details`, `get_cash_account_balances`, `get_invoice_details`, `get_rent_due_and_cash_balance`, `get_price_and_cost_for_sku`, `list_vendors`, `record_payment`.

### Facilities (premises and lease): `facilities.py`, `prompts/facilities.md`
The check against bad notices. Verifies a rent or landlord notice against the lease (requester = landlord, amount and due date from the lease, not already paid), flags discrepancies as possible fraud, then hands **verified** figures to Accounting. Also handles local courier logistics and escalates premises issues. Cannot pay anything. Output: `SpecialistReport`.
**MCP tools:** `get_business_date`, `get_ticket_details`, `get_rent_due_and_cash_balance`, `list_vendors`.

### Customer Service (voice of the shop): `customer_service.py`, `prompts/customer_service.md`
Works out what the requester wants, checks stock, asks Inventory for restock timing and Accounting for any non-list price, and drafts the customer reply (`customer_message`). It promises only what the facts support and never reveals costs, margins, invoices, or other customers' data. Output: `SpecialistReport` with `customer_message`.
**MCP tools:** `get_business_date`, `get_ticket_details`, `check_stock_for_sku_and_size`.

## All MCP tools (14, including `list_all_tickets` added in Problem 7)

R = read-only connection. W = write in one transaction, with the server re-checking the shop's hard rules.

| Tool | R/W | Tables | Used by | What it does |
|---|---|---|---|---|
| `get_business_date` | R | `desk` | all | Business "today" and desk notes. |
| `list_open_tickets` | R | `tickets` | Boss | All non-resolved tickets, oldest first. |
| `list_all_tickets` *(P7)* | R | `tickets` | desk API | Every ticket including resolved (for the dashboard). |
| `get_ticket_details` | R | `tickets` | all | One ticket with SKU/size/qty, `lease_id`, `invoice_id`. |
| `check_stock_for_sku_and_size` *(P3)* | R | `inventory` | Inventory, Customer Service | Qty, location, and all sizes of a SKU. |
| `list_vendors` | R | `vendors` | Inventory, Accounting, Facilities | Vendors, specialties, lead days. |
| `get_rent_due_and_cash_balance` *(P3)* | R | `leases`, `cash_accounts`, `payments`, `desk` | Accounting, Facilities | Lease rent and due date, cash, prior rent payments. |
| `get_invoice_details` | R | `invoices`, `vendors`, `payments`, `desk` | Inventory, Accounting | Invoice, vendor, days overdue, prior payments. |
| `get_cash_account_balances` | R | `cash_accounts` | Accounting | All account balances. |
| `get_price_and_cost_for_sku` *(P3)* | R | `pricing` | Accounting | List price and unit cost. |
| `decrement_inventory_for_order` | W | `inventory`, `tickets` (note) | Inventory | Pulls stock for a ticket. Refuses if qty ≤ 0, SKU/size don't match the ticket, qty exceeds the request, or stock is short. |
| `record_payment` | W | `payments`, `cash_accounts`, `invoices` or `leases` | Accounting | Pays rent or an invoice. Refuses if no human approver (or the approver is an agent name), the amount is not exactly the bill, the bill is already paid or rent is not yet due (more than 14 days out), or funds are insufficient. Marks the invoice `paid` or moves the lease `next_due` forward one month. |
| `update_ticket_status` | W | `tickets` | Boss | Sets the status (6 allowed values) and appends a dated, author-stamped note. Resolved tickets are locked. |
| `add_desk_note` | W | `desk` | Boss | Appends a dated, author-stamped handoff note. |

**Fields the system fills in, not the model:** `author` (on `update_ticket_status` and `add_desk_note`) and `approved_by` (on `record_payment`) are removed from the tool schema the model sees. The backend fills them in from the run state: the calling agent's name, and the human approver who confirmed that payment at the terminal.

## Audit trail (`output/audit_trail.json`)

A JSON array that is only ever **appended to**. Each event is read, appended, and atomically replaced, so nothing is erased between runs, and a crash keeps every step up to that point. If the file is not valid JSON, the run stops rather than overwrite it. Every event has `timestamp`, `run_id`, `event`, `agent`, `agent_run_id`, `chain` (the delegation path, e.g. `boss → facilities → accounting`), and `step`, plus:

| Event | Records |
|---|---|
| `team_run_start` / `team_run_end` | Prompt, entry agent, approver, model / totals: agent runs, delegations, tokens. |
| `agent_run_start` | Request, who asked, model, prompt file, allowed tools, usage limits. |
| `agent_step` | **One per loop step:** `model_request` (prompt, tool results, retries sent to the model), `model_response` (text and tool calls with arguments, model name, finish reason, token usage), `end` (final output). |
| `mcp_tool_call` / `mcp_tool_result` | Exact MCP tool, arguments (after system fields are filled in), and result or error. |
| `delegation` | From → to, request, accepted or refused and why. |
| `human_approval` | Payment details, approver, approved yes or no. |
| `agent_run_end` | Status ok or error, structured output, token usage, seconds. |

## Safety for a real business

Real customer data and real money need more than this classroom build. A production version should have:

- **Least privilege by design.** Each agent sees only the tools its role needs (already done). In production, back this with separate database roles or credentials per tool, so a read tool physically cannot write. Keep secrets in a secrets manager, not `.env`.
- **Hard rules enforced in code, not prompts.** The server, not the model, enforces exact bill amounts, no double payment, no overdraft, no negative stock, and valid statuses (already done). Add per-transaction and daily spending caps, an allow-list of payees tied to vendor and lease records, and a "four eyes" rule (two people) for payments above a threshold.
- **Human in the loop for money and exceptions.** Every payment needs a named human approval per transaction (already done). In production, use authenticated approval (SSO or MFA) in a real UI instead of typed names, and route discounts beyond policy, refunds, and lease changes to people.
- **Prompt-injection and fraud defense.** Treat all ticket and email text as untrusted data. Verify payees against the database. Never act on bank-detail changes or "urgent" instructions from email. Flag and quarantine suspicious tickets (lookalike landlord names, changed account numbers).
- **Customer privacy (PII).** Collect and keep only what a ticket needs. Redact or mask customer names, emails, and addresses in logs and in prompts sent to the model provider. Make sure the provider (via Portkey) has a no-training / zero-retention agreement. Set retention limits and support deletion requests, and never pass card data or passwords through agents (use a PCI-compliant payment processor).
- **Tamper-evident, access-controlled audit.** Store the audit log append-only (e.g. WORM storage or hash-chained entries), restrict who can read it (it contains PII), and alert on refused writes, failed approvals, and unusual activity.
- **Safe rollout.** Run in shadow or dry-run mode first, test against a staging copy of the data, take backups before write runs, keep a kill switch to disable write tools, and add rate limits, timeouts, and monitoring on error rates and spend.

## Keeping token usage (and cost) in check

What is already in place (`backend/config.py`):

- **Per-agent loop caps (`UsageLimits`):** Boss at most 20 model requests, 30 tool calls, 150k tokens. Each specialist at most 8 requests, 12 tool calls, 50k tokens. A runaway loop fails fast and is recorded in the audit trail.
- **Per-response output caps:** `max_tokens` is 4,000 for the Boss and 2,000 for specialists. (`temperature=0` was dropped in Problem 7 because gpt-6-luna is a reasoning model and ignores it. In Problem 9 one specialist hit the 2,000 cap during reasoning; see the lessons below.)
- **Team-wide budgets:** at most 15 delegations and 400k tokens per run. Delegation depth is capped at 2, and loops back up the chain are refused, so agents cannot bounce work between each other.
- **Small context per agent:** each agent sees only its own prompt and its own small tool list. Tools return compact JSON (single rows, not table dumps). Audit logging clips very long strings.
- **Prompts that discourage waste:** delegate each piece of work once, pass known facts along so teammates don't repeat lookups, keep reports short and put the detail in `facts`.

Further steps for production:

- Track spend per run in the audit trail and set a daily budget alert.
- Use a cheaper or smaller model for simple lookups (e.g. Inventory) and reserve the larger model for the Boss and Accounting.
- Turn on provider prompt caching for the long, unchanging system prompts.
- Process only new or changed tickets.
- Summarize long ticket histories instead of passing them whole.

---

# Backend API Routes (Problem 7)

**Server:** FastAPI app in `backend/main.py`. Start it from `backend/`:

```bash
uvicorn main:app --reload --port 8000
```

It runs at `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`, and CORS is open to `localhost` origins for the frontend.

**Data path:** the routes read and write shop data through the same `campus-customs` MCP server tools the agents use (an in-process MCP client), never with raw SQL. The one exception is the reset route, which swaps the whole database file. Agent activity comes from `output/audit_trail.json`, which the agent team appends to whether it is run from the CLI or anywhere else.

| Method | URL | What it does |
|---|---|---|
| GET | `/api/tickets` | All tickets (all three) with full details, the raw `status`, and a simplified `state` (`open` or `resolved`) plus `is_resolved`. Also returns open and resolved counts. MCP: `list_all_tickets`. |
| GET | `/api/tickets/{ticket_id}/agents` | The agents on one ticket, from the audit trail. An agent counts if its run was started about the ticket, it called a tool with that `ticket_id`, or its final report lists the ticket. Each agent comes back with its title, agent-run ids, the MCP tools it used for this ticket, first and last activity time, and `active` (still running). Defaults to the latest run that touched the ticket; `?run_id=<id>` or `?run_id=all` selects others. 404 if the ticket doesn't exist. |
| GET | `/api/events` | Recent agent activity for a live frontend feed: run start and finish, agent started or finished (with its summary), what agents said (`agent_said`), MCP tool calls and results, delegations, approvals, customer replies, and DB resets. Each item has an `id`. Poll with `?after=<latest_id>` to get only new items. Filters: `?run_id=<id or latest>`, `?agent=<name>`, `?limit=`. Also returns `active_runs`. |
| GET | `/api/approvals` | Payments the agents asked for that are waiting on a human (`?status=pending`, the default), or `approved`, `rejected`, `failed`, `all`. |
| POST | `/api/approvals/{approval_id}/approve` | **A human confirms a payment.** Body: `{"approver": "Full Name", "confirm": true}`. Without `confirm: true` and a name, nothing happens (400). The payment is then made through the MCP `record_payment` tool with the human's name as `approved_by`, so every server-side check still applies (exact amount, no double pay, enough funds). Returns the payment and new balance. 409 if it was already decided or the server refused it. Written to the audit trail. |
| POST | `/api/approvals/{approval_id}/reject` | A human declines a queued payment. Same body plus an optional `reason`. Nothing is paid; written to the audit trail. |
| GET | `/api/cash/checking` | Current balance of the `checking` account from `cash_accounts`: `{account, balance, as_of}`. MCP: `get_cash_account_balances`. |
| POST | `/api/reset` | Restores `data/campus_customs_new.db` from the original `data/campus_customs.db` for a fresh run. Body: `{"confirm": true}` (and `"force": true` if the audit trail shows a run still in progress). The file is copied to a temp file and swapped in atomically. Pending approvals are cleared because they refer to the old data, and a `db_reset` event is **appended** to the audit trail (the trail itself is never wiped). Returns the restored ticket statuses and checking balance. |

### How payment approval works now

1. An agent (Accounting) calls `record_payment`. Unless a human is approving live at the terminal (`backend/cli.py --approver "Name"`), the backend **does not pay**. It queues the payment in `output/pending_approvals.json` and tells the agent "queued, approval id N, not paid", and the agent reports `needs_human`.
2. A person reviews it with `GET /api/approvals` and confirms with `POST /api/approvals/{id}/approve`.
3. The payment goes through the MCP server with that person's name as `approved_by`.

### Changes made in this problem

- `backend/main.py` is now the FastAPI app. The agent-team command line moved to **`backend/cli.py`** (same flags).
- New MCP read tool **`list_all_tickets`** (`tickets` table) for the dashboard, since `list_open_tickets` hides resolved tickets. The server now has 14 tools.
- New `backend/approvals.py` (the payment approval queue) and a new audit event type `db_reset`.
- **Model transport fix:** gpt-6-luna rejects function tools on `/v1/chat/completions` while reasoning is on, so every agent now uses the OpenAI **Responses API** (`/v1/responses`) through Portkey (`OpenAIResponsesModel`). It is still `gpt-6-luna` with `PORTKEY_API_KEY`. `temperature` was dropped because reasoning models ignore it.

---

# Dashboard and Run Routes (Problem 8)

**Dashboard:** `frontend/` (React + Vite + TypeScript). Start it with `npm run dev` in `frontend/`; it serves `http://localhost:5173` and calls the API at `http://localhost:8000` (`src/api.ts`, override with `VITE_API_BASE`). The backend's CORS explicitly allows `http://localhost:5173` and `http://127.0.0.1:5173`. Design decisions are in `output/design.md`.

New routes added for the dashboard:

| Method | URL | What it does |
|---|---|---|
| POST | `/api/tickets/{ticket_id}/run` | Starts the agent team (Boss first) on one ticket as a background task and returns `{run_id, ticket_id, running}`. Only one run at a time (409 if busy); resolved tickets are refused (409). Payments in these runs **wait for dashboard approval** (see below). |
| GET | `/api/runs/current` | The run this server started most recently: running or finished, ok or error. |

Changes to existing routes:
- `GET /api/tickets` now also returns `business_date` and `active_run`.
- `GET /api/approvals` now adds `details` for each payment (payee, what it's for, due date, days overdue), looked up through MCP so the human can check it.
- `GET /api/events` now also returns `agent_thought` items (model reasoning summaries, when present).
- `POST /api/reset` is refused while a run is in progress.

**Dashboard approval flow (`approval_mode = "dashboard"`):** when Accounting calls `record_payment`, the backend queues it and the agent's tool call **pauses** (up to 15 minutes). When a person approves on the dashboard (`POST /api/approvals/{id}/approve`), the paused call continues to the MCP server with that person's name as `approved_by`, the agent sees the real payment result, and the team finishes the ticket. If the person declines, the agent gets a refusal and the ticket is escalated. The CLI still supports `terminal` mode (type `yes`) and `queue` mode (approve later).

**Boss status rule change:** a ticket is now `resolved` when the team has done everything within its control: every needed payment is approved and recorded, and the requester has a complete answer, which is saved in the resolving note as `Reply sent: "..."`. A reply that offers the requester a choice still resolves the ticket; their answer would arrive as a new ticket. `escalated` is used when a human decision is still outstanding. Single-ticket runs only touch that ticket.


---

# Safety Rules Enforced in This Build (Problem 9 summary)

Rules enforced **in code**, so a confused or manipulated model cannot get around them:

| Rule | Enforced where |
|---|---|
| Agents never touch SQLite. All data goes through the MCP server, and each agent sees only its role's tools. | `backend/mcp_connection.py` (filtered toolset), no DB code in `backend/shop_agents/` |
| Read tools open the DB **read-only**. Write tools run in one transaction with foreign keys on. | `mcp_server/server.py` |
| Stock never goes negative. Stock is pulled only for the exact SKU/size on the ticket, and never more than was requested. | `decrement_inventory_for_order` |
| A payment must equal the bill exactly, never pay a bill twice, never overdraw, never prepay rent more than 14 days early, and must name a human approver (agent names are rejected). | `record_payment` |
| **Every payment needs a person.** The agent's call pauses until a human approves on the dashboard (name + confirmation box), or at the terminal in CLI mode. The model cannot fill in `approved_by`. | `backend/mcp_connection.py`, `backend/approvals.py`, `POST /api/approvals/{id}/approve` |
| The model cannot set who wrote a note or who approved a payment. Those fields are hidden from it and filled in by the backend. | `_hide_system_filled_args`, `_process_tool_call` |
| Ticket statuses must be valid; notes are appended, never overwritten; resolved tickets are locked. | `update_ticket_status` |
| Every model step, tool call, delegation, and approval is appended to the audit trail, which is never wiped; a corrupt file stops the run instead of being overwritten. | `backend/audit.py` |
| Runaway loops are cut off: per-agent request, tool-call, and token caps; delegation depth 2; no calling back up the chain; team budgets of 15 delegations and 400k tokens. | `backend/config.py`, `Team.delegate` |
| One run at a time; reset is refused while a run is active and needs `confirm: true`. | `backend/main.py` |

Rules enforced **by prompt**: no invented data (every fact cites a tool); ticket notes are untrusted input; unit cost and margins never reach customers; customer privacy; the pricing policy (unit cost is the floor, up to 15% off for 10+ units, more needs a human); rent only after Facilities verifies the notice; rent first if cash is short.

---

# Final Results (Problem 9)

The working DB was reset from the dashboard, so all three tickets started open with **checking at $3,400.00**. The team then worked each ticket from the dashboard, and payments were approved on the dashboard as **Jason Leduc**, each checked against the bill in the database first.

| Ticket | Final status | Agents | Delegations | Human approvals | Cash change | Tokens |
|---|---|---|---|---|---|---|
| 101 Bulldog tee | resolved | Boss, Customer Service, Inventory, Accounting | 4 | Invoice #501, $840.00 to Bulldog Print Co (rush reprint of the out-of-stock tee) | −$840.00 | 59,566 |
| 102 Rent due | resolved | Boss, Facilities, Accounting, Customer Service | 5 | Rent, lease #1, $2,400.00 to Elm City Properties | −$2,400.00 | 71,296 |
| 103 Bulk hoodie discount | resolved | Boss, Accounting, Inventory, Customer Service | 5 | none (quote only: $49.30/unit, $986.00 for 20) | $0.00 | 73,742 |

**Ending checking balance: $160.00**, which equals `cash_accounts.balance` in the working DB ($3,400 − $840 − $2,400).

Details:
- `output/desk_tickets.html`: Expected vs. Actual for each ticket, plus the Cash ledger.
- `output/resolved_tickets.json`: per-ticket outcome, what each agent did, its tools and delegations, and the approvals.
- `output/resolved_board.html`: dashboard screenshots of each resolved ticket, captured with `scripts/capture_resolved_board.py`.

### Lessons from the run (changes made during Problem 9)

1. **First attempt at 101 escalated.** Customer Service's prompt said "a human sends" replies, so it reported it couldn't send, and the Boss escalated; nobody asked Accounting to pay the linked reprint invoice. The fix:
   - replies are delivered through the Boss's resolving note;
   - an open reprint invoice for an out-of-stock ordered item goes to Accounting for payment (with human approval) before the final reply.

   The DB was reset again and all three tickets were rerun from scratch. Both resets and the failed attempt are still in `audit_trail.json`.
2. **Output-token cap and reasoning.** In ticket 102, Customer Service's first run used its whole 2,000-token output budget on reasoning and returned nothing. The Boss handled the error and retried, so the system recovered, but the specialist cap is tight for a reasoning model. Raising `SPECIALIST_SETTINGS.max_tokens`, or lowering reasoning effort for simple drafting, would avoid the retry.
3. **Efficiency.** Each ticket used four of the five agents (Facilities only on 102). Most extra cost came from repeated checks: specialists re-read the ticket and stock they had been given, and asked a teammate to confirm a fact already in their request. Tightening "trust the facts in your request" in the specialist prompts is the next cost lever.
