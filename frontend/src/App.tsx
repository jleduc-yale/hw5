import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError, API_BASE } from './api'
import type { Approval, Checking, FeedItem, TicketsResponse } from './types'
import { Header } from './components/Header'
import { TicketList } from './components/TicketList'
import { TicketDetail } from './components/TicketDetail'

/** Run `fn` now and every `ms` while mounted. */
function usePoll(fn: () => void, ms: number, deps: unknown[] = []) {
  useEffect(() => {
    fn()
    const t = setInterval(fn, ms)
    return () => clearInterval(t)
  }, deps)  // eslint-disable-line react-hooks/exhaustive-deps
}

export default function App() {
  const [data, setData] = useState<TicketsResponse | null>(null)
  const [checking, setChecking] = useState<Checking | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [online, setOnline] = useState(true)
  // ?ticket=<id> deep-links straight to a ticket (used for shareable links and screenshots).
  const [selected, setSelected] = useState<number | null>(
    () => Number(new URLSearchParams(window.location.search).get('ticket')) || null,
  )
  const [runByTicket, setRunByTicket] = useState<Record<number, string>>({})
  const [events, setEvents] = useState<Record<string, FeedItem[]>>({})
  const cursors = useRef<Record<string, number>>({})
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState<string | null>(null)
  const [resetOpen, setResetOpen] = useState(false)

  const activeRun = data?.active_run ?? null

  // ---- polling --------------------------------------------------------------
  const refreshTickets = useCallback(() => {
    api.tickets().then((d) => { setData(d); setOnline(true) }).catch(() => setOnline(false))
  }, [])
  usePoll(refreshTickets, 2500)
  usePoll(() => { api.checking().then(setChecking).catch(() => {}) }, 2500)
  usePoll(() => { api.approvals().then((r) => setApprovals(r.approvals)).catch(() => {}) }, 2000)

  useEffect(() => {
    if (selected == null && data?.tickets.length) setSelected(data.tickets[0].id)
  }, [data, selected])

  // Which run to show for the selected ticket: the live one, else the latest run that touched it.
  useEffect(() => {
    if (selected == null) return
    if (activeRun && activeRun.ticket_id === selected) {
      setRunByTicket((m) => ({ ...m, [selected]: activeRun.run_id }))
      return
    }
    api.ticketAgents(selected).then((r) => {
      if (r.run_id) setRunByTicket((m) => (m[selected] === r.run_id ? m : { ...m, [selected]: r.run_id! }))
    }).catch(() => {})
  }, [selected, activeRun?.run_id, activeRun?.running])  // eslint-disable-line

  const runId = selected != null ? runByTicket[selected] : undefined
  const runIsLive = !!activeRun?.running && activeRun.run_id === runId

  const pullEvents = useCallback(async (rid: string) => {
    const after = cursors.current[rid]
    const r = await api.events(rid, after)
    cursors.current[rid] = r.latest_id
    if (r.events.length || after === undefined) {
      setEvents((m) => ({ ...m, [rid]: [...(after === undefined ? [] : m[rid] ?? []), ...r.events] }))
    }
  }, [])

  // Load the run's events once, then keep polling while it is live (and a little after, to catch the end).
  useEffect(() => {
    if (!runId) return
    let stop = false
    let tail = 3
    const loop = async () => {
      while (!stop) {
        try { await pullEvents(runId) } catch { /* offline; retry */ }
        if (!runIsLive && --tail <= 0) break
        await new Promise((res) => setTimeout(res, 1200))
      }
    }
    loop()
    return () => { stop = true }
  }, [runId, runIsLive, pullEvents])

  // ---- actions --------------------------------------------------------------
  const start = async () => {
    if (selected == null) return
    setStarting(true); setStartError(null)
    try {
      const run = await api.startRun(selected)
      setRunByTicket((m) => ({ ...m, [selected]: run.run_id }))
      refreshTickets()
    } catch (e) {
      setStartError(e instanceof ApiError ? e.message : 'Could not reach the desk API')
    } finally {
      setStarting(false)
    }
  }

  const decide = async (id: number, approve: boolean, approver: string, reason: string | null) => {
    if (approve) await api.approve(id, approver)
    else await api.reject(id, approver, reason)
    const [a, c] = await Promise.all([api.approvals(), api.checking()])
    setApprovals(a.approvals); setChecking(c)
  }

  const reset = async () => {
    try { await api.reset(false) }
    catch (e) {
      if (e instanceof ApiError && e.status === 409) await api.reset(true)
      else throw e
    }
    setEvents({}); cursors.current = {}; setRunByTicket({}); setResetOpen(false)
    refreshTickets(); api.checking().then(setChecking)
  }

  const ticket = data?.tickets.find((t) => t.id === selected) ?? null
  const runApprovals = approvals.filter((a) => a.status === 'pending' && (!runId || a.run_id === runId || !a.agent_waiting))

  return (
    <div className="app">
      <Header checking={checking} businessDate={data?.business_date ?? null} online={online} onReset={() => setResetOpen(true)} />

      {!online && (
        <div className="offline">Can't reach the desk API at <code>{API_BASE}</code>. Start it with <code>uvicorn main:app --reload --port 8000</code> in <code>backend/</code>.</div>
      )}

      <main className="layout">
        <TicketList
          tickets={data?.tickets ?? []}
          selected={selected}
          onSelect={(id) => { setSelected(id); setStartError(null) }}
          activeRun={activeRun}
          counts={{ open: data?.open ?? 0, resolved: data?.resolved ?? 0 }}
        />
        {ticket ? (
          <TicketDetail
            ticket={ticket}
            items={runId ? events[runId] ?? [] : []}
            run={activeRun}
            approvals={runApprovals}
            checking={checking}
            starting={starting}
            startError={startError}
            onStart={start}
            onDecide={decide}
          />
        ) : (
          <section className="detail"><div className="card empty">{online ? 'Loading tickets…' : ''}</div></section>
        )}
      </main>

      {resetOpen && (
        <div className="modal-backdrop" onClick={() => setResetOpen(false)}>
          <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
            <h3>Reset the shop data?</h3>
            <p>This restores <code>campus_customs_new.db</code> to the original copy: all tickets open, checking back to its starting balance, and pending approvals cleared. The audit trail is kept.</p>
            <div className="modal-actions">
              <button className="btn ghost" onClick={() => setResetOpen(false)}>Cancel</button>
              <button className="btn danger" onClick={reset}>Reset data</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
