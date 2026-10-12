# Campus Customs Desk: Dashboard Design

The dashboard (`frontend/`, React + Vite + TypeScript, `npm run dev` → `http://localhost:5173`) is where a person watches the agent team work, steps in when money moves, and sees the result. Every design decision below serves one of three goals:

1. **Trust.** A person must be able to see what the agents did and why, and nothing that costs money happens without them.
2. **Calm.** This is a back-office tool used for long stretches, so it should feel quiet and orderly, never alarming without reason.
3. **Delight in small doses.** Motion and polish reward the moments that matter (a ticket closing, money moving) and stay out of the way otherwise.

---

## Visual language

| Choice | What | Why |
|---|---|---|
| **Palette** | Warm off-white page (`#f7f5f0`), white cards, **deep navy** (`#0f2d52`) for structure and primary actions, **muted gold** (`#b08d3c`) as a thin accent only | It matches the Campus Customs storefront from HW 4, so the back office feels like the same business. Navy reads as dependable, which suits money and records. Gold is rationed so that when it appears (the header rule, the approval card, a balance change) it means "look here". |
| **Status colors** | Gold-tint "Open", navy-tint "In progress / Team working", slate "Waiting", amber "Needs a human", solid green "Resolved" | One meaning per color, used the same way everywhere (queue, detail header, summary). Amber is the only warning color, and it is reserved for things a person must act on. **Solid** green is used only for Resolved, so finished work is the most saturated badge on the page. |
| **Type** | Serif headings (Iowan Old Style / Palatino / Georgia), a clean sans for body, monospace for SKUs, ids, and tool names | Serif headings give the dashboard a ledger-like, "official records" feel, matching the storefront. Monospace marks machine values (`CC-TEE-WHITE`, `get_invoice_details(...)`), so people can tell data from prose at a glance. |
| **Numbers** | Tabular figures for every amount and time | Dollar amounts line up and don't jitter while the balance animates. |
| **Surfaces** | 8px corners, 1px borders, very soft shadows; hover lifts cards by 1px | Professional and restrained, with no heavy drop shadows or gradients competing with the content. The 1px lift tells people a card is clickable without shouting. |
| **Icons** | Small inline SVG line icons (check, arrow, play, alert, tool, mail); **no emoji** in the interface | Consistent stroke weight and color control. Emoji would clash with the tone of a financial tool. |
| **Agent identity** | Each agent has a monogram avatar in its own muted color: Boss navy (with a gold underline), Customer Service brick, Inventory teal, Accounting bronze, Facilities plum | People recognize *who* is speaking in the feed before reading a word. The colors are desaturated so five of them can sit side by side without turning the page into a rainbow. The Boss is the only one with the gold detail, which marks it as the one in charge. |

---

## Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [CC] Campus Customs        Business date              Checking $3,400.00 │  sticky navy bar
│      Back Office Desk      Monday, August 31, 2026    as of Aug 31  Reset│  gold rule underneath
├───────────────┬──────────────────────────────────────────────────────────┤
│ Ticket queue  │  #102 · RENT NOTICE · FROM ELM CITY PROPERTIES           │
│ 2 open·1 res. │  Rent due                          [ ▶ Start agent team ]│  ticket header
│ ┌───────────┐ │  ● Open  Lease #1                                        │
│ │#101  Open │ │  ┃ Ticket notes (untrusted) "Email: shop rent due…"      │
│ │Bulldog tee│ ├──────────────────────────────────────────────────────────┤
│ └───────────┘ │  ▲ Your approval is needed   $2,400.00 to Elm City …     │  only when asked
│ ┌───────────┐ ├──────────────────────────────────────────────────────────┤
│ │#102 ✓Res. │ │ [Boss] [Customer Svc] [Inventory] [Accounting] [Facil.]  │  agent roster
│ └───────────┘ ├──────────────────────────────────────────────────────────┤
│ ┌───────────┐ │  Live activity | Summary                                 │
│ │#103  Open │ │   B  Boss → Facilities  "Ticket 102 is a rent notice…"   │  feed / summary
│ └───────────┘ │   F  Checked the lease and cash  …$2,400 due 2026-09-02  │
└───────────────┴──────────────────────────────────────────────────────────┘
```

- **Two columns:** a fixed 340px **ticket queue** on the left (sticky, so it never scrolls away) and a flexible **workspace** on the right. This is the familiar email or helpdesk pattern (list on the left, the open item on the right), so it needs no explanation. On narrow screens the columns stack.
- **The workspace reads top to bottom in the order a person thinks:** *What is this ticket?* → *Do they need me?* → *Who is working on it?* → *What are they doing, and what happened?*
- **The checking balance lives in the header**, not in a tab, because money is the one number that matters on every ticket. It is visible at all times, including while you approve a payment further down the page.
- **The business date sits in the center of the header.** The agents reason about "today" as 2026-08-31, not the real date, so people need to see that too.
- **Reset** is a quiet outlined button in the header. It opens a confirmation dialog that explains exactly what will be restored and that the audit trail is kept.

---

## How tickets show up

Each ticket in the queue is a card with:
- `#id` in monospace, the ticket type in small caps ("CUSTOMER ORDER"), and a status pill on the right;
- the subject in the serif heading face (the most prominent line), then the requester;
- a monospace meta line with what the ticket references: `20 × CC-HOOD-NAVY · M`, `Lease #1`, `Invoice #501`.

A **3px accent bar** on the card's left edge carries the state:
- **gold** = waiting for work;
- **navy** = selected, and while the team is working it gently "breathes" (fades in and out), with a pulsing "Team working" pill;
- **green** = resolved.

**Selected** cards get a navy outline and a slightly deeper shadow.

### How resolved tickets look different

Resolved tickets change in four ways at once, so the difference is obvious at a glance, even in peripheral vision:

1. The card background becomes a **soft green wash** with a green border, and the left bar turns green.
2. The status pill becomes **solid green with a check mark** ("Resolved"). It is the only solid pill on the board.
3. A small **"✓ Closed out" seal** appears at the bottom of the card.
4. The subject text is **muted** to gray, so finished work recedes and the open tickets stand out.

In the workspace the "Start agent team" button is replaced by a green **"✓ Resolved"** badge, and the ticket notes show the Boss's resolving note, including the reply that was sent.

*Why:* green-and-check is a widely understood "done" signal. Muting the text instead of hiding the card keeps the record visible, so people can still open a resolved ticket and read what happened.

---

## Watching the agents work

- **Agent roster:** five tiles, one per agent, always in the same order. Each tile shows the agent's avatar, role, and live state:
  - *Standing by*
  - *Working*: a spinning ring around the avatar, three "typing" dots, and a navy glow
  - *Waiting on you*: gold glow
  - *Done*: green check
  - *Not needed*: the tile fades to 50%

  Under the state is the agent's latest line ("Asked accounting", "Lease 1 identifies Elm City…"). Clicking a tile filters the feed to that agent.
  
  *Why:* fading the agents who were *not* needed makes efficient routing visible. You can see at a glance that only three of the five agents touched a ticket.
- **Live activity feed:** a chat-style timeline (new rows slide in and the feed stays pinned to the bottom unless you scroll up). Different kinds of activity look different:
  - **Delegations:** `Boss → Facilities` with the request in a navy-tinted speech bubble.
  - **Tool use:** a compact card with a plain-English label ("Checked the lease and cash"), the exact call in faint monospace (`get_rent_due_and_cash_balance(lease_id: 1)`), and a one-line result ("Elm City Properties: $2400 due 2026-09-02 · checking $3400"). Results that need attention (out of stock, overdue, refused) are amber. **Click to expand** the raw JSON. People get the gist first and the evidence on demand.
  - **Agent text** in neutral bubbles. **Reports** get a green left rule ("Reported back"). **Approvals** appear as gold rows. **Customer replies** look like a letter (serif, cream paper).
  - **Run start and finish dividers** show the totals (agent runs, delegations, tokens), so cost is visible without being intrusive.
