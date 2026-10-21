// The made-up 5-report sample patient (web/design/Results.dc.html), in the API contract's shape.
// Effusion small → moderate → moderate → small → resolved; mild cardiomegaly from report 2, borderline in 5;
// pacemaker new in report 3.
import { LABELS, type AskResult, type Corroboration, type Label, type LabelName, type Report, type Sentence, type Status, type Verification } from '../contract'

const sents = (prefix: string, texts: string[]): Sentence[] => texts.map((text, i) => ({ id: `${prefix}${i + 1}`, text }))

type Spec = [LabelName, Status, Verification, Corroboration | null, string[], string?]

function report(no: number, filename: string, s: { indication: string; comparison?: string; findings: string[]; impression: string[] }, specs: Spec[]): Report {
  const sections = {
    indication: sents('N', [s.indication]),
    comparison: sents('C', s.comparison ? [s.comparison] : []),
    findings: sents('F', s.findings),
    impression: sents('I', s.impression),
  }
  const byId = new Map([...sections.findings, ...sections.impression].map((x) => [x.id, x.text]))
  const labels: Label[] = LABELS.map((label) => {
    const spec = specs.find((x) => x[0] === label)
    if (!spec) return { label, status: 'not_mentioned', verification: 'verified_rules', corroboration: null, evidence: [], reason: '' }
    const [, status, verification, corroboration, ids, reason = ''] = spec
    return { label, status, verification, corroboration, evidence: ids.map((id) => ({ sentence_id: id, text: byId.get(id)! })), reason }
  })
  return { report_no: no, filename, sections, sections_identified: true, labels }
}

export const SAMPLE_REPORTS: Report[] = [
  report(1, 'exam_1.txt', {
    indication: 'Shortness of breath.',
    findings: ['Heart size is normal.', 'Small left pleural effusion.', 'No pneumothorax.', 'The lungs are otherwise clear.'],
    impression: ['Small left pleural effusion.'],
  }, [
    ['Pleural Effusion', 'present', 'verified_rules', 'both', ['F2', 'I1']],
    ['Cardiomegaly', 'absent', 'verified_rules', null, ['F1']],
    ['Pneumothorax', 'absent', 'verified_rules', null, ['F3']],
  ]),
  report(2, 'exam_2.txt', {
    indication: 'Worsening shortness of breath.',
    comparison: 'Prior chest radiograph (report 1).',
    findings: ['The cardiac silhouette is mildly enlarged.', 'Moderate left pleural effusion, increased from the prior study.', 'Patchy left basilar opacity, possibly atelectasis.', 'No pneumothorax.'],
    impression: ['Mild cardiomegaly.', 'Increased moderate left pleural effusion.', 'Left basilar opacity, likely atelectasis.'],
  }, [
    ['Cardiomegaly', 'present', 'verified_rules', 'both', ['F1', 'I1']],
    ['Pleural Effusion', 'present', 'verified_rules', 'both', ['F2', 'I2']],
    ['Lung Opacity', 'present', 'suggested', 'both', ['F3', 'I3'], 'The first pass missed this; the check found it in two sentences.'],
    ['Atelectasis', 'uncertain', 'corrected', null, ['F3', 'I3'], 'Changed from present: the report hedges ("possibly", "likely").'],
    ['Pneumothorax', 'absent', 'verified_rules', null, ['F4']],
  ]),
  report(3, 'exam_3.pdf', {
    indication: 'Pacemaker placement.',
    comparison: 'Prior chest radiograph (report 2).',
    findings: ['A left chest wall pacemaker is present with leads in expected position.', 'Moderate left pleural effusion, unchanged.', 'The heart remains mildly enlarged.', 'No pneumothorax.'],
    impression: ['New pacemaker in expected position.', 'Stable moderate left pleural effusion.', 'Infection at the left base cannot be excluded.'],
  }, [
    ['Support Devices', 'present', 'verified_rules', 'both', ['F1', 'I1']],
    ['Pleural Effusion', 'present', 'verified_rules', 'both', ['F2', 'I2']],
    ['Cardiomegaly', 'present', 'verified', 'findings', ['F3']],
    ['Consolidation', 'uncertain', 'unverified', null, ['I3'], 'Possible infection is mentioned, but no sentence names consolidation. Check it yourself.'],
    ['Pneumothorax', 'absent', 'verified_rules', null, ['F4']],
  ]),
  report(4, 'exam_4.txt', {
    indication: 'Follow-up.',
    comparison: 'Prior chest radiograph (report 3).',
    findings: ['Pacemaker leads unchanged.', 'Small left pleural effusion, decreased.', 'Heart size mildly enlarged, stable.', 'No pneumothorax.'],
    impression: ['Decreasing small left pleural effusion.', 'Stable mild cardiomegaly.'],
  }, [
    ['Support Devices', 'present', 'verified_rules', 'findings', ['F1']],
    ['Pleural Effusion', 'present', 'verified_rules', 'both', ['F2', 'I1']],
    ['Cardiomegaly', 'present', 'verified_rules', 'both', ['F3', 'I2']],
    ['Pneumothorax', 'absent', 'verified_rules', null, ['F4']],
  ]),
  report(5, 'exam_5.txt', {
    indication: 'Follow-up.',
    comparison: 'Prior chest radiograph (report 4).',
    findings: ['Pacemaker in place.', 'Heart size is borderline.', 'No pleural effusion.', 'The lungs are clear.'],
    impression: ['Resolved left pleural effusion.', 'No acute cardiopulmonary abnormality.'],
  }, [
    ['Support Devices', 'present', 'verified_rules', 'findings', ['F1']],
    ['Cardiomegaly', 'present', 'verified_rules', 'findings', ['F2'], 'Borderline enlargement counts as present by the label definition.'],
    ['Pleural Effusion', 'absent', 'verified_rules', null, ['F3', 'I1']],
  ]),
]

