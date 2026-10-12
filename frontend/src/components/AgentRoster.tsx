import type { AgentName } from '../types'
import { AGENTS, AGENT_ORDER } from '../format'
import { CheckIcon } from './Icons'

export type AgentState = 'idle' | 'working' | 'waiting' | 'done' | 'unused'

const STATE_LABEL: Record<AgentState, string> = {
  idle: 'Standing by',
  working: 'Working',
  waiting: 'Waiting on you',
  done: 'Done',
  unused: 'Not needed',
}

export function Avatar({ agent, size = 'md' }: { agent: AgentName; size?: 'sm' | 'md' | 'lg' }) {
  return <span className={`avatar avatar-${agent} avatar-${size}`} aria-hidden="true">{AGENTS[agent].initials}</span>
}

export function AgentRoster({ states, focus, onFocus, lastLine }: {
  states: Record<AgentName, AgentState>
  focus: AgentName | null
  onFocus: (a: AgentName | null) => void
  lastLine: Partial<Record<AgentName, string>>
}) {
  return (
    <div className="roster">
      {AGENT_ORDER.map((a) => {
        const s = states[a]
        return (
          <button
            key={a}
            className={`agent-tile state-${s} ${focus === a ? 'is-focus' : ''}`}
            onClick={() => onFocus(focus === a ? null : a)}
            title={focus === a ? 'Show everyone' : `Show only ${AGENTS[a].label}`}
          >
            <div className="agent-tile-top">
              <span className="avatar-wrap"><Avatar agent={a} />{s === 'working' && <span className="ring" />}</span>
              <div>
                <div className="agent-name">{AGENTS[a].label}</div>
                <div className="agent-role">{AGENTS[a].role}</div>
              </div>
            </div>
            <div className={`agent-state state-${s}`}>
              {s === 'done' && <CheckIcon size={12} />}
              {s === 'working' && <span className="typing"><i /><i /><i /></span>}
              {STATE_LABEL[s]}
            </div>
            {lastLine[a] && <div className="agent-last">{lastLine[a]}</div>}
          </button>
        )
      })}
    </div>
  )
}
