import type { AgentName, TicketStatus } from './types'

export const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const signedMoney = (n: number) => `${n < 0 ? '−' : '+'}${money(Math.abs(n))}`

export const longDate = (iso: string | null | undefined) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
  }) : ''

export const shortDate = (iso: string | null | undefined) =>
  iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : ''

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })

export const AGENTS: Record<AgentName, { label: string; role: string; initials: string }> = {
  boss: { label: 'Boss', role: 'Shop manager', initials: 'B' },
  inventory: { label: 'Inventory', role: 'Stock manager', initials: 'In' },
  accounting: { label: 'Accounting', role: 'Bookkeeper', initials: 'Ac' },
  facilities: { label: 'Facilities', role: 'Premises & lease', initials: 'F' },
  customer_service: { label: 'Customer Service', role: 'Voice of the shop', initials: 'CS' },
}
export const AGENT_ORDER: AgentName[] = ['boss', 'customer_service', 'inventory', 'accounting', 'facilities']

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_on_customer: 'Waiting on customer',
  waiting_on_vendor: 'Waiting on vendor',
  escalated: 'Needs a human',
  resolved: 'Resolved',
}

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export const TOOL_LABEL: Record<string, string> = {
  get_business_date: 'Checked the business date',
  list_open_tickets: 'Listed open tickets',
  list_all_tickets: 'Listed all tickets',
  get_ticket_details: 'Read the ticket',
  check_stock_for_sku_and_size: 'Checked stock',
  list_vendors: 'Looked up vendors',
  get_rent_due_and_cash_balance: 'Checked the lease and cash',
  get_invoice_details: 'Read the invoice',
  get_cash_account_balances: 'Checked cash balances',
  get_price_and_cost_for_sku: 'Looked up price and cost',
  decrement_inventory_for_order: 'Pulled stock for the order',
  record_payment: 'Recorded a payment',
  update_ticket_status: 'Updated the ticket',
  add_desk_note: 'Wrote the desk note',
}

export const humanize = (s: string) => s.replace(/_/g, ' ')
