import { useState, type DragEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MACRO_F1, MAX_FILES, REPORTS_TESTED, UNVERIFIED_RIGHT, VERIFIED_RIGHT } from '../numbers'
import { SAMPLE_FILES } from '../sample'
import { useSession } from '../session'
import { GITHUB, LogoMark, Warn } from '../ui'

const ACCEPTED = /\.(txt|pdf)$/i
const card = 'bg-white border border-line rounded-[14px] p-6'

export function Upload() {
  const { start } = useSession()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [confirmed, setConfirmed] = useState(false)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [sample, setSample] = useState(false) // the built-in sample patient is loaded in the list
  const [shown, setShown] = useState<number | null>(null) // sample card whose text is open

  function addFiles(list: FileList | null) {
    setSample(false) // your own files replace the sample
    const picked = Array.from(list ?? [])
    const ok = picked.filter((f) => ACCEPTED.test(f.name))
    const all = [...files, ...ok.filter((f) => !files.some((x) => x.name === f.name && x.size === f.size))]
    setFiles(all.slice(0, MAX_FILES))
    setError(ok.length < picked.length ? 'Only .txt and .pdf files can be added.'
      : all.length > MAX_FILES ? `Up to ${MAX_FILES} reports at a time; the rest were left out.` : '')
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (sample) { // made-up reports: no confirmation needed; the outputs are precomputed
      start({ sample: true })
      return navigate('/results')
    }
    if (!text.trim() && !files.length) return setError('Paste a report or add at least one file.')
    if (!confirmed) return setError('Please confirm the reports contain no information that identifies a person.')
    start({ text: text.trim() || undefined, files })
    navigate('/results')
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  return (
    <div className="min-h-screen font-sans text-ink bg-page flex flex-col">
      <header className="bg-white border-b border-line">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-6 py-4 flex items-center justify-between flex-wrap gap-3">
          <Link to="/" className="flex items-center gap-2.5 text-xl font-bold tracking-[-0.01em] text-ink no-underline"><LogoMark />RadLabel</Link>
          <nav aria-label="Main" className="flex gap-6 text-[15px] flex-wrap">
            <a href="#how">How it works</a>
            <a href="#results">Results &amp; limits</a>
            <a href={GITHUB}>GitHub</a>
          </nav>
        </div>
      </header>

      <main className="flex-1 w-full max-w-[1120px] mx-auto px-4 sm:px-6 pt-10 sm:pt-12 pb-8">
        <h1 className="m-0 mb-3 text-[30px] sm:text-[40px] leading-[1.15] font-bold tracking-[-0.02em] max-w-[760px]">Turn chest X-ray reports into verified findings</h1>
        <p className="m-0 mb-8 text-lg leading-[1.55] text-body max-w-[720px]">Upload one or more radiology reports. RadLabel tags 13 findings, shows the sentence behind every label, checks each one, and answers your questions with citations.</p>

        <div className="flex flex-wrap gap-6 items-stretch">
          <form onSubmit={submit} noValidate className={`${card} flex-[999_1_560px] min-w-0 flex flex-col gap-4`}>
            <label htmlFor="report" className="text-[15px] font-semibold">Paste a report</label>
            <textarea id="report" value={text} onChange={(e) => { setText(e.target.value); setSample(false) }} placeholder={'INDICATION: ...\nFINDINGS: ...\nIMPRESSION: ...'}
              className="h-[200px] resize-y border border-[#C9D1D9] rounded-[10px] p-3.5 font-mono text-sm leading-normal text-ink placeholder:text-[#6A7782]" />

            <div className="flex items-center gap-3 text-[#5F6C77] text-sm" aria-hidden="true"><span className="flex-1 h-px bg-line" />or<span className="flex-1 h-px bg-line" /></div>

            <label htmlFor="files" onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
              className={`relative border-2 border-dashed rounded-xl p-6 flex flex-col items-center gap-1.5 text-center cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-teal has-[:focus-visible]:outline-offset-2 ${dragging ? 'border-teal bg-[#EEF6F6]' : 'border-[#B9C4CE] bg-[#FAFBFC]'}`}>
              <svg width="28" height="28" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="#0F6E6E" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" /></svg>
              <span className="text-[15px] font-semibold">Drop files here or browse</span>
              <span className="text-[13px] text-muted">.txt or .pdf with selectable text · up to {MAX_FILES} reports</span>
              <input id="files" type="file" multiple accept=".txt,.pdf" className="sr-only" onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
            </label>

            {sample && (
              <section aria-label="Sample patient" className="flex flex-col gap-3 bg-[#F3F8F8] border border-[#D3E6E6] rounded-xl p-4">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <p className="m-0 text-sm font-semibold text-teal-text">Made-up reports for demonstration <span className="font-normal text-muted">· 5 follow-up reports of one fictional patient</span></p>
                  <button type="button" onClick={() => { setSample(false); setShown(null) }} className="min-h-8 px-2.5 rounded-lg bg-white border border-line text-[13px] text-muted cursor-pointer hover:text-ink">Remove sample</button>
                </div>
                <ul aria-label="Sample files" className="list-none m-0 p-0 flex flex-wrap gap-2">
                  {SAMPLE_FILES.map((f, k) => (
                    <li key={f.name}>
                      <button type="button" aria-pressed={shown === k} onClick={() => setShown(shown === k ? null : k)}
                        className={`min-h-9 px-3 rounded-lg border text-[13px] cursor-pointer ${shown === k ? 'bg-teal text-white border-teal' : 'bg-white text-ink border-line hover:border-teal'}`}>{f.name}</button>
                    </li>
                  ))}
                </ul>
                {shown !== null && <pre aria-label={`Text of ${SAMPLE_FILES[shown].name}`} className="m-0 p-3 bg-white border border-line rounded-lg font-mono text-[13px] leading-normal text-ink whitespace-pre-wrap">{SAMPLE_FILES[shown].text}</pre>}
              </section>
            )}

            {files.length > 0 && (
              <ul aria-label="Added files" className="list-none m-0 p-0 flex flex-wrap gap-2">
                {files.map((f) => (
                  <li key={f.name + f.size} className="inline-flex items-center gap-1 text-[13px] bg-[#F6F7F9] border border-line rounded-lg pl-2.5">
                    {f.name}
                    <button type="button" onClick={() => setFiles(files.filter((x) => x !== f))} aria-label={`Remove ${f.name}`}
                      className="min-w-8 min-h-8 bg-transparent border-0 cursor-pointer text-muted text-base hover:text-ink">×</button>
                  </li>
                ))}
              </ul>
            )}

            <div className="flex gap-3 items-start bg-[#FFF6E5] border border-[#F0D49A] rounded-[10px] px-4 py-3.5">
              <span className="mt-0.5"><Warn size={20} color="#8A5300" /></span>
              <p className="m-0 text-sm leading-normal text-[#4A3300]">
                <strong>Don't paste original reports with personal details.</strong> Remove names, dates of birth, record numbers and anything else that identifies a person before uploading. Redaction is your responsibility. Reports are processed in memory, sent to Azure OpenAI for analysis, and never stored.
              </p>
            </div>

            <label className="flex gap-2.5 items-start text-sm leading-normal cursor-pointer">
              <input type="checkbox" required checked={confirmed} onChange={(e) => { setConfirmed(e.target.checked); setError('') }} className="w-[18px] h-[18px] mt-0.5 flex-none accent-teal" />
              <span>I confirm these reports contain no information that identifies a person.{sample && <span className="text-muted"> (Not needed for the sample.)</span>}</span>
            </label>

            <p role="alert" className={`m-0 text-sm font-medium text-[#A0300E] ${error ? '' : 'hidden'}`}>{error}</p>

            <div className="flex gap-3 flex-wrap">
              <button type="submit" className="inline-flex items-center justify-center min-h-12 px-6 rounded-[10px] bg-teal hover:bg-[#0B5A5A] text-white font-semibold text-base border-0 cursor-pointer">Analyze reports</button>
              <button type="button" onClick={() => { setSample(true); setShown(null); setText(''); setFiles([]); setError('') }}
                className="inline-flex items-center justify-center min-h-12 px-5 rounded-[10px] bg-white text-teal-text border border-[#9FC2C2] hover:border-teal font-semibold text-base cursor-pointer">Load sample patient (5 reports)</button>
            </div>
          </form>

          <aside id="how" className="flex-[1_1_300px] min-w-0 flex flex-col gap-4">
            <div className={card}>
              <h2 className="m-0 mb-4 text-lg">What you get</h2>
              <ol className="list-decimal m-0 pl-5 flex flex-col gap-3 text-[15px] leading-normal text-copy">
                <li><strong>13 findings</strong> per report: present, uncertain, absent or not mentioned.</li>
                <li><strong>Evidence</strong>: click a finding to see the sentences behind it.</li>
                <li><strong>A check on every label</strong>: verified, corrected, suggested or unverified.</li>
                <li><strong>Questions</strong> about one report, or across all your reports at once, answered with citations.</li>
              </ol>
            </div>
            <div id="results" className={card}>
              <h2 className="m-0 mb-3 text-lg">Measured on {REPORTS_TESTED} reports</h2>
              <p className="m-0 mb-2 text-[15px] leading-normal text-copy">Macro-F1 <strong>{MACRO_F1}</strong> against expert codes. Verified labels were right <strong>{VERIFIED_RIGHT}%</strong> of the time, unverified ones <strong>{UNVERIFIED_RIGHT}%</strong>.</p>
              <p className="m-0 text-[13px] leading-normal text-muted">One dataset (Indiana University, ~2013). Labels describe the report text, not the image.</p>
            </div>
          </aside>
        </div>
      </main>

      <footer className="border-t border-line bg-white">
        <div className="max-w-[1120px] mx-auto px-4 sm:px-6 py-[18px] flex flex-wrap justify-between gap-3 text-[13px] text-muted">
          <span><strong className="text-[#8A2C0D]">Not a medical device.</strong> For research and demonstration only.</span>
          <span>Reference data: Indiana University Chest X-ray Collection (Open-i, NLM), CC BY-NC-ND 4.0 · Built by Vibhu Gupta · <a href={GITHUB}>GitHub</a></span>
        </div>
      </footer>
    </div>
  )
}
