import { useState } from 'react'
import type { Approval, Checking } from '../types'
import { AGENTS, money, shortDate } from '../format'
import { AlertIcon } from './Icons'

const NAME_KEY = 'cc.approverName'

export function ApprovalCard({ approval, checking, onDecide }: {
  approval: Approval
  checking: Checking | null
  onDecide: (id: number, approve: boolean, approver: string, reason: string | null) => Promise<void>
}) {
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) ?? '')
  const [checked, setChecked] = useState(false)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState<'approve' | 'reject' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { args, details } = approval
  const after = checking ? checking.balance - args.amount : null
  const ready = name.trim().length > 1 && checked && !busy

  const decide = async (approve: boolean) => {
    setBusy(approve ? 'approve' : 'reject'); setError(null)
    localStorage.setItem(NAME_KEY, name.trim())
    try { await onDecide(approval.approval_id, approve, name.trim(), reason.trim() || null) }
    catch (e: any) { setError(e?.message ?? 'Something went wrong') }
    finally { setBusy(null) }
  }

  return (
    <section className="approval" role="alertdialog" aria-labelledby={`appr-${approval.approval_id}`}>
      <div className="approval-head">
        <AlertIcon size={18} />
        <div>
          <h3 id={`appr-${approval.approval_id}`}>Your approval is needed</h3>
          <p>
            {AGENTS[approval.requested_by]?.label ?? approval.requested_by} wants to make a payment
            {approval.agent_waiting ? ' and is waiting for your decision.' : '.'} Nothing is paid until you approve.
          </p>
        </div>
      </div>

      <div className="approval-body">
        <div className="approval-amount">
          <span className="eyebrow">{details.label}{args.kind === 'invoice' ? ` #${args.ref_id}` : ` · lease #${args.ref_id}`}</span>
          <span className="approval-figure">{money(args.amount)}</span>
          <span className="approval-payee">to <strong>{details.payee ?? 'unknown payee'}</strong></span>
        </div>
        <dl className="approval-facts">
          {details.description && <><dt>For</dt><dd>{details.description}</dd></>}
          {details.due_date && <><dt>Due</dt><dd>{shortDate(details.due_date)}
            {details.days_overdue != null && details.days_overdue > 0 && <span className="overdue"> · {details.days_overdue} days overdue</span>}</dd></>}
          {details.amount_due != null && details.amount_due !== args.amount &&
            <><dt>Bill says</dt><dd className="mismatch">{money(details.amount_due)} (does not match)</dd></>}
          <dt>From</dt><dd>{args.account}{checking && <> · {money(checking.balance)} → <strong>{money(after)}</strong></>}</dd>
        </dl>
      </div>

      <div className="approval-form">
        <label className="field">
          <span>Your name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name of the approver" />
        </label>
        <label className="field grow">
          <span>Note (optional, used if you decline)</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" />
        </label>
        <label className="check">
          <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
          I checked the payee and the amount against the bill.
        </label>
        <div className="approval-actions">
          <button className="btn ghost" disabled={!ready} onClick={() => decide(false)}>
            {busy === 'reject' ? 'Declining…' : 'Decline'}
          </button>
          <button className="btn primary" disabled={!ready} onClick={() => decide(true)}>
            {busy === 'approve' ? 'Paying…' : `Approve ${money(args.amount)}`}
          </button>
        </div>
        {error && <p className="form-error">{error}</p>}
      </div>
    </section>
  )
}
