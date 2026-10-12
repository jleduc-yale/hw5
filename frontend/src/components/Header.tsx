import { useEffect, useRef, useState } from 'react'
import type { Checking } from '../types'
import { longDate, money, shortDate, signedMoney } from '../format'
import { ResetIcon } from './Icons'

/** Animates a number toward its new value so balance changes are felt, not just read. */
function useCountUp(value: number | undefined, ms = 900) {
  const [shown, setShown] = useState(value)
  const from = useRef(value)
  useEffect(() => {
    if (value === undefined) return
    if (from.current === undefined) { from.current = value; setShown(value); return }
    const start = performance.now(), a = from.current, b = value
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(a + (b - a) * eased)
      if (k < 1) raf = requestAnimationFrame(tick)
      else from.current = b
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, ms])
  return shown
}

export function Header({ checking, businessDate, online, onReset }: {
  checking: Checking | null
  businessDate: string | null
  online: boolean
  onReset: () => void
}) {
  const shown = useCountUp(checking?.balance)
  const prev = useRef<number | undefined>(undefined)
  const [delta, setDelta] = useState<{ amount: number; key: number } | null>(null)

  useEffect(() => {
    if (checking == null) return
    if (prev.current !== undefined && Math.abs(prev.current - checking.balance) > 0.004) {
      setDelta({ amount: checking.balance - prev.current, key: Date.now() })
    }
    prev.current = checking.balance
  }, [checking])

  useEffect(() => {
    if (!delta) return
    const t = setTimeout(() => setDelta(null), 9000)
    return () => clearTimeout(t)
  }, [delta])

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">CC</div>
        <div>
          <div className="brand-name">Campus Customs</div>
          <div className="brand-sub">Back Office Desk</div>
        </div>
      </div>

      <div className="topbar-date">
        <span className="eyebrow light">Business date</span>
        <span>{businessDate ? longDate(businessDate) : '—'}</span>
      </div>

      <div className="topbar-right">
        <div className={`balance ${delta ? 'balance-changed' : ''}`} aria-live="polite">
          <span className="eyebrow light">Checking</span>
          <span className="balance-amount">{shown === undefined ? '—' : money(shown)}</span>
          <span className="balance-asof">
            {delta
              ? <span key={delta.key} className={`delta ${delta.amount < 0 ? 'neg' : 'pos'}`}>{signedMoney(delta.amount)}</span>
              : checking ? `as of ${shortDate(checking.as_of)}` : online ? '' : 'offline'}
          </span>
        </div>
        <button className="btn ghost-light" onClick={onReset} title="Restore the database to its starting state">
          <ResetIcon /> Reset data
        </button>
      </div>
    </header>
  )
}
