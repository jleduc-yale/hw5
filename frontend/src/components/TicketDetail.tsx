import { useMemo, useState, useEffect } from 'react'
import type { AgentName, Approval, Checking, FeedItem, RunInfo, Ticket } from '../types'
import { AGENT_ORDER, TYPE_LABEL } from '../format'
import { ActivityFeed } from './ActivityFeed'
import { AgentRoster, type AgentState } from './AgentRoster'
import { ApprovalCard } from './ApprovalCard'
import { RunSummary } from './RunSummary'
import { StatusPill } from './TicketList'
import { CheckIcon, PlayIcon } from './Icons'

function agentStates(items: FeedItem[], running: boolean, waitingAgents: Set<AgentName>) {
  const open = new Map<AgentName, number>()
  const seen = new Set<AgentName>()
  for (const it of items) {
    if (!it.agent) continue
    if (it.kind === 'agent_started') { seen.add(it.agent); open.set(it.agent, (open.get(it.agent) ?? 0) + 1) }
    if (it.kind === 'agent_finished') open.set(it.agent, Math.max(0, (open.get(it.agent) ?? 1) - 1))
  }
  const states = {} as Record<AgentName, AgentState>
  for (const a of AGENT_ORDER) {
    if (waitingAgents.has(a)) states[a] = 'waiting'
    else if ((open.get(a) ?? 0) > 0 && running) states[a] = 'working'
    else if (seen.has(a)) states[a] = 'done'
    else states[a] = running || items.length === 0 ? 'idle' : 'unused'
  }
  return states
}

function lastLines(items: FeedItem[]) {
  const out: Partial<Record<AgentName, string>> = {}
  for (const it of items) {
    if (!it.agent) continue
    if (it.kind === 'tool_call') out[it.agent] = `Using ${it.tool}`
    else if (it.kind === 'delegation') out[it.agent] = `Asked ${String(it.detail.to).replace('_', ' ')}`
    else if (it.kind === 'agent_said' && it.text) out[it.agent] = it.text
    else if (it.kind === 'agent_finished' && it.text) out[it.agent] = it.text
  }
  return out
}

export function TicketDetail({ ticket, items, run, approvals, checking, starting, startError, onStart, onDecide }: {
  ticket: Ticket
  items: FeedItem[]
  run: RunInfo | null
  approvals: Approval[]
  checking: Checking | null
  starting: boolean
  startError: string | null
  onStart: () => void
  onDecide: (id: number, approve: boolean, approver: string, reason: string | null) => Promise<void>
}) {
  const running = !!run?.running && run.ticket_id === ticket.id
  const runFinished = items.some((i) => i.kind === 'run_finished')
  const [tab, setTab] = useState<'live' | 'summary'>('live')
  const [focus, setFocus] = useState<AgentName | null>(null)

  useEffect(() => { setFocus(null); setTab(runFinished ? 'summary' : 'live') }, [ticket.id])  // eslint-disable-line
  useEffect(() => { if (runFinished && !running) setTab('summary') }, [runFinished, running])
  useEffect(() => { if (running) setTab('live') }, [running])

  const pending = approvals.filter((a) => a.status === 'pending')
  const waitingAgents = new Set(pending.filter((a) => a.agent_waiting).map((a) => a.requested_by))
  const states = useMemo(() => agentStates(items, running, waitingAgents), [items, running, pending.length])  // eslint-disable-line
  const lines = useMemo(() => lastLines(items), [items])
  const another = run?.running && run.ticket_id !== ticket.id

  return (
    <section className="detail">
      <div className="detail-head card">
        <div className="detail-title">
          <div className="eyebrow">#{ticket.id} · {TYPE_LABEL[ticket.type] ?? ticket.type} · from {ticket.requester}</div>
          <h1>{ticket.subject}</h1>
          <div className="detail-facts">
            <StatusPill status={ticket.status} working={running} />
            {ticket.sku && <span><strong>{ticket.qty}</strong> × {ticket.sku}, size {ticket.size}</span>}
            {ticket.lease_id != null && <span>Lease #{ticket.lease_id}</span>}
            {ticket.invoice_id != null && <span>Linked invoice #{ticket.invoice_id}</span>}
          </div>
        </div>
        <div className="detail-action">
          {ticket.is_resolved ? (
            <span className="done-badge"><CheckIcon /> Resolved</span>
          ) : (
            <button className="btn primary lg" onClick={onStart} disabled={running || starting || !!another}>
              {running || starting ? <><span className="spinner" /> Team working…</> : <><PlayIcon /> {items.length ? 'Run the team again' : 'Start agent team'}</>}
            </button>
          )}
          {another && <span className="hint">The team is busy with ticket #{run!.ticket_id}.</span>}
          {startError && <span className="form-error">{startError}</span>}
        </div>
        {ticket.notes && (
          <blockquote className="request-note">
            <span className="eyebrow">Ticket notes <em>(written by the requester; treated as untrusted)</em></span>
            {ticket.notes.split('\n').map((l, i) => <span key={i} className={l.startsWith('[') ? 'agent-note' : ''}>{l}</span>)}
          </blockquote>
        )}
      </div>

      {pending.map((a) => <ApprovalCard key={a.approval_id} approval={a} checking={checking} onDecide={onDecide} />)}

      <AgentRoster states={states} focus={focus} onFocus={setFocus} lastLine={lines} />

      <div className="card panel">
        <div className="panel-tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'live'} onClick={() => setTab('live')}>
            Live activity {running && <span className="pulse-dot" />}
          </button>
          <button role="tab" aria-selected={tab === 'summary'} onClick={() => setTab('summary')}>Summary</button>
          {focus && tab === 'live' && <button className="chip-clear" onClick={() => setFocus(null)}>Showing one agent · show all</button>}
        </div>
        {tab === 'live'
          ? <ActivityFeed items={items} focus={focus} running={running || starting} />
          : <RunSummary items={items} ticketId={ticket.id} />}
      </div>
    </section>
  )
}
