export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type TicketStatus =
  | 'open' | 'in_progress' | 'waiting_on_customer' | 'waiting_on_vendor' | 'escalated' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  state: 'open' | 'resolved'
  is_resolved: boolean
}

export interface RunInfo {
  run_id: string
  ticket_id: number
  started_at: string
  running: boolean
  ok?: boolean
  error?: string | null
}

export interface TicketsResponse {
  business_date: string
  active_run: RunInfo | null
  count: number
  open: number
  resolved: number
  tickets: Ticket[]
}

export interface Checking {
  account: string
  balance: number
  as_of: string
}

export type FeedKind =
  | 'run_started' | 'run_finished' | 'agent_started' | 'agent_finished' | 'agent_said' | 'agent_thought'
  | 'tool_call' | 'tool_result' | 'delegation' | 'approval' | 'customer_reply' | 'db_reset'

export interface FeedItem {
  id: number
  timestamp: string
  run_id: string
  agent: AgentName | null
  chain: AgentName[]
  kind: FeedKind
  tool?: string
  text: string | null
  detail: Record<string, any>
}

export interface EventsResponse {
  latest_id: number
  active_runs: string[]
  count: number
  events: FeedItem[]
}

export interface Approval {
  approval_id: number
  status: 'pending' | 'approved' | 'rejected' | 'failed'
  args: { kind: 'rent' | 'invoice'; ref_id: number; amount: number; account: string }
  requested_by: AgentName
  run_id: string
  agent_waiting: boolean
  requested_at: string
  decided_by: string | null
  result: Record<string, any> | null
  details: {
    payee: string | null
    label: string
    description: string | null
    amount_due?: number
    due_date?: string
    days_overdue?: number
  }
}

export interface TicketAgents {
  ticket_id: number
  status: TicketStatus
  run_id: string | null
  agents: { agent: AgentName; title: string; tools_used: string[]; active: boolean }[]
}

export interface SpecialistReport {
  ticket_ids: number[]
  summary: string
  facts: string[]
  actions_taken: string[]
  recommended_status: TicketStatus | null
  needs_human: boolean
  human_action_needed: string | null
  customer_message?: string | null
}

export interface ShiftReport {
  tickets: {
    ticket_id: number
    final_status: TicketStatus
    handled_by: AgentName[]
    summary: string
    customer_reply: string | null
    human_action_needed: string | null
  }[]
  desk_note: string
}
