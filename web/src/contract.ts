// API contract types (assumptions listed in web/README.md).

// Mirrors src/radlabel/labels.py, labelling/schema.py and labelling/verifier_agent.py.
export const LABELS = [
  'No Finding', 'Cardiomegaly', 'Lung Opacity', 'Lung Lesion', 'Atelectasis', 'Pleural Effusion', 'Fracture',
  'Support Devices', 'Other Abnormality', 'Edema', 'Pleural Other', 'Consolidation', 'Pneumothorax',
] as const
export type LabelName = (typeof LABELS)[number]
export type Status = 'present' | 'absent' | 'uncertain' | 'not_mentioned'
export type Verification = 'verified_rules' | 'verified' | 'verified_impression_only' | 'corrected' | 'suggested' | 'unverified'
export type Corroboration = 'both' | 'findings' | 'impression' | 'none'

export interface Sentence { id: string; text: string }
export type SectionName = 'indication' | 'comparison' | 'findings' | 'impression'
export interface Label {
  label: LabelName
  status: Status
  verification: Verification
  corroboration: Corroboration | null
  evidence: { sentence_id: string; text: string }[]
  reason: string
}
export interface Report {
  report_no: number
  filename: string
  sections: Record<SectionName, Sentence[]>
  sections_identified: boolean
  labels: Label[]
  rules_only?: boolean
}
export interface Citation { report_no: number; sentence_id: string }
export interface AskResult {
  answer: string | null
  refusal: string | null
  citations: Citation[]
  retrieved_sentences: number
  retrieved_reports: number
}
export interface TimelineRow { label: LabelName; statuses: Record<string, Status> }
export interface UploadInput { text?: string; files?: File[]; sample?: boolean }
export interface AskInput { scope: 'report' | 'all'; report_no?: number; question: string }

export interface Api {
  createSession(): Promise<{ session_id: string }>
  uploadReports(sessionId: string, input: UploadInput): Promise<{ reports: Report[] }>
  ask(sessionId: string, input: AskInput): Promise<AskResult>
  timeline(sessionId: string): Promise<{ timeline: TimelineRow[] }>
}