- **Summary tab:** opens automatically when a run finishes. It shows:
  - an **Outcome** card (final status, what was done, a "Handled by" row of avatar chips, the reply to the requester as a letter, anything still needing a person, and run stats);
  - a card per specialist with its summary, the **actions it took** (green checks), its recommended status, and a collapsible "*n* facts checked" list. Every fact cites the MCP tool it came from, so the summary can be audited.

---

## Human approval of payments and purchases

When Accounting tries to pay something, the agent **pauses** and an approval card appears at the top of the workspace, just under the ticket header, so it can't be missed.

- **Look:** white card with a **gold top border** and a warm gold glow, the alert icon, and the heading "Your approval is needed". It slides in. It is the only element on the page with a gold border, so it reads as "a person must act".
- **Content, ordered by what a careful approver checks:**
  - the **amount**, large in serif;
  - the **payee** in bold;
  - what it's **for** (looked up from the database, not taken from the agent's word);
  - the **due date** (overdue days shown in amber);
  - a red "**does not match**" warning if the amount differs from the bill;
  - the account, with the **balance before → after** this payment.
- **Friction on purpose:** you must type your name (remembered for next time) **and** tick "I checked the payee and the amount against the bill" before the buttons enable. The primary button states the exact amount ("Approve $2,400.00"). "Decline" sits beside it with an optional reason.

*Why:* this is the one moment where a mistake costs real money. A small, deliberate pause (name plus checkbox) prevents reflex clicks without adding a second dialog. Your name is what the database records as `approved_by`.

---

## How cash shows up

- **Header balance:** "CHECKING" eyebrow label, then the amount in a large serif with tabular figures, then "as of Aug 31, 2026".
- **When the balance changes:**
  - the number **counts down smoothly** to the new value (about 0.9s, easing out);
  - the panel **flashes a gold tint**;
  - the "as of" line becomes a **delta chip** (e.g. **−$2,400.00** in soft gold, or green for money coming in) for about 9 seconds before settling back.
- The approval card also shows **balance before → after**, so the money consequence is visible *before* you approve, not just after.

*Why:* a number that silently changes is easy to miss. A brief, physical-feeling count plus a delta turns "the balance updated" into something you notice and understand ("rent just went out"), without a toast or modal.

---

## Choices that make it pleasant to use

- **It explains itself:**
  - plain-English tool labels;
  - status names in words ("Needs a human", not "escalated");
  - empty states that tell you what to do ("Start the agent team to see them work");
  - an offline banner that gives the exact command to start the backend.
- **Live but calm:** polling keeps everything current (tickets 2.5s, approvals 2s, the active run's feed 1.2s). Motion is short, eased, and tied to meaning: a new row, a working agent, money moving, a ticket closing. Nothing loops while idle, and `prefers-reduced-motion` turns animation off.
- **Rewarding endings:** when the team finishes, the view switches to the Summary on its own, the ticket card turns green with its "Closed out" seal, and the resolved count in the queue header ticks up. People get a small sense of completion without confetti.
- **Respect for the reader's attention:** dense evidence (raw JSON, full fact lists) is folded away behind `details`, and the default view shows the story.
- **Safety cues are visual too:** ticket notes are labeled *"written by the requester; treated as untrusted"* in a muted quote block, and the agents' own appended notes are shown in monospace, so people can tell outside text from the team's records.
- **Accessible defaults:** real buttons and tabs with ARIA roles, visible focus outlines on inputs, the balance in an `aria-live` region, sufficient contrast on every pill, and a responsive layout that stacks on narrow screens.
