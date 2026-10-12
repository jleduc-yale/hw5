import type { Approval, Checking, EventsResponse, RunInfo, TicketAgents, TicketsResponse } from './types'

/** The desk API (FastAPI). Override with VITE_API_BASE if the backend runs elsewhere. */
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : (detail as any)?.message ?? `HTTP ${status}`)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const body = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body)
  return body as T
}

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  tickets: () => request<TicketsResponse>('/api/tickets'),
  ticketAgents: (id: number) => request<TicketAgents>(`/api/tickets/${id}/agents`),
  startRun: (id: number) => post<RunInfo>(`/api/tickets/${id}/run`, {}),
  events: (runId: string, after?: number) =>
    request<EventsResponse>(
      `/api/events?run_id=${encodeURIComponent(runId)}&limit=1000${after !== undefined ? `&after=${after}` : ''}`,
    ),
  approvals: () => request<{ count: number; approvals: Approval[] }>('/api/approvals?status=all'),
  approve: (id: number, approver: string) =>
    post<Approval>(`/api/approvals/${id}/approve`, { approver, confirm: true }),
  reject: (id: number, approver: string, reason: string | null) =>
    post<Approval>(`/api/approvals/${id}/reject`, { approver, confirm: true, reason }),
  checking: () => request<Checking>('/api/cash/checking'),
  reset: (force = false) => post<{ ok: boolean }>('/api/reset', { confirm: true, force }),
}
