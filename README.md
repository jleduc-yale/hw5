# Campus Customs Agent Desk (HW 5)

A team of AI agents (Boss, Inventory, Accounting, Facilities, Customer Service) that works the back-office tickets of **Campus Customs**, a small Yale merchandise shop. The agents read and write the shop database only through an **MCP server**. A **FastAPI backend** starts agent runs and handles human payment approvals, and a **React dashboard** lets you watch the agents work and approve payments.

```
React dashboard (frontend/, :5173) ──HTTP──▶ FastAPI backend (backend/main.py, :8000)
                                                   │ starts runs, approvals, cash, reset, event feed
                                                   ▼
                              Agent team (backend/shop_agents/, PydanticAI, gpt-6-luna via Portkey)
                                                   │ MCP tools only, no direct SQL
                                                   ▼
                              campus-customs MCP server (mcp_server/server.py, FastMCP)
                                                   │
                                                   ▼
            data/campus_customs_new.db  (working copy)   ◀── reset from ── data/campus_customs.db (original)
```

## Prerequisites

- **Python 3.13** and **Node.js 20+** (built with Node 24).
- A **Portkey API key** with access to `gpt-6-luna`. Put it in a `.env` file as:

  ```
  PORTKEY_API_KEY=your-key-here
  ```

  The backend looks for `.env` in `backend/`, then the project root, then the project's parent folder. Never commit this file.

## One-time setup

From the project root:

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
cd frontend && npm install
```

`playwright` is only needed for `scripts/capture_resolved_board.py`, which takes the dashboard screenshots. If you want to use it, install its browser:

```bash
.venv/bin/playwright install chromium
```

## Resetting the database (do this before every full run)

The original data lives in `data/campus_customs.db` and **is never modified**. The agents work on the copy, `data/campus_customs_new.db`. Every run changes that copy: tickets get resolved, payments are recorded, and the checking balance drops. Before a new run, **copy the original over the existing copy**:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

Also clear any queued payment approvals, since they refer to the old data:

```bash
echo '[]' > output/pending_approvals.json
```

Equivalent shortcut: with the backend running, the dashboard's **Reset data** button (or `POST /api/reset` with `{"confirm": true}`) does both steps. It copies atomically and adds a `db_reset` entry to the audit trail.

> **Reset before a full three-ticket run.** After a reset, all three tickets (101, 102, 103) are `open` and checking is **$3,400.00**. If you skip the reset, resolved tickets can't be run again (the API returns 409), and paid bills are refused by the payment safeguards (no double payments).

`output/audit_trail.json` is **not** reset. It is an append-only log of every run.

## Starting the pieces

Each long-running server below gets its own terminal.

### 1. MCP server (`mcp_server/server.py`)

The MCP server talks over **stdio**, so a client starts it as a child process. In normal use you don't start it yourself:

- the **FastAPI backend** starts it (in-process) for the dashboard routes, and the agent team starts it (as a stdio subprocess) for every run;
- **Claude Code** starts it from `.mcp.json` (the `campus-customs` server), so you can call its tools directly.

To start it by hand (for example to check it boots, or to connect your own MCP client):

```bash
.venv/bin/python mcp_server/server.py
```

It then waits for an MCP client on stdin and stdout; press `Ctrl+C` to stop it. It serves `data/campus_customs_new.db`. The 14 tools are listed in `mcp_server/README.md`.

> `.mcp.json` uses paths relative to the repo root (`.venv/bin/python mcp_server/server.py`), so it works in any clone once the one-time setup has created `.venv`. Open Claude Code **from the project root** and approve the `campus-customs` server when asked. On Windows, change `command` to `.venv\\Scripts\\python.exe`.

### 2. FastAPI backend (`backend/main.py`, port 8000)

```bash
cd backend
```

```bash
../.venv/bin/uvicorn main:app --reload --port 8000
```

If the venv is activated (`source .venv/bin/activate`), plain `uvicorn main:app --reload --port 8000` works too. Check that it's up at http://localhost:8000/docs (interactive route docs) or http://localhost:8000/api/tickets. CORS allows the dashboard at `http://localhost:5173`.

