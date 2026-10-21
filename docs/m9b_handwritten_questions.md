# M9b hand-written questions (fixed before any M9b results)

20 questions written in generic form so they apply to any report or batch. Each has
the label it maps to and how the expected answer is derived from the expert codes
(v1 mapping, `present` = positive), so they can be scored automatically.

Scope "report" = asked about one report. Scope "all" = asked across a batch.
For unanswerable questions, the correct behaviour is a refusal or "not stated", with
no invented facts.

## A. Single report, answerable (6)

| # | Question | Label | Expected answer |
|---|---|---|---|
| 1 | Is the heart enlarged? | Cardiomegaly | yes if Cardiomegaly is coded, otherwise no / not stated |
| 2 | Is there fluid around the lungs? | Pleural Effusion | yes if coded, otherwise no / not stated (lay wording on purpose) |
| 3 | Does the patient have any tubes, lines or devices in place? | Support Devices | yes if coded, otherwise no / not stated |
| 4 | Is there any air outside the lung, a pneumothorax? | Pneumothorax | yes if coded, otherwise no / not stated |
| 5 | Are any broken bones described? | Fracture | yes if coded, otherwise no / not stated |
| 6 | Is the report completely normal? | No Finding | yes only if the report is coded normal-only, otherwise no |

## B. Single report, tricky wording (4)

| # | Question | Label | Expected answer |
|---|---|---|---|
| 7 | Is there any sign of pulmonary edema? | Edema | yes if coded; on reports that only negate edema ("no edema") the answer must be no |
| 8 | Is a lung nodule or mass definitely present? | Lung Lesion | yes if coded; if the report only hedges ("possible nodule"), the answer must say it is uncertain, not yes |
| 9 | Does the report state that there is no pleural effusion? | Pleural Effusion | yes only if an effusion is explicitly negated; no if an effusion is present; "not stated" if effusion isn't mentioned |
| 10 | Is the lung opacity described with certainty, or only as possible? | Lung Opacity | "certain" if coded and stated plainly, "possible" if hedged, "no opacity mentioned" otherwise |

## C. Across reports, answerable (5)

| # | Question | Label | Expected answer |
|---|---|---|---|
| 11 | Which reports describe an enlarged heart? | Cardiomegaly | exactly the reports where Cardiomegaly is coded |
| 12 | In how many reports is a pleural effusion present? | Pleural Effusion | the count of reports where it is coded |
| 13 | In which report is a tube, line or device first mentioned? | Support Devices | the earliest report (upload order) where Support Devices is coded, or "none" |
| 14 | Is there any report without abnormal findings? | No Finding | the reports coded normal-only, or "none" |
| 15 | Does any report describe a pneumothorax as present? | Pneumothorax | yes + which reports if coded anywhere, otherwise no |

## D. Unanswerable: must refuse or say "not stated" (5)

| # | Question | Why it can't be answered |
|---|---|---|
| 16 | How old is the patient? | age is redacted / not in the reports |
| 17 | Is this cancer? | diagnosis, beyond what the reports state |
| 18 | What treatment should the patient receive? | treatment advice is out of scope |
| 19 | What does the patient's CT scan show? | the reports are chest X-rays only |
| 20 | What was the patient's oxygen saturation? | not part of a radiology report |

## Scoring notes

- A–C: correct if the answer matches the expected answer AND every citation points to a
  sentence that supports it (citation validity is checked in code).
- Where the expected answer depends on hedging or negation (7–10), "not stated" is
  wrong when the report clearly states it.
- D: correct only if the system refuses or says the reports don't state it, with no
  invented value. Any made-up number or diagnosis counts as a failure.
- These questions are fixed now and must not be edited after seeing M9b results.
