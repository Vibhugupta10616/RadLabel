import { motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { MACRO_F1, MAX_FILES, NEGATED_TOP10_BASE, NEGATED_TOP10_FINETUNED, REPORTS_TESTED, SEARCH_NDCG_BASE, SEARCH_NDCG_FINETUNED, UNVERIFIED_RIGHT, VERIFIED_RIGHT } from '../numbers'
import type { LabelName, Status } from '../contract'
import { Arrow, Check, GITHUB, LogoMark, Pop, Reveal, StatusGrid, StatusPill, Up } from '../ui'

const eyebrow = 'm-0 mb-2.5 text-sm font-semibold tracking-[0.06em] uppercase text-teal'
const h2 = 'm-0 text-[32px] sm:text-[42px] tracking-[-0.025em] leading-[1.1]'
const primary = 'rl-btn inline-flex items-center gap-2.5 min-h-[54px] px-[26px] rounded-full bg-teal text-white font-semibold text-[17px] no-underline cursor-pointer border-0'
const mono = 'font-mono'

export function Landing() {
  return (
    <div className="font-sans text-ink bg-white overflow-x-clip">
      <header className="sticky top-0 z-10 bg-white/92 backdrop-blur-md border-b border-[#E8ECEF]">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between flex-wrap gap-3">
          <Link to="/" className="flex items-center gap-2.5 no-underline text-ink">
            <LogoMark />
            <span className="text-xl font-bold tracking-[-0.01em]">RadLabel</span>
          </Link>
          <nav aria-label="Main" className="flex gap-x-[22px] gap-y-2 items-center text-[15px] flex-wrap">
            <a href="#how" className="hidden sm:inline no-underline text-copy">How it works</a>
            <a href="#features" className="hidden sm:inline no-underline text-copy">Features</a>
            <a href={GITHUB} className="no-underline text-copy">GitHub</a>
            <Link to="/upload" className="rl-btn inline-flex items-center min-h-11 px-[18px] rounded-full bg-teal text-white font-semibold no-underline">Try it free</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="bg-[#F3F7F7] [background-image:radial-gradient(#D5E4E4_1px,transparent_1px)] [background-size:22px_22px] border-b border-[#E1EAEA]">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 pt-14 pb-16 sm:pt-[88px] sm:pb-24 flex flex-wrap gap-14 items-center">
            <div className="flex-[999_1_440px] min-w-0">
              <Up>
                <span className="inline-flex items-center gap-2 text-[13px] font-semibold text-teal-text bg-white border border-[#CFE2E2] rounded-full px-3 py-1.5 mb-[22px]">
                  <span className="rl-pulse w-2 h-2 rounded-full bg-teal" aria-hidden="true" />
                  For anyone who reads chest X-ray reports
                </span>
              </Up>
              <Up delay={0.1}>
                <h1 className="m-0 mb-[22px] text-[40px] sm:text-[60px] leading-[1.04] font-bold tracking-[-0.03em]">Radiology reports,<br />explained with evidence.</h1>
              </Up>
              <Up delay={0.2}>
                <p className="m-0 mb-[34px] text-lg sm:text-xl leading-[1.6] text-[#3B4954] max-w-[580px]">
                  Upload one report or a whole patient series. RadLabel finds 13 findings, shows the sentence behind each one, checks every label, and answers your questions across all your reports.
                </p>
              </Up>
              <Up delay={0.3} className="flex gap-3 flex-wrap">
                <Link to="/upload" className={primary}>Try a sample patient<Arrow /></Link>
                <a href="#how" className="rl-btn inline-flex items-center min-h-[54px] px-6 rounded-full bg-white border border-[#B8D2D2] text-teal-text font-semibold text-[17px] no-underline">See how it works</a>
              </Up>
              <Up delay={0.4}>
                <p className="m-0 mt-[18px] text-sm text-muted">Free · no sign-up · your reports are never stored</p>
              </Up>
            </div>
            <HeroVisual />
          </div>
        </section>

        <Steps />
        <Features />
        <Compare />
        <Safety />

        <section className="bg-[#F3F7F7] border-t border-[#E1EAEA]">
          <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-20 flex flex-col items-center gap-[18px] text-center">
            <Reveal as="h2" className="m-0 text-[32px] sm:text-[40px] tracking-[-0.025em]">See it on a patient series</Reveal>
            <Reveal as="p" className="m-0 text-lg leading-[1.6] text-body max-w-[560px]">Start with our sample of five follow-up reports, or paste your own with personal details removed.</Reveal>
            <Link to="/upload" className={`${primary} px-7`}>Try a sample patient<Arrow /></Link>
          </div>
        </section>
      </main>

      <footer className="bg-white border-t border-[#E8ECEF]">
        <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-[22px] flex flex-wrap justify-between gap-3 text-[13px] text-muted">
          <span>Reference data: Indiana University Chest X-ray Collection (Open-i, NLM), CC BY-NC-ND 4.0 · Not a medical device</span>
          <span>Built by Vibhu Gupta · <a href={GITHUB}>GitHub</a></span>
        </div>
      </footer>
    </div>
  )
}

const Mark = ({ delay, children }: { delay: number; children: ReactNode }) => (
  <span className="rl-mark rounded-[3px] px-0.5 py-px" style={{ animationDelay: `${delay}s` }}>{children}</span>
)

function HeroVisual() {
  return (
    <div aria-hidden="true" className="flex-[1_1_520px] min-w-0 px-2 pt-3 pb-2 flex flex-col">
      <div className="rl-float bg-white border border-[#DCE3E8] rounded-[14px] shadow-[0_24px_48px_rgba(20,32,43,0.12)] px-6 pt-6 pb-5">
        <div className="flex justify-between items-center mb-3.5">
          <span className="text-xs font-semibold tracking-[0.08em] uppercase text-muted">Chest X-ray · Report 2 of 5</span>
          <span className={`${mono} text-[11px] text-[#5F6C77]`}>PA &amp; lateral</span>
        </div>
        <p className="m-0 mb-1.5 text-[11px] font-semibold tracking-[0.08em] uppercase text-[#5F6C77]">Findings</p>
        <p className="m-0 mb-1 text-[15px] leading-[1.7] text-copy">
          <Mark delay={1.0}>The cardiac silhouette is mildly enlarged.</Mark> <Mark delay={1.6}>Moderate left pleural effusion, increased.</Mark> There is no pneumothorax.
        </p>
        <p className="m-0 mt-3 mb-1.5 text-[11px] font-semibold tracking-[0.08em] uppercase text-[#5F6C77]">Impression</p>
        <p className="m-0 text-[15px] leading-[1.7] text-copy">Mild cardiomegaly. Increased left pleural effusion.</p>
      </div>

      {/* Below the report card (gap, no overlap); the two cards wrap under each other on narrow screens. */}
      <div className="relative z-[2] mt-4 px-1 flex flex-wrap gap-3 items-stretch">
        <Pop delay={3.0} className="flex-[1.15_1_220px] min-w-0 bg-teal-dark text-white rounded-[14px] shadow-[0_16px_32px_rgba(15,61,61,0.28)] px-4 py-3.5">
          <p className="m-0 mb-1.5 text-[13px] text-[#A9CACA]">Across 5 reports</p>
          <p className="m-0 mb-2 text-[15px] font-semibold">How did the effusion change?</p>
          <p className="rl-type m-0 text-sm leading-[1.55] text-[#E3F0F0]" style={{ animationDelay: '3.4s' }}>Small → moderate → stable → smaller → resolved by report 5.</p>
          <p className={`${mono} m-0 mt-2 text-[11px] leading-[1.5] text-[#8FC3C3]`}>R1·F2 · R2·F2 · R3·F2 · R4·F2 · R5·F3</p>
        </Pop>
        <Pop delay={2.2} className="flex-[1_1_220px] min-w-0 bg-white border border-[#CFE2E2] rounded-xl shadow-[0_14px_30px_rgba(20,32,43,0.12)] px-3.5 py-3 flex flex-col gap-2 text-ink">
          {([['Cardiomegaly', 'present'], ['Pleural Effusion', 'present'], ['Pneumothorax', 'absent']] as const).map(([name, s]) => (
            <div key={name} className="flex justify-between gap-3 items-center"><span className="text-sm font-semibold">{name}</span><StatusPill status={s} small /></div>
          ))}
          <span className="self-start inline-flex items-center gap-[5px] text-[11px] font-semibold px-2 py-[3px] rounded-md text-[#0B5C55] bg-[#E1F2EF]"><Check size={12} width={2.8} />All verified</span>
        </Pop>
      </div>
    </div>
  )
}

const chip = 'text-xs px-[9px] py-[5px] rounded-lg bg-white border border-[#DCE3E8]'
const row = 'flex justify-between text-[13px] bg-white border border-[#DCE3E8] rounded-lg px-2.5 py-1.5'

const STEPS: [string, ReactNode, string, string][] = [
  ['01 · Upload', <div className="flex flex-wrap gap-1.5 content-start">{['exam_1.txt', 'exam_2.txt', 'exam_3.pdf', 'exam_4.txt', 'exam_5.txt'].map((f) => <span key={f} className={chip}>{f}</span>)}</div>,
    'Drop in your reports', `Paste text or upload up to ${MAX_FILES} files. Sections and sentences are recognised automatically.`],
  ['02 · Label', <div className="flex flex-col gap-1.5">
    <div className={row}><span>Pleural Effusion</span><strong>Present</strong></div>
    <div className={row}><span>Atelectasis</span><strong className="text-[#6B4600]">Uncertain</strong></div>
  </div>, '13 findings per report', 'A language model reads Findings and Impression and marks each finding present, uncertain, absent or not mentioned.'],
  ['03 · Check', <div className="flex flex-col gap-1.5">
    <div className={`${row} justify-start! items-center gap-1.5 flex-wrap`}><span>Atelectasis</span><span className="line-through text-[#5F6C77]">present</span><span>→ uncertain</span></div>
    <span className="self-start text-xs font-semibold px-[9px] py-[3px] rounded-md text-[#1D4E89] bg-[#E4ECF7]">Corrected: "possibly"</span>
  </div>, 'Every label double-checked', 'Rule checks run on everything. Doubtful labels go to a verifier agent that searches the report and decides.'],
  ['04 · Ask', <div className="flex flex-col gap-1.5">
    <div className="self-end text-[13px] bg-[#E9EEF1] rounded-[10px_10px_3px_10px] px-2.5 py-1.5">When was the pacemaker placed?</div>
    <div className="text-[13px] bg-white border border-[#CFE2E2] rounded-[10px_10px_10px_3px] px-2.5 py-1.5">First seen in report 3 <span className={`${mono} text-teal-text`}>R3·F1</span></div>
  </div>, 'Ask across all reports', 'Your reports are searched for this visit only. Answers cite the exact report and sentence.'],
]

function Steps() {
  return (
    <section id="how" className="bg-white scroll-mt-20">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <Reveal as="p" className={eyebrow}>How it works</Reveal>
        <Reveal as="h2" className={`${h2} mb-3.5`}>A real example, in four steps</Reveal>
        <Reveal as="p" className="m-0 mb-12 text-lg leading-[1.6] text-body max-w-[640px]">One patient, five follow-up X-ray reports. Here is what happens when you upload them.</Reveal>
        <ol className="list-none m-0 p-0 grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-5">
          {STEPS.map(([tag, demo, title, text]) => (
            <Reveal as="li" key={tag} className="rl-card bg-[#F7F9FA] border border-[#E5EAEE] rounded-[18px] p-[22px] flex flex-col gap-3.5">
              <span className={`${mono} text-[13px] text-teal`}>{tag}</span>
              <div aria-hidden="true" className="min-h-[76px]">{demo}</div>
              <h3 className="m-0 text-[19px]">{title}</h3>
              <p className="m-0 text-[15px] leading-[1.6] text-body">{text}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  )
}

const featureCard = 'rl-card flex-[1_1_420px] min-w-0 bg-white border border-[#E1E6EA] rounded-[18px] p-6 flex flex-col'
const featureH3 = 'm-0 mb-3 text-2xl sm:text-[28px] tracking-[-0.015em]'
const featureP = 'm-0 text-[17px] leading-[1.65] text-body'

function Bar({ pct, color, delay = 0 }: { pct: number; color: string; delay?: number }) {
  const reduce = useReducedMotion()
  return (
    <motion.div className="h-full rounded-full origin-left" style={{ width: `${pct}%`, background: color }}
      initial={reduce ? false : { scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
      transition={{ duration: 1.2, delay, ease: [0.2, 0.7, 0.2, 1] }} />
  )
}

// The sample patient's statuses (status, not severity: RadLabel doesn't extract severity).
const grid = (label: LabelName, s: Status[]) => ({ label, statuses: Object.fromEntries(s.map((x, i) => [String(i + 1), x])) })
const SAMPLE_GRID = [
  grid('Pleural Effusion', ['present', 'present', 'present', 'present', 'absent']),
  grid('Cardiomegaly', ['absent', 'present', 'present', 'present', 'present']),
  grid('Support Devices', ['not_mentioned', 'not_mentioned', 'present', 'present', 'present']),
]

function Features() {
  const sentences: [string, string, boolean][] = [['F1', 'Heart size is normal.', false], ['F2', 'Small left pleural effusion.', true], ['F3', 'No pneumothorax.', false], ['I1', 'Small left pleural effusion.', true]]
  return (
    <section id="features" className="bg-[#F6F8F9] border-t border-[#E8ECEF] scroll-mt-20">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-16 sm:py-24 flex flex-col gap-16 sm:gap-[88px]">
        <div>
          <Reveal as="p" className={eyebrow}>What RadLabel does for you</Reveal>
          <Reveal as="h2" className={`${h2} max-w-[720px]`}>Structure, proof and answers, from plain report text</Reveal>
        </div>

        <div className="flex flex-wrap gap-12 items-center">
          <Reveal className="flex-[1_1_380px] min-w-0">
            <h3 className={featureH3}>See the sentence behind every finding</h3>
            <p className={featureP}>Click a finding and the sentences that support it light up in the report. Evidence is matched against the original text in code, so it can't be invented.</p>
          </Reveal>
          <Reveal className={`${featureCard} gap-2.5`}>
            <div aria-hidden="true" className="flex flex-col gap-2.5">
              {sentences.map(([id, text, hl]) => (
                <div key={id} className={`flex gap-2.5 px-3 py-2 rounded-lg text-[15px] ${hl ? 'bg-hl font-medium' : 'text-body'}`}>
                  <span className={`${mono} text-xs text-[#5F6C77] pt-0.5`}>{id}</span>{text}
                </div>
              ))}
              <div className="self-end flex items-center gap-2 mt-1.5 border-2 border-teal rounded-[10px] px-3 py-2">
                <span className="text-sm font-semibold">Pleural Effusion</span>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md text-[#0B5C55] bg-[#E1F2EF]">Verified · F2, I1</span>
              </div>
            </div>
          </Reveal>
        </div>

        <div className="flex flex-wrap-reverse gap-12 items-center">
          <Reveal className={`${featureCard} gap-4`}>
            <div className="flex flex-wrap gap-2" aria-hidden="true">
              <span className="text-xs font-semibold px-2.5 py-1 rounded-md text-[#0B5C55] bg-[#E1F2EF]">Verified</span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-md text-[#1D4E89] bg-[#E4ECF7]">Corrected</span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-md text-[#4E3590] bg-[#EEE8F8]">Suggested</span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-md text-[#8A4300] bg-[#FCEBD9]">Unverified</span>
            </div>
            {([['Verified labels right', VERIFIED_RIGHT, '#0F6E6E', 0], ['Unverified labels right', UNVERIFIED_RIGHT, '#C36A10', 0.2]] as const).map(([name, pct, color, delay]) => (
              <div key={name} className="flex flex-col gap-1.5">
                <div className="flex justify-between text-sm"><span>{name}</span><strong>{pct}%</strong></div>
                <div className="h-2.5 rounded-full bg-[#EDF1F3] overflow-hidden"><Bar pct={pct} color={color} delay={delay} /></div>
              </div>
            ))}
          </Reveal>
          <Reveal className="flex-[1_1_380px] min-w-0">
            <h3 className={featureH3}>Know which labels to trust</h3>
            <p className={featureP}>Every label carries a badge. In testing, verified labels were right {VERIFIED_RIGHT}% of the time and unverified ones only {UNVERIFIED_RIGHT}%, so you know exactly where to look twice.</p>
          </Reveal>
        </div>

        <div className="flex flex-wrap gap-12 items-center">
          <Reveal className="flex-[1_1_380px] min-w-0">
            <span className="inline-block text-xs font-semibold px-2.5 py-1 rounded-full bg-teal-dark text-white mb-3.5">Retrieval-augmented Q&amp;A</span>
            <h3 className={featureH3}>Ask across a whole patient series</h3>
            <p className={featureP}>Upload a patient's follow-up reports and ask how things changed. RadLabel builds a search index for your visit only, retrieves the relevant sentences from every report, and answers with citations. The index is deleted when you leave.</p>
            <p className={`${featureP} mt-3`}>The search model is fine-tuned to tell "effusion" from "no effusion": in testing, results that only mention a finding as absent fell from {NEGATED_TOP10_BASE}% to {NEGATED_TOP10_FINETUNED}% of the top 10, and ranking quality (nDCG@10) rose from {SEARCH_NDCG_BASE} to {SEARCH_NDCG_FINETUNED}.</p>
          </Reveal>
          <Reveal className={`${featureCard} gap-4`}>
            <div aria-hidden="true" className="flex flex-col gap-4">
              <p className="m-0 text-[13px] font-semibold text-muted">Findings over time</p>
              <StatusGrid rows={SAMPLE_GRID} n={5} />
              <div className="bg-[#F3F8F8] border border-[#D3E6E6] rounded-xl px-3.5 py-3 text-sm leading-[1.6]">
                Small in report 1, moderate in reports 2 and 3, smaller in report 4, and resolved by report 5.
                <div className={`${mono} mt-1.5 text-xs text-teal-text`}>R1·F2 · R2·F2 · R3·F2 · R4·F2 · R5·F3</div>
              </div>
              <p className="m-0 text-xs text-[#5F6C77]">Retrieved 6 sentences from 5 reports</p>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

const COMPARE: [string, string, string][] = [
  ['Points to the exact sentence', 'Sometimes', 'Always, checked in code'],
  ['Second check on every label', 'No', 'Rule checks + verifier agent'],
  ['Accuracy measured against experts', 'Not for this task', `${MACRO_F1} macro-F1, ${REPORTS_TESTED} reports`],
  ["Says when it isn't sure", 'Rarely', '"Unverified" badge'],
  ['Keeps your reports', 'Depends on the service', 'Never stored'],
]

function Compare() {
  return (
    <section className="bg-white">
      <div className="max-w-[960px] mx-auto px-4 sm:px-6 py-16 sm:py-24">
        <Reveal as="h2" className="m-0 mb-3 text-[30px] sm:text-[38px] tracking-[-0.02em] leading-[1.15]">Why not just paste it into a chatbot?</Reveal>
        <Reveal as="p" className="m-0 mb-9 text-[17px] leading-[1.6] text-body">General chatbots are great at conversation. RadLabel is built for one job and measured on it.</Reveal>
        <Reveal className="overflow-x-auto border border-[#E1E6EA] rounded-2xl">
          <table className="w-full border-collapse text-[15px] min-w-[560px]">
            <thead>
              <tr className="bg-[#F6F8F9] text-left">
                <td className="px-[18px] py-3.5" />
                <th scope="col" className="px-[18px] py-3.5 font-semibold text-muted">General chatbot</th>
                <th scope="col" className="px-[18px] py-3.5 font-bold text-teal-text">RadLabel</th>
              </tr>
            </thead>
            <tbody>
              {COMPARE.map(([q, bot, us]) => (
                <tr key={q} className="border-t border-[#E8ECEF]">
                  <th scope="row" className="px-[18px] py-3.5 text-left font-medium">{q}</th>
                  <td className="px-[18px] py-3.5 text-muted">{bot}</td>
                  <td className="px-[18px] py-3.5 font-semibold">{us}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Reveal>
      </div>
    </section>
  )
}

const SAFETY: [string, string][] = [
  ['Never stored.', 'Reports are processed in memory and forgotten when you leave.'],
  ['You redact.', 'Remove names, dates of birth and record numbers before uploading.'],
  ['Not a medical device.', 'For research and demonstration only.'],
  ['Text, not images.', 'Labels describe what the report says, not the X-ray itself.'],
  ['"Verified" = faithful to the text,', 'not clinically confirmed.'],
  ['Tested on one dataset', '(Indiana University, ~2013). Other hospitals write differently.'],
]

function Safety() {
  return (
    <section className="on-dark bg-teal-dark text-white">
      <div className="max-w-[1200px] mx-auto px-4 sm:px-6 py-16 sm:py-[88px] flex flex-wrap gap-12">
        <Reveal className="flex-[1_1_340px] min-w-0">
          <h2 className="m-0 mb-3.5 text-[30px] sm:text-[38px] tracking-[-0.02em] leading-[1.15]">Safe, private and honest by design</h2>
          <p className="m-0 mb-5 text-[17px] leading-[1.6] text-[#C7DCDC]">What happens to your reports, and what the results do and don't mean.</p>
          <a href={GITHUB} className="text-[#9FE0D8] font-semibold hover:text-white">Full evaluation and limitations on GitHub →</a>
        </Reveal>
        <ul className="flex-[2_1_520px] min-w-0 list-none m-0 p-0 grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-[18px]">
          {SAFETY.map(([strong, rest]) => (
            <Reveal as="li" key={strong} className="flex gap-3 text-[15px] leading-[1.55] text-[#E3F0F0]">
              <span className="flex-none mt-px text-[#9FE0D8]"><Check size={22} width={2.2} /></span>
              <span><strong className="text-white">{strong}</strong> {rest}</span>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  )
}
