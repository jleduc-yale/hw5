import { useEffect, useMemo, useRef, useState } from 'react'
import type { AgentName, FeedItem } from '../types'
import { AGENTS, TOOL_LABEL, clock, humanize } from '../format'
import { Avatar } from './AgentRoster'
import { ArrowIcon, MailIcon, ToolIcon } from './Icons'

type Row =
  | { type: 'item'; item: FeedItem }
  | { type: 'tool'; call: FeedItem; result: FeedItem | null }

function buildRows(items: FeedItem[]): Row[] {
  const rows: Row[] = []
  for (const it of items) {
    if (it.kind === 'tool_result') {
      const open = [...rows].reverse().find(
        (r): r is Extract<Row, { type: 'tool' }> =>
          r.type === 'tool' && !r.result && r.call.tool === it.tool && r.call.agent === it.agent,
      )
      if (open) { open.result = it; continue }
    }
    if (it.kind === 'tool_call') rows.push({ type: 'tool', call: it, result: null })
    else rows.push({ type: 'item', item: it })
  }
  return rows
}

const fmtArgs = (args: Record<string, unknown> | undefined) =>
  args ? Object.entries(args).map(([k, v]) => `${k}: ${typeof v === 'string' ? `"${v}"` : JSON.stringify(v)}`).join(', ') : ''

/** One readable line for a tool result. */
function resultLine(tool: string | undefined, r: any): { text: string; tone: 'ok' | 'warn' } {
  if (!r) return { text: 'running…', tone: 'ok' }
  if (r.error) return { text: `error: ${r.error}`, tone: 'warn' }
  const res = r.result ?? {}
  if (res.refused || res.ok === false) return { text: res.reason ?? 'refused', tone: 'warn' }
  if (res.found === false) return { text: 'not found', tone: 'warn' }
  switch (tool) {
    case 'check_stock_for_sku_and_size':
      return { text: `${res.qty_on_hand} on hand in ${res.size} (${res.location}) · all sizes ${Object.entries(res.all_sizes_for_sku ?? {}).map(([s, q]) => `${s} ${q}`).join(', ')}`, tone: res.in_stock ? 'ok' : 'warn' }
    case 'get_rent_due_and_cash_balance':
      return { text: `${res.landlord}: $${res.monthly_rent} due ${res.next_due} · ${(res.cash_accounts ?? []).map((a: any) => `${a.name} $${a.balance}`).join(', ')}`, tone: 'ok' }
    case 'get_invoice_details':
      return { text: `#${res.id} ${res.vendor?.name}: $${res.amount}, ${res.status}, due ${res.due_date}${res.days_overdue > 0 ? ` (${res.days_overdue} days overdue)` : ''}`, tone: res.days_overdue > 0 && res.status === 'open' ? 'warn' : 'ok' }
    case 'get_price_and_cost_for_sku':
      return { text: `list $${res.list_price} · cost $${res.unit_cost}`, tone: 'ok' }
    case 'record_payment':
      return { text: `paid $${res.amount} · ${res.account} now $${res.balance_after} · approved by ${res.approved_by}`, tone: 'ok' }
    case 'update_ticket_status':
      return { text: `${humanize(res.old_status ?? '')} → ${humanize(res.new_status ?? '')}`, tone: 'ok' }
    case 'decrement_inventory_for_order':
      return { text: `${res.qty_before} → ${res.qty_after} on hand`, tone: 'ok' }
    case 'list_vendors':
      return { text: (res.vendors ?? []).map((v: any) => `${v.name} (${v.lead_days}d)`).join(', '), tone: 'ok' }
    case 'get_ticket_details':
      return { text: `${res.subject} · ${humanize(res.status ?? '')}`, tone: 'ok' }
    case 'get_business_date':
      return { text: res.date_today, tone: 'ok' }
    case 'add_desk_note':
      return { text: 'handoff note saved for the next shift', tone: 'ok' }
    case 'list_open_tickets':
    case 'list_all_tickets':
      return { text: `${res.count} tickets`, tone: 'ok' }
    default: {
      const scalars = Object.entries(res).filter(([, v]) => v !== null && typeof v !== 'object').slice(0, 4)
      return { text: scalars.map(([k, v]) => `${humanize(k)} ${v}`).join(' · ') || 'done', tone: 'ok' }
    }
  }
}

function AgentLabel({ agent, time }: { agent: AgentName | null; time: string }) {
  return (
    <div className="feed-who">
      <strong>{agent ? AGENTS[agent].label : 'Desk'}</strong>
      <span className="feed-time">{clock(time)}</span>
    </div>
  )
}

