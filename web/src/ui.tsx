import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import type { Label, Status, TimelineRow, Verification } from './contract'

export const GITHUB = 'https://github.com/Vibhugupta10616/RadLabel'

export const LogoMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true">
    <rect x="1" y="1" width="26" height="26" rx="7" fill="#0F6E6E" />
    <path d="M8 9h7a3.5 3.5 0 0 1 0 7H8zM8 16v4M14 16l4 4" stroke="#FFFFFF" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

export const Check = ({ size = 14, width = 2.5 }: { size?: number; width?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={width} strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7" /></svg>
)

export const Arrow = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
)

export const Warn = ({ size = 14, color = 'currentColor' }: { size?: number; color?: string }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className="flex-none"><path d="M12 3l9.5 17h-19z" /><path d="M12 10v4M12 17.5v.01" /></svg>
)

// Motion wrappers: with prefers-reduced-motion they render the end state, no animation.
const EASE = [0.2, 0.7, 0.2, 1] as const

export function Up({ delay = 0, className, children }: { delay?: number; className?: string; children: ReactNode }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay, ease: EASE }}>
      {children}
    </motion.div>
  )
}

export function Pop({ delay = 0, className, children }: { delay?: number; className?: string; children: ReactNode }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, scale: 0.86 }}
      animate={{ opacity: [0, 1, 1], scale: [0.86, 1.04, 1] }} transition={{ duration: 0.55, delay, times: [0, 0.7, 1], ease: 'easeOut' }}>
      {children}
    </motion.div>
  )
}

export function Reveal({ as = 'div', className, children }: { as?: 'div' | 'li' | 'p' | 'h2'; className?: string; children: ReactNode }) {
  const reduce = useReducedMotion()
  const M = motion[as]
  return (
    <M className={className} initial={reduce ? false : { opacity: 0, y: 18 }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.7, ease: EASE }}>
      {children}
    </M>
  )
}

export const STATUS_TEXT: Record<Status, string> = { present: 'Present', uncertain: 'Uncertain', absent: 'Absent', not_mentioned: 'Not mentioned' }
const STATUS_STYLE: Record<Status, string> = {
  present: 'bg-ink text-white', uncertain: 'bg-[#FFF1C9] text-[#6B4600]', absent: 'bg-[#E9EDF1] text-[#34424D]', not_mentioned: 'bg-[#F1F3F5] text-muted',
}

export const StatusPill = ({ status, small }: { status: Status; small?: boolean }) => (
  <span className={`${small ? 'text-[11px] px-2 py-0.5' : 'text-xs px-2.5 py-[3px]'} font-semibold rounded-full whitespace-nowrap ${STATUS_STYLE[status]}`}>
    {STATUS_TEXT[status]}
  </span>
)

type Kind = 'verified' | 'corrected' | 'suggested' | 'unverified'
const kindOf = (v: Verification): Kind => (v.startsWith('verified') ? 'verified' : (v as Kind))
const BADGE_STYLE: Record<Kind, string> = {
  verified: 'text-[#0B5C55] bg-[#E1F2EF]', corrected: 'text-[#1D4E89] bg-[#E4ECF7]',
  suggested: 'text-[#4E3590] bg-[#EEE8F8]', unverified: 'text-[#8A4300] bg-[#FCEBD9]',
}
const BADGE_ICON: Record<Kind, ReactNode> = {
  verified: <Check />,
  corrected: <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 20h4L19 9l-4-4L4 16z" /></svg>,
  suggested: <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>,
  unverified: <Warn />,
}

export function badgeText({ verification, corroboration }: Pick<Label, 'verification' | 'corroboration'>) {
  const kind = kindOf(verification)
  if (kind !== 'verified') return kind[0].toUpperCase() + kind.slice(1)
  if (verification === 'verified_impression_only' || corroboration === 'impression') return 'Verified · Impression only'
  return { both: 'Verified · both sections', findings: 'Verified · Findings only', none: 'Verified' }[corroboration ?? 'none']
}

export const Badge = ({ label }: { label: Pick<Label, 'verification' | 'corroboration'> }) => {
  const kind = kindOf(label.verification)
  return (
    <span className={`inline-flex items-center gap-[5px] text-xs font-semibold px-[9px] py-[3px] rounded-md ${BADGE_STYLE[kind]}`}>
      {BADGE_ICON[kind]}
      {badgeText(label)}
    </span>
  )
}

export const kindCount = (labels: Label[], kind: Kind) => labels.filter((l) => l.status !== 'not_mentioned' && kindOf(l.verification) === kind).length

const CELL: Record<Status, string> = {
  present: 'bg-teal text-white', uncertain: 'bg-[#FFF1C9] text-[#6B4600]', absent: 'bg-[#F1F3F5] text-[#5F6C77]', not_mentioned: 'bg-[#F1F3F5] text-[#5F6C77]',
}

// Status per report (rows = labels, columns = R1..Rn). Scrolls sideways when narrow: the label column stays put and a
// fade + text cue show while columns are hidden. `label` makes it a named, keyboard-scrollable region.
export function StatusGrid({ rows, n, label }: { rows: Pick<TimelineRow, 'label' | 'statuses'>[]; n: number; label?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState(false)
  useEffect(() => {
    const el = ref.current!
    const check = () => setMore(el.scrollLeft + el.clientWidth < el.scrollWidth - 1)
    check()
    const ro = new ResizeObserver(check)
    ro.observe(el)
    el.addEventListener('scroll', check, { passive: true })
    return () => { ro.disconnect(); el.removeEventListener('scroll', check) }
  }, [])
  const nos = Array.from({ length: n }, (_, i) => String(i + 1))
  return (
    <div>
      <div className="relative">
        <div ref={ref} tabIndex={label ? 0 : undefined} role={label ? 'region' : undefined} aria-label={label && `${label} (scrolls sideways)`}
          className="relative overflow-x-auto rounded-md">
          <table aria-label={label} className="w-full border-collapse table-fixed text-[13px]" style={{ minWidth: 120 + n * 68 }}>
            <thead>
              <tr>
                <td className="sticky left-0 z-[1] bg-white w-[120px] sm:w-[140px]" />
                {nos.map((no) => <th key={no} scope="col" className="pb-1 font-mono text-xs font-medium text-muted"><abbr title={`Report ${no}`} className="no-underline">R{no}</abbr></th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <th scope="row" className="sticky left-0 z-[1] bg-white text-left font-semibold pr-2 py-[3px]">{r.label}</th>
                  {nos.map((no) => {
                    const s = r.statuses[no] ?? 'not_mentioned'
                    return (
                      <td key={no} className="p-[3px]">
                        <span className={`block text-center px-1 py-1.5 rounded-md text-xs font-semibold ${CELL[s]}`}>
                          {s === 'not_mentioned' ? <><span aria-hidden="true">—</span><span className="sr-only">Not mentioned</span></> : STATUS_TEXT[s]}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {more && <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-white to-transparent" />}
      </div>
      {more && <p className="m-0 mt-2 text-xs text-muted" aria-hidden="true">Scroll sideways to see all {n} reports →</p>}
    </div>
  )
}
