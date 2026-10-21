// Mock implementation of the API contract, serving the sample patient only.
import type { Api, AskResult, Status } from '../contract'
import { SAMPLE_ALL_ANSWERS, SAMPLE_REPORT_ANSWERS, SAMPLE_REPORTS } from './sample'

const wait = (ms: number) => new Promise((r) => setTimeout(r, import.meta.env.MODE === 'test' ? 0 : ms))

const refusal = (text: string): AskResult => ({ answer: null, refusal: text, citations: [], retrieved_sentences: 0, retrieved_reports: 0 })

export const mockApi: Api = {
  async createSession() {
    return { session_id: 'mock-session' }
  },
  async uploadReports(_id, { sample }) {
    await wait(1200)
    if (!sample) throw new Error('Mock mode only has the sample patient. Run with VITE_MOCK=false to analyze your own reports.')
    return { reports: SAMPLE_REPORTS }
  },
  async ask(_id, { scope, report_no, question }) {
    await wait(700)
    if (scope === 'all') {
      return SAMPLE_ALL_ANSWERS.find(([re]) => re.test(question))?.[1] ?? refusal('Not enough evidence in these reports to answer that.')
    }
    if (SAMPLE_ALL_ANSWERS[0][0].test(question)) return refusal('I can only answer what the report says, not give diagnosis or treatment advice.')
    const [re, , answer, ids] = SAMPLE_REPORT_ANSWERS[report_no!]
    if (!re.test(question)) return refusal('Not enough evidence in this report to answer that.')
    return { answer, refusal: null, citations: ids.map((sentence_id) => ({ report_no: report_no!, sentence_id })), retrieved_sentences: ids.length, retrieved_reports: 1 }
  },
  async timeline() {
    return {
      timeline: SAMPLE_REPORTS[0].labels.map(({ label }) => ({
        label,
        statuses: Object.fromEntries(SAMPLE_REPORTS.map((r) => [String(r.report_no), r.labels.find((l) => l.label === label)!.status])) as Record<string, Status>,
      })),
    }
  },
}
