import { motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { api } from '../api'
import type { AskResult, Citation, Label, LabelName, Report, Sentence, Status, TimelineRow } from '../contract'
import { SAMPLE_SUGGESTIONS } from '../mocks/sample'
import { useSession, type SessionState } from '../session'
import { Badge, kindCount, LogoMark, STATUS_TEXT, StatusPill, Warn } from '../ui'

type Mode = 'report' | 'all'
type Turn = { q: string; res?: AskResult; error?: string }

const ORDER: Record<Status, number> = { present: 0, uncertain: 1, absent: 2, not_mentioned: 3 }
const box = 'bg-white border border-line rounded-2xl p-5 sm:p-6'
const sectionHead = 'm-0 mb-1.5 text-xs font-semibold tracking-[0.08em] uppercase text-muted'
const citeBtn = 'min-h-8 px-2.5 rounded-md border border-[#9FC2C2] bg-white text-teal-text font-mono text-[13px] cursor-pointer hover:border-teal hover:bg-[#F3F8F8]'
const plural = (k: number, word: string) => `${k} ${word}${k === 1 ? '' : 's'}`

export function Results() {
  const { state } = useSession()
  if (state.status === 'idle') return <Navigate to="/upload" replace />
  return state.status === 'ready' ? <ResultsView {...state} /> : <Shell state={state}><Pending state={state} /></Shell>
}

function Shell({ state, picker, children }: { state: SessionState; picker?: React.ReactNode; children: React.ReactNode }) {
  const ready = state.status === 'ready'
  return (
    <div className="min-h-screen font-sans text-ink bg-page pb-24 lg:pb-0">
      <header className="bg-white border-b border-line">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between flex-wrap gap-x-3 gap-y-2">
          <Link to="/" className="flex items-center gap-2.5 no-underline text-ink text-xl font-bold"><LogoMark />RadLabel</Link>
          <div className="flex gap-2 sm:gap-3 items-center flex-wrap">
            <span className="hidden sm:inline text-[13px] text-muted">
              {ready && `${state.sample ? 'Sample patient · ' : ''}${plural(state.reports.length, 'report')} · `}processed in memory, not stored
            </span>
            {picker}
            <Link to="/upload" aria-label="New upload" className="inline-flex items-center min-h-10 px-4 rounded-full border border-[#9FC2C2] text-teal-text font-semibold text-sm no-underline hover:border-teal">New<span className="hidden sm:inline">&nbsp;upload</span></Link>
          </div>
        </div>
      </header>
      {children}
      <footer className="border-t border-line bg-white mt-2">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-4 flex flex-wrap justify-between gap-3 text-[13px] text-muted">
          <span><strong className="text-[#8A2C0D]">Not a medical device.</strong> Labels describe the report text, not the image.{ready && state.sample && ' The sample patient is made up.'}</span>
          <span>Reference data: Indiana University Chest X-ray Collection (Open-i, NLM), CC BY-NC-ND 4.0</span>
        </div>
      </footer>
    </div>
  )
}

function Pending({ state }: { state: SessionState }) {
  const { retry } = useSession()
  if (state.status === 'error') {
    return (
      <main className="max-w-[720px] mx-auto p-4 sm:p-6">
        <div role="alert" className={`${box} flex flex-col gap-3`}>
          <h1 className="m-0 text-[22px]">We couldn't analyze your reports</h1>
          <p className="m-0 text-[15px] leading-relaxed text-body">{state.status === 'error' && state.message}</p>
          <div className="flex gap-3 flex-wrap">
            <button type="button" onClick={retry} className="min-h-11 px-5 rounded-[10px] bg-teal text-white font-semibold border-0 cursor-pointer hover:bg-[#0B5A5A]">Try again</button>
            <Link to="/upload" className="inline-flex items-center min-h-11 px-5 rounded-[10px] border border-[#9FC2C2] text-teal-text font-semibold no-underline">Back to upload</Link>
          </div>
        </div>
      </main>
    )
  }
  const count = state.status === 'loading' ? state.count : 0
  return (
    <main className="max-w-[1400px] mx-auto p-4 sm:p-6 flex flex-col gap-5">
      <div role="status" className={`${box} flex flex-col gap-2`}>
        <h1 className="m-0 text-[22px]">Analyzing {count ? plural(count, 'report') : 'your reports'}…</h1>
        <p className="m-0 text-[15px] text-body">Labelling 13 findings per report, checking each label, and building a search index for this visit only.</p>
      </div>
      <div aria-hidden="true" className="flex flex-wrap gap-5">
        <div className={`${box} flex-[999_1_520px] flex flex-col gap-3`}>
          {[90, 75, 82, 60, 70].map((w, i) => <div key={i} className="h-4 rounded bg-[#EDF1F3] animate-pulse" style={{ width: `${w}%` }} />)}
        </div>
        <div className="flex-[1_1_340px] lg:max-w-[420px] flex flex-col gap-2.5">
          {[0, 1, 2].map((i) => <div key={i} className="h-[88px] rounded-xl bg-white border border-line animate-pulse" />)}
        </div>
      </div>
    </main>
  )
}

function summary(r: Report) {
  if (r.rules_only) return 'rules only'
  const parts = (['unverified', 'corrected', 'suggested'] as const).map((k) => [kindCount(r.labels, k), k] as const).filter(([k]) => k)
  return parts.length ? parts.map(([k, w]) => `${k} ${w}`).join(' · ') : 'all verified'
}

function ResultsView({ sessionId, reports, sample }: { sessionId: string; reports: Report[]; sample: boolean }) {
  const n = reports.length
  const reduce = useReducedMotion()
  const [rep, setRep] = useState(0)
  const [sel, setSel] = useState<LabelName | null>(null)
  const [cite, setCite] = useState<string | null>(null)
  const [mode, setMode] = useState<Mode>(n > 1 ? 'all' : 'report')
  const [threads, setThreads] = useState<Record<string, Turn[]>>({})
  const [asking, setAsking] = useState(false)
  const [question, setQuestion] = useState('')
  const [timeline, setTimeline] = useState<TimelineRow[] | null>(null)
  const threadEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (n > 1) api.timeline(sessionId).then((r) => setTimeline(r.timeline), () => setTimeline([]))
  }, [sessionId, n])

  const cur = reports[rep]
  const shown = cur.labels.filter((l) => l.status !== 'not_mentioned').sort((a, b) => ORDER[a.status] - ORDER[b.status])
  const selected = shown.find((l) => l.label === sel) ?? shown[0]
  const highlighted = cite ? [cite] : selected?.evidence.map((e) => e.sentence_id) ?? []
  const key = mode === 'all' ? 'all' : `r${cur.report_no}`
  const thread = threads[key] ?? []

  useEffect(() => {
    if (cite) document.getElementById(`s-${cite}`)?.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' })
  }, [rep, cite, reduce])

  const pickReport = (i: number) => { setRep(i); setSel(null); setCite(null) }
  const goCite = (c: Citation) => {
    const i = reports.findIndex((r) => r.report_no === c.report_no)
    if (i < 0) return
    setRep(i)
    setSel(null)
    setCite(c.sentence_id)
  }

  async function ask(q: string) {
    q = q.trim()
    if (!q || asking) return
    const k = key
    const update = (turn: Turn) => setThreads((t) => ({ ...t, [k]: [...(t[k] ?? []).slice(0, -1), turn] }))
    setThreads((t) => ({ ...t, [k]: [...(t[k] ?? []), { q }] }))
    setQuestion('')
    setAsking(true)
    try {
      update({ q, res: await api.ask(sessionId, mode === 'all' ? { scope: 'all', question: q } : { scope: 'report', report_no: cur.report_no, question: q }) })
    } catch (e) {
      update({ q, error: (e as Error).message })
    } finally {
      setAsking(false)
      requestAnimationFrame(() => threadEnd.current?.scrollIntoView({ block: 'nearest', behavior: reduce ? 'auto' : 'smooth' }))
    }
  }

  const switchMode = (m: Mode) => { setMode(m); setCite(null) }
  const onTabKey = (e: KeyboardEvent) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return
    const m = mode === 'all' ? 'report' : 'all'
    switchMode(m)
    document.getElementById(`tab-${m}`)?.focus()
  }

  const suggestions = sample && !thread.length ? (mode === 'all' ? SAMPLE_SUGGESTIONS.all : SAMPLE_SUGGESTIONS.report(cur.report_no)) : []
  const notMentioned = cur.labels.filter((l) => l.status === 'not_mentioned').map((l) => l.label)
  const fadeIn = { initial: reduce ? false : { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.4, ease: 'easeOut' } } as const

  const picker = n > 1 && (
    <span className="lg:hidden">
      <label htmlFor="pick" className="sr-only">Report</label>
      <select id="pick" value={rep} onChange={(e) => pickReport(Number(e.target.value))}
        className="min-h-10 border border-[#C9D1D9] rounded-lg px-2.5 font-sans text-sm bg-white text-ink">
        {reports.map((r, i) => <option key={r.report_no} value={i}>Report {r.report_no} of {n}</option>)}
      </select>
    </span>
  )

  return (
    <Shell state={{ status: 'ready', sessionId, reports, sample }} picker={picker}>
      <div className="max-w-[1400px] mx-auto p-4 sm:p-6 flex flex-col lg:flex-row lg:flex-wrap gap-5 lg:items-start">
        {n > 1 && (
          <nav aria-label="Uploaded reports" className="hidden lg:flex flex-[1_1_200px] max-w-[240px] min-w-0 flex-col gap-2">
            <span className="text-xs font-semibold tracking-[0.06em] uppercase text-muted px-1">Your reports</span>
            {reports.map((r, i) => (
              <button key={r.report_no} type="button" onClick={() => pickReport(i)} aria-current={i === rep ? 'true' : undefined}
                className={`rl-hover text-left min-h-14 px-3 py-2.5 rounded-xl bg-white cursor-pointer font-sans ${i === rep ? 'border-[1.5px] border-teal' : 'border border-line'}`}>
                <span className="block text-sm font-semibold text-ink">Report {r.report_no}</span>
                <span className="block text-xs text-muted">{r.filename} · {summary(r)}</span>
              </button>
            ))}
          </nav>
        )}

        <main className="order-2 lg:order-none flex-[999_1_520px] min-w-0 flex flex-col gap-5">
          <section aria-labelledby="report-title" className={box}>
            <div className="flex justify-between items-baseline gap-3 flex-wrap mb-4">
              <h1 id="report-title" className="m-0 text-[22px]">Report {cur.report_no} <span className="text-sm font-normal text-muted">{cur.filename}</span></h1>
              <span aria-live="polite" className="text-[13px] text-muted">
                {cite ? <>Showing <strong className="text-ink">citation Report {cur.report_no} · {cite}</strong></>
                  : selected && <>Showing evidence for <strong className="text-ink">{selected.label}</strong></>}
              </span>
            </div>
            {cur.rules_only && (
              <p className="m-0 mb-4 flex gap-2.5 items-start bg-[#FFF6E5] border border-[#F0D49A] rounded-[10px] px-3.5 py-3 text-sm leading-normal text-[#4A3300]">
                <span className="mt-0.5"><Warn size={18} color="#8A5300" /></span>
                <span><strong>Rules only.</strong> The language model wasn't available for this report, so its labels come from the rule checks alone and were not checked by the verifier. Read the evidence yourself.</span>
              </p>
            )}
            {!cur.sections_identified && (
              <p className="m-0 mb-4 text-sm text-body">The report's sections couldn't be identified, so every sentence is read as Findings.</p>
            )}
            <div className="flex flex-col gap-[18px]">
              <Prose title="Indication" note="(used for questions, not for labels)" sentences={cur.sections.indication} />
              <Prose title="Comparison" sentences={cur.sections.comparison} />
              <Numbered title="Findings" sentences={cur.sections.findings} highlighted={highlighted} />
              <Numbered title="Impression" sentences={cur.sections.impression} highlighted={highlighted} />
            </div>
          </section>

          <section aria-label="Ask questions" className={`${box} flex flex-col gap-4`}>
            {n > 1 && (
              <div role="tablist" aria-label="Question scope" onKeyDown={onTabKey} className="flex gap-2 flex-wrap">
                {([['report', 'Ask about this report'], ['all', `Ask across all ${n} reports`]] as const).map(([m, text]) => (
                  <button key={m} id={`tab-${m}`} type="button" role="tab" aria-selected={mode === m} aria-controls="ask-panel" tabIndex={mode === m ? 0 : -1}
                    onClick={() => switchMode(m)}
                    className={`min-h-10 px-4 rounded-full font-semibold text-sm cursor-pointer font-sans border ${mode === m ? 'border-ink bg-ink text-white' : 'border-[#C9D1D9] bg-white text-copy hover:border-ink'}`}>
                    {text}
                  </button>
                ))}
              </div>
            )}

            <motion.div key={mode} {...fadeIn} id="ask-panel" role={n > 1 ? 'tabpanel' : undefined} aria-labelledby={n > 1 ? `tab-${mode}` : undefined} className="flex flex-col gap-3.5">
              {mode === 'all' && <Timeline rows={timeline} n={n} />}
              <div aria-live="polite" className="flex flex-col gap-3.5">
                {thread.map((t, i) => <TurnView key={i} turn={t} scope={mode} onCite={goCite} />)}
              </div>
              {suggestions.length > 0 && (
                <div className="flex flex-wrap gap-2 items-center">
                  <span className="text-[13px] text-muted">Try:</span>
                  {suggestions.map((s) => (
                    <button key={s} type="button" onClick={() => ask(s)} disabled={asking}
                      className="min-h-9 px-3 rounded-full border border-[#C9D1D9] bg-white text-copy text-[13px] cursor-pointer font-sans hover:border-teal text-left">{s}</button>
                  ))}
                </div>
              )}
              <div ref={threadEnd} />
            </motion.div>

            <form onSubmit={(e: FormEvent) => { e.preventDefault(); ask(question) }}
              className="fixed inset-x-0 bottom-0 z-20 flex gap-2 bg-white border-t border-line px-4 py-3 lg:static lg:p-0 lg:border-0 lg:bg-transparent">
              <label htmlFor="q" className="sr-only">Your question</label>
              <input id="q" type="text" value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={500} autoComplete="off"
                placeholder={mode === 'all' ? 'Ask across all reports, e.g. Which reports mention cardiomegaly?' : 'Ask about this report, e.g. Is there a pneumothorax?'}
                className="flex-1 min-w-0 min-h-12 border border-[#C9D1D9] rounded-[10px] lg:rounded-full px-3 lg:px-[18px] text-[15px] font-sans placeholder:text-[#6A7782]" />
              <button type="submit" disabled={asking} className="min-h-12 px-[18px] lg:px-[22px] rounded-[10px] lg:rounded-full border-0 bg-teal text-white font-semibold text-[15px] cursor-pointer font-sans disabled:opacity-70 disabled:cursor-wait hover:bg-[#0B5A5A]">
                {asking ? 'Asking…' : 'Ask'}
              </button>
            </form>
            <p className="m-0 text-xs text-muted">Answers cite report and sentence. Questions about diagnosis or treatment are declined.</p>
          </section>
        </main>

        <aside aria-labelledby="findings-title" className="order-1 lg:order-none flex-[1_1_340px] lg:max-w-[420px] min-w-0 flex flex-col gap-2.5">
          <div className="flex justify-between items-baseline gap-2">
            <h2 id="findings-title" className="m-0 text-lg">Findings · Report {cur.report_no}</h2>
            <span className="text-[13px] text-muted">Click to see evidence</span>
          </div>
          {shown.length === 0 && <p className="m-0 text-sm text-body">No finding is mentioned in this report.</p>}
          {shown.map((l) => (
            <LabelCard key={`${cur.report_no}-${l.label}`} label={l} selected={!cite && l === selected} fade={fadeIn}
              onPick={() => { setSel(l.label); setCite(null) }} sentences={[...cur.sections.findings, ...cur.sections.impression]} />
          ))}
          {notMentioned.length > 0 && (
            <div className="bg-white border border-line rounded-xl px-4 py-3.5">
              <span className="block text-[13px] font-semibold mb-1">Not mentioned</span>
              <span className="text-[13px] leading-normal text-muted">{notMentioned.join(' · ')}</span>
            </div>
          )}
          <details className="bg-white border border-line rounded-xl px-4 py-3 text-[13px] leading-normal text-copy">
            <summary className="font-semibold cursor-pointer min-h-7">What the badges mean</summary>
            <p className="m-0 mt-2"><strong>Verified</strong>: the checks (rules, or a second AI model with tools) found supporting sentences. <strong>Corrected</strong>: the check changed the first answer. <strong>Suggested</strong>: a finding the first pass missed. <strong>Unverified</strong>: couldn't be confirmed; read the evidence yourself. "Both sections" means Findings and Impression agree.</p>
          </details>
        </aside>
      </div>
    </Shell>
  )
}