function RowView({ row }: { row: Row }) {
  if (row.type === 'tool') {
    const { call, result } = row
    const line = resultLine(call.tool, result?.detail)
    return (
      <li className="feed-row kind-tool">
        {call.agent && <Avatar agent={call.agent} size="sm" />}
        <div className="feed-main">
          <AgentLabel agent={call.agent} time={call.timestamp} />
          <details className="tool-card">
            <summary>
              <ToolIcon size={13} />
              <span className="tool-label">{TOOL_LABEL[call.tool ?? ''] ?? call.tool}</span>
              <code className="tool-name">{call.tool}({fmtArgs(call.detail.args)})</code>
              <span className={`tool-result tone-${line.tone}`}>{line.text}</span>
            </summary>
            <pre>{JSON.stringify(result?.detail?.result ?? result?.detail ?? null, null, 2)}</pre>
          </details>
        </div>
      </li>
    )
  }
  const it = row.item
  switch (it.kind) {
    case 'run_started':
      return <li className="feed-divider"><span>Run started · {clock(it.timestamp)}</span></li>
    case 'run_finished':
      return <li className="feed-divider end"><span>Run finished · {clock(it.timestamp)} · {it.text}</span></li>
    case 'agent_started':
      return it.detail.requested_by === 'human' ? null : (
        <li className="feed-row kind-joined">
          {it.agent && <Avatar agent={it.agent} size="sm" />}
          <div className="feed-main muted-line">{it.agent ? AGENTS[it.agent].label : ''} picked up the request</div>
        </li>
      )
    case 'delegation': {
      const to = it.detail.to as AgentName
      return (
        <li className={`feed-row kind-delegation ${it.detail.accepted ? '' : 'refused'}`}>
          {it.agent && <Avatar agent={it.agent} size="sm" />}
          <div className="feed-main">
            <div className="feed-who">
              <strong>{it.agent ? AGENTS[it.agent].label : ''}</strong>
              <ArrowIcon size={13} className="arrow" />
              <strong>{AGENTS[to]?.label ?? to}</strong>
              <span className="feed-time">{clock(it.timestamp)}</span>
            </div>
            <div className="bubble">{it.detail.request}</div>
            {!it.detail.accepted && <div className="refusal">Not sent: {it.detail.refusal}</div>}
          </div>
        </li>
      )
    }
    case 'agent_said':
    case 'agent_thought':
      return (
        <li className={`feed-row kind-${it.kind}`}>
          {it.agent && <Avatar agent={it.agent} size="sm" />}
          <div className="feed-main">
            <AgentLabel agent={it.agent} time={it.timestamp} />
            <div className={it.kind === 'agent_thought' ? 'thought' : 'bubble'}>{it.text}</div>
          </div>
        </li>
      )
    case 'approval':
      return (
        <li className="feed-row kind-approval">
          {it.agent ? <Avatar agent={it.agent} size="sm" /> : <span className="avatar avatar-human avatar-sm">You</span>}
          <div className="feed-main">
            <AgentLabel agent={it.agent} time={it.timestamp} />
            <div className="approval-line">{it.text}{it.detail.approver ? ` · ${it.detail.approver}` : ''}</div>
          </div>
        </li>
      )
    case 'agent_finished':
      return (
        <li className="feed-row kind-finished">
          {it.agent && <Avatar agent={it.agent} size="sm" />}
          <div className="feed-main">
            <AgentLabel agent={it.agent} time={it.timestamp} />
            <div className={`finished ${it.detail.status === 'error' ? 'is-error' : ''}`}>
              <span className="eyebrow">{it.detail.status === 'error' ? 'Stopped with an error' : 'Reported back'}</span>
              {it.text}
            </div>
          </div>
        </li>
      )
    case 'customer_reply':
      return (
        <li className="feed-row kind-reply">
          {it.agent && <Avatar agent={it.agent} size="sm" />}
          <div className="feed-main">
            <div className="letter"><span className="eyebrow"><MailIcon size={12} /> Draft reply to the customer</span>{it.text}</div>
          </div>
        </li>
      )
    default:
      return null
  }
}

export function ActivityFeed({ items, focus, running }: { items: FeedItem[]; focus: AgentName | null; running: boolean }) {
  const rows = useMemo(() => buildRows(focus ? items.filter((i) => i.agent === focus) : items), [items, focus])
  const listRef = useRef<HTMLDivElement>(null)
  const [pinned, setPinned] = useState(true)

  useEffect(() => {
    const el = listRef.current
    if (el && pinned) el.scrollTop = el.scrollHeight
  }, [rows.length, pinned])

  return (
    <div className="feed-wrap">
      <div
        className="feed-scroll"
        ref={listRef}
        onScroll={(e) => {
          const el = e.currentTarget
          setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 40)
        }}
      >
        {rows.length === 0
          ? <div className="empty">{running ? 'The Boss is reading the ticket…' : 'No activity yet. Start the agent team to see them work.'}</div>
          : <ol className="feed">{rows.map((r) => <RowView key={r.type === 'tool' ? `t${r.call.id}` : `i${r.item.id}-${r.item.kind}`} row={r} />)}</ol>}
        {running && rows.length > 0 && <div className="feed-live"><span className="pulse-dot" /> Live</div>}
      </div>
    </div>
  )
}