### 3. React dashboard (`frontend/`, port 5173)

```bash
cd frontend
```

```bash
npm run dev
```

Open **http://localhost:5173**. The dashboard calls the backend at `http://localhost:8000` (set `VITE_API_BASE` to change this). Port 5173 must be free, because the backend's CORS setting expects it.

## Running all three tickets

1. **Reset the database** (see above). Confirm the header shows **Checking $3,400.00** and the queue shows **3 open · 0 resolved**.
2. With the backend and dashboard running, select **#101 Bulldog tee** and click **Start agent team**. Watch the agent tiles and the *Live activity* feed.
3. When Accounting needs to pay something, the run **pauses** and an approval card appears. Check the payee and the amount, type your name, tick the confirmation box, and click **Approve** (or **Decline**). Nothing is paid until a human approves; the agent waits up to 15 minutes.
4. When the run finishes, the ticket turns green (**Resolved**) and the *Summary* tab shows what each agent did. Repeat for **#102 Rent due** and **#103 Bulk hoodie discount**. Runs go one at a time.

Expected money movement in a full run (the agents decide, so details can vary between runs):

| Ticket | Payment approved | Checking after |
|---|---|---|
| Start (after reset) | — | $3,400.00 |
| #101 | Invoice #501, $840.00 to Bulldog Print Co (rush reprint of the out-of-stock tee) | $2,560.00 |
| #102 | Rent, $2,400.00 to Elm City Properties (lease #1) | $160.00 |
| #103 | none (price quote only) | $160.00 |

**Without the dashboard**, the agent team can be run from the command line (with `--approver`, each payment asks for `yes` in the terminal; without it, payments are queued for later approval):

```bash
.venv/bin/python backend/cli.py --ticket 101 --approver "Your Name"
```

Each run uses roughly 60–75k tokens.

## Where to look afterward

| File | What it contains |
|---|---|
| `output/audit_trail.json` | Append-only log of every run: each model step, MCP tool call and result, delegation, approval, and reset |
| `output/desk_tickets.html` | Expected vs. actual for each ticket, the cash ledger, and the reflection |
| `output/resolved_tickets.json` | Final status, outcome, and per-agent actions and approvals for each ticket |
| `output/resolved_board.html` | Dashboard screenshots of the resolved tickets (`scripts/capture_resolved_board.py`) |
| `output/harness.md` | Full project reference: tables, MCP tools, agents, routes, dashboard, safety rules |
| `output/design.md` | Dashboard design decisions |
| `AI_prompts.md` | Log of every prompt used to build the project |

## Project layout

```
backend/
  main.py              FastAPI app (routes)
  cli.py               command-line runner for the agent team
  shop_agents/         one file per agent + base.py (agent loops, delegation, audit steps)
  prompts/             one prompt per agent (role, scope, shop rules)
  models.py            data types (run state, reports, audit events)
  mcp_connection.py    the agents' only path to data: filtered MCP tools + approval hook
  approvals.py         payment approval queue / dashboard hand-off
  audit.py             append-only audit trail writer
  config.py            model (gpt-6-luna via Portkey), token and loop limits
mcp_server/            FastMCP server (server.py) + README
frontend/              React + Vite + TypeScript dashboard
data/                  campus_customs.db (original), campus_customs_new.db (working copy)
output/                results, audit trail, docs
scripts/               screenshot capture
```

## Troubleshooting

- **Port 8000 or 5173 already in use.** Another dev server is running. Stop it (`lsof -iTCP:8000 -sTCP:LISTEN` shows which process).
- **Dashboard says it can't reach the desk API.** Start the backend from the `backend/` folder (the command in step 2).
- **"Ticket is already resolved" / payment refused as already paid.** Reset the database before running again.
- **`PORTKEY_API_KEY is not set`.** Add the `.env` file described in Prerequisites.
