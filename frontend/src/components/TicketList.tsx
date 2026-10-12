import type { RunInfo, Ticket } from '../types'
import { STATUS_LABEL, TYPE_LABEL } from '../format'
import { CheckIcon } from './Icons'

export function StatusPill({ status, working }: { status: Ticket['status']; working?: boolean }) {
  if (working) return <span className="pill pill-working"><span className="pulse-dot" />Team working</span>
  return (
    <span className={`pill pill-${status}`}>
      {status === 'resolved' && <CheckIcon size={12} />}
      {STATUS_LABEL[status] ?? status}
    </span>
  )
}

export function TicketList({ tickets, selected, onSelect, activeRun, counts }: {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
  activeRun: RunInfo | null
  counts: { open: number; resolved: number }
}) {
  return (
    <aside className="queue">
      <div className="queue-head">
        <h2>Ticket queue</h2>
        <div className="queue-counts">
          <span><strong>{counts.open}</strong> open</span>
          <span className="dot-sep" />
          <span><strong>{counts.resolved}</strong> resolved</span>
        </div>
      </div>
      <ol className="ticket-list">
        {tickets.map((t) => {
          const working = activeRun?.running && activeRun.ticket_id === t.id
          return (
            <li key={t.id}>
              <button
                className={`ticket-card ${t.is_resolved ? 'is-resolved' : ''} ${selected === t.id ? 'is-selected' : ''} ${working ? 'is-working' : ''}`}
                onClick={() => onSelect(t.id)}
                aria-pressed={selected === t.id}
              >
                <div className="ticket-card-top">
                  <span className="ticket-id">#{t.id}</span>
                  <span className="ticket-type">{TYPE_LABEL[t.type] ?? t.type}</span>
                  <StatusPill status={t.status} working={!!working} />
                </div>
                <div className="ticket-subject">{t.subject}</div>
                <div className="ticket-requester">{t.requester}</div>
                <div className="ticket-meta">
                  {t.sku && <span>{t.qty} × {t.sku} · {t.size}</span>}
                  {t.lease_id != null && <span>Lease #{t.lease_id}</span>}
                  {t.invoice_id != null && <span>Invoice #{t.invoice_id}</span>}
                </div>
                {t.is_resolved && <div className="resolved-seal"><CheckIcon size={12} /> Closed out</div>}
              </button>
            </li>
          )
        })}
      </ol>
    </aside>
  )
}