function Prose({ title, note, sentences }: { title: string; note?: string; sentences: Sentence[] }) {
  if (!sentences.length) return null
  return (
    <div>
      <h2 className={sectionHead}>{title} {note && <span className="font-normal normal-case tracking-normal">{note}</span>}</h2>
      <p className="m-0 text-[15px] leading-relaxed text-body">{sentences.map((s) => s.text).join(' ')}</p>
    </div>
  )
}

function Numbered({ title, sentences, highlighted }: { title: string; sentences: Sentence[]; highlighted: string[] }) {
  if (!sentences.length) return null
  return (
    <div>
      <h2 className={sectionHead}>{title}</h2>
      <ol className="list-none m-0 p-0 flex flex-col gap-1">
        {sentences.map((s) => {
          const on = highlighted.includes(s.id)
          return (
            <li key={s.id} id={`s-${s.id}`} className={`flex gap-2.5 px-2.5 py-1.5 rounded-lg text-[15px] leading-[1.55] transition-colors duration-300 scroll-mt-24 ${on ? 'bg-hl text-ink font-medium' : 'text-copy'}`}>
              <span className="font-mono text-xs text-[#5F6C77] w-7 flex-none pt-[3px]">{s.id}</span>
              <span>{s.text}{on && <span className="sr-only"> (evidence)</span>}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

function LabelCard({ label: l, selected, onPick, sentences, fade }: {
  label: Label; selected: boolean; onPick: () => void; sentences: Sentence[]; fade: object
}) {
  const ids = l.evidence.map((e) => e.sentence_id)
  return (
    <motion.button {...fade} type="button" onClick={onPick} aria-pressed={selected}
      className={`rl-hover flex flex-col gap-2 text-left w-full px-4 py-3.5 rounded-xl bg-white cursor-pointer font-sans text-ink ${selected ? 'border-2 border-teal shadow-[0_2px_10px_rgba(15,110,110,0.12)]' : 'border border-line m-px'}`}>
      <span className="flex justify-between items-center gap-2 flex-wrap w-full">
        <span className="text-base font-semibold">{l.label}</span>
        <StatusPill status={l.status} />
      </span>
      <span className="flex items-center gap-2 flex-wrap">
        <Badge label={l} />
        {ids.length > 0 && <span className="font-mono text-xs text-body">Evidence: {ids.join(', ')}</span>}
      </span>
      {l.reason && <span className="text-[13px] leading-[1.45] text-body">{l.reason}</span>}
      {selected && ids.length > 0 && (
        <span className="lg:hidden flex flex-col gap-1.5 w-full">
          {sentences.filter((s) => ids.includes(s.id)).map((s) => (
            <span key={s.id} className="block bg-hl rounded-lg px-2.5 py-2 text-sm leading-normal">
              <span className="font-mono text-xs text-[#5F6C77]">{s.id}</span> {s.text}
            </span>
          ))}
        </span>
      )}
    </motion.button>
  )
}

const CELL: Record<Status, string> = {
  present: 'bg-teal text-white', uncertain: 'bg-[#FFF1C9] text-[#6B4600]', absent: 'bg-[#F1F3F5] text-[#5F6C77]', not_mentioned: 'bg-[#F1F3F5] text-[#5F6C77]',
}

function Timeline({ rows, n }: { rows: TimelineRow[] | null; n: number }) {
  const nos = Array.from({ length: n }, (_, i) => String(i + 1))
  const changing = (rows ?? []).filter((r) => r.label !== 'No Finding' && Object.values(r.statuses).some((s) => s === 'present' || s === 'uncertain'))
  return (
    <div className="relative border border-line rounded-xl px-4 py-3.5 overflow-x-auto">
      <p className="m-0 mb-2.5 text-[13px] font-semibold text-muted" id="timeline-title">Findings over time</p>
      {!rows ? <p className="m-0 text-[13px] text-muted">Loading…</p> : !changing.length ? <p className="m-0 text-[13px] text-muted">No finding is present in any report.</p> : (
        <table aria-labelledby="timeline-title" className="w-full min-w-[520px] border-separate border-spacing-1.5 -m-1.5 text-[13px] table-fixed">
          <thead>
            <tr>
              <td className="w-[140px]" />
              {nos.map((no) => <th key={no} scope="col" className="font-mono text-xs font-medium text-muted"><abbr title={`Report ${no}`} className="no-underline">R{no}</abbr></th>)}
            </tr>
          </thead>
          <tbody>
            {changing.map((r) => (
              <tr key={r.label}>
                <th scope="row" className="text-left font-semibold py-1.5">{r.label}</th>
                {nos.map((no) => {
                  const s = r.statuses[no] ?? 'not_mentioned'
                  return <td key={no} className={`text-center px-1 py-1.5 rounded-md text-xs font-semibold ${CELL[s]}`}>{s === 'not_mentioned' ? <><span aria-hidden="true">—</span><span className="sr-only">Not mentioned</span></> : STATUS_TEXT[s]}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function TurnView({ turn, scope, onCite }: { turn: Turn; scope: Mode; onCite: (c: Citation) => void }) {
  const { q, res, error } = turn
  return (
    <>
      <div className="self-end max-w-[80%] bg-[#EEF1F4] rounded-[12px_12px_4px_12px] px-3.5 py-2.5 text-[15px]">{q}</div>
      {!res && !error && <div className="text-sm text-muted">Searching your reports…</div>}
      {error && <div role="alert" className="max-w-[92%] text-sm text-[#A0300E]">{error}</div>}
      {res && (
        <div className={`max-w-[92%] rounded-[12px_12px_12px_4px] px-3.5 py-3 text-[15px] leading-relaxed border ${res.answer ? 'bg-[#F3F8F8] border-[#D3E6E6]' : 'bg-[#FAFBFC] border-line text-body'}`}>
          {res.answer ?? res.refusal}
          {res.citations.length > 0 && (
            <div className="flex gap-1.5 mt-2 flex-wrap">
              {res.citations.map((c) => (
                <button key={`${c.report_no}-${c.sentence_id}`} type="button" onClick={() => onCite(c)} className={citeBtn}
                  aria-label={`Show report ${c.report_no}, sentence ${c.sentence_id}`}>
                  {scope === 'all' ? `R${c.report_no}·${c.sentence_id}` : c.sentence_id}
                </button>
              ))}
            </div>
          )}
          {scope === 'all' && res.retrieved_sentences > 0 && (
            <p className="m-0 mt-2 text-xs text-[#5F6C77]">Retrieved {plural(res.retrieved_sentences, 'sentence')} from {plural(res.retrieved_reports, 'report')}</p>
          )}
        </div>
      )}
    </>
  )
}