// One pasted report labelled by the rule checks alone (LLM unavailable, e.g. the cost cap): the "rules only" state.
export const RULES_ONLY_REPORT: Report = {
  ...report(1, 'Pasted report', {
    indication: 'Cough.',
    findings: ['Heart size is normal.', 'Small right pleural effusion.', 'No pneumothorax.'],
    impression: ['Small right pleural effusion.'],
  }, [
    ['Pleural Effusion', 'present', 'unverified', null, ['F2', 'I1']],
    ['Cardiomegaly', 'absent', 'unverified', null, ['F1']],
    ['Pneumothorax', 'absent', 'unverified', null, ['F3']],
  ]),
  rules_only: true,
}

const ok = (answer: string, cites: [number, string][], sentences: number, reports: number): AskResult => ({
  answer, refusal: null, citations: cites.map(([report_no, sentence_id]) => ({ report_no, sentence_id })),
  retrieved_sentences: sentences, retrieved_reports: reports,
})

// Canned answers for scope "all": [keywords, result]. The first match wins.
export const SAMPLE_ALL_ANSWERS: [RegExp, AskResult][] = [
  [/antibiotic|treat|medic|diagnos|should/i, {
    answer: null, refusal: 'I can only answer what the reports say, not give treatment advice. Report 3 notes that infection at the left base cannot be excluded.',
    citations: [{ report_no: 3, sentence_id: 'I3' }], retrieved_sentences: 1, retrieved_reports: 1,
  }],
  [/effusion/i, ok('It was small in report 1, increased to moderate in report 2, stayed moderate in report 3, decreased in report 4, and had resolved by report 5.',
    [[1, 'F2'], [2, 'F2'], [3, 'F2'], [4, 'F2'], [5, 'F3']], 6, 5)],
  [/pacemaker|device|lead/i, ok("In report 3, as a new pacemaker with leads in expected position. Reports 1 and 2 don't mention one.",
    [[3, 'F1'], [3, 'I1']], 4, 3)],
  [/cardiomegaly|heart|cardiac/i, ok('Reports 2, 3 and 4 describe a mildly enlarged heart and report 5 calls it borderline. Report 1 describes a normal heart size.',
    [[1, 'F1'], [2, 'F1'], [3, 'F3'], [4, 'F3'], [5, 'F2']], 7, 5)],
]

// Canned answers for scope "report", one per report (design copy).
export const SAMPLE_REPORT_ANSWERS: Record<number, [RegExp, string, string, string[]]> = {
  1: [/pneumothorax/i, 'Is there a pneumothorax?', 'No. The report states there is no pneumothorax.', ['F3']],
  2: [/cardiomegaly|heart/i, 'What supports cardiomegaly?', 'The heart is described as mildly enlarged, and the impression states mild cardiomegaly.', ['F1', 'I1']],
  3: [/pacemaker|lead/i, 'Is the pacemaker in the right place?', 'The report describes the leads in expected position.', ['F1', 'I1']],
  4: [/effusion/i, 'Is the effusion getting better?', 'The report describes it as small and decreased.', ['F2', 'I1']],
  5: [/effusion/i, 'Is there still an effusion?', 'No. There is no pleural effusion, and the impression calls it resolved.', ['F3', 'I1']],
}

export const SAMPLE_SUGGESTIONS = {
  all: ['How did the pleural effusion change across the reports?', 'When was the pacemaker first described?', 'Should the patient start antibiotics?'],
  report: (no: number) => [SAMPLE_REPORT_ANSWERS[no][1]],
}
