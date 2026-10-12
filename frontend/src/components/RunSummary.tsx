import type { AgentName, FeedItem, ShiftReport, SpecialistReport } from '../types'
import { AGENTS, AGENT_ORDER, humanize } from '../format'
import { Avatar } from './AgentRoster'
import { StatusPill } from './TicketList'
import { CheckIcon, MailIcon } from './Icons'

export function RunSummary({ items, ticketId }: { items: FeedItem[]; ticketId: number }) {
  const finished = items.filter((i) => i.kind === 'agent_finished')
  const runEnd = items.find((i) => i.kind === 'run_finished')
  const boss = [...finished].reverse().find((i) => i.agent === 'boss')
  const shift = boss?.detail.output as ShiftReport | undefined
  const outcome = shift?.tickets?.find((t) => t.ticket_id === ticketId) ?? shift?.tickets?.[0]

  // Latest report from each specialist, in roster order.
  const reports = new Map<AgentName, { report: SpecialistReport; error?: string }>()
  for (const f of finished) {
    if (!f.agent || f.agent === 'boss') continue
    reports.set(f.agent, f.detail.status === 'error'
      ? { report: { summary: f.text ?? '', facts: [], actions_taken: [], ticket_ids: [], recommended_status: null, needs_human: false, human_action_needed: null }, error: f.text ?? 'error' }
      : { report: f.detail.output as SpecialistReport })
  }
  const order = AGENT_ORDER.filter((a) => reports.has(a))
  const tokens = runEnd?.detail?.total_tokens

  if (!boss && order.length === 0) return <div className="empty">The summary appears here as each agent reports back.</div>

  return (
    <div className="summary">
      {outcome && (
        <section className="outcome">
          <div className="outcome-head">
            <div>
              <span className="eyebrow">Outcome</span>
              <h3>Ticket #{outcome.ticket_id}</h3>
            </div>
            <StatusPill status={outcome.final_status} />
          </div>
          <p className="outcome-text">{outcome.summary}</p>
          <div className="handled-by">
            Handled by {['boss', ...outcome.handled_by.filter((a) => a !== 'boss')].map((a) => (
              <span key={a} className="handled-chip"><Avatar agent={a as AgentName} size="sm" />{AGENTS[a as AgentName]?.label ?? a}</span>
            ))}
          </div>
          {outcome.customer_reply && (
            <div className="letter"><span className="eyebrow"><MailIcon size={12} /> Reply to the requester</span>{outcome.customer_reply}</div>
          )}
          {outcome.human_action_needed && (
            <div className="human-needed"><strong>Still needs a person:</strong> {outcome.human_action_needed}</div>
          )}
          {runEnd && (
            <div className="run-stats">
              <span>{runEnd.detail.agent_runs} agent runs</span>
              <span>{runEnd.detail.delegations} delegations</span>
              {tokens != null && <span>{Number(tokens).toLocaleString()} tokens</span>}
            </div>
          )}
        </section>
      )}

      <div className="report-grid">
        {order.map((a) => {
          const { report, error } = reports.get(a)!
          return (
            <article key={a} className={`report-card ${error ? 'is-error' : ''}`}>
              <header>
                <Avatar agent={a} />
                <div>
                  <div className="agent-name">{AGENTS[a].label}</div>
                  <div className="agent-role">{AGENTS[a].role}</div>
                </div>
                {report.recommended_status && <span className="rec">recommends <strong>{humanize(report.recommended_status)}</strong></span>}
              </header>
              <p>{report.summary}</p>
              {report.actions_taken?.length > 0 && (
                <>
                  <h4>Actions taken</h4>
                  <ul className="actions">{report.actions_taken.map((x, i) => <li key={i}><CheckIcon size={12} />{x}</li>)}</ul>
                </>
              )}
              {report.facts?.length > 0 && (
                <details className="facts">
                  <summary>{report.facts.length} facts checked</summary>
                  <ul>{report.facts.map((x, i) => <li key={i}>{x}</li>)}</ul>
                </details>
              )}
              {report.needs_human && report.human_action_needed && (
                <div className="human-needed small">{report.human_action_needed}</div>
              )}
            </article>
          )
        })}
      </div>

      {shift?.desk_note && (
        <section className="desk-note">
          <span className="eyebrow">Desk note from the Boss</span>
          <p>{shift.desk_note}</p>
        </section>
      )}
    </div>
  )
}
