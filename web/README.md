# RadLabel website (M9c frontend)

React + Vite + TypeScript + Tailwind v4 + Framer Motion. Pages: landing (`/`), upload (`/upload`),
results (`/results`). The approved visual design is in `design/` (see `design/DESIGN_README.md`).

```bash
npm install
npm run dev        # http://localhost:5173, mock API (default)
npm test           # main flow in mock mode: sample → results → ask → citation
npm run build
```

**Mock vs real API.** Mock mode is the default while the backend (M9a) doesn't exist; it serves the 5-report
sample patient from `src/mocks/`. `VITE_MOCK=false npm run dev` calls the real API; the dev server proxies
`/api` to `http://localhost:8000` (`vite.config.ts`). `VITE_API_BASE` sets an absolute API origin for a build.
In mock mode, uploading your own reports shows the error state on purpose.

**Numbers.** Every number shown (0.887, 3,086, 94%, 39%, 50 files) lives in `src/numbers.ts`, which must match
README §10.

## API contract the frontend assumes

Types: `src/contract.ts`. Enums mirror `src/radlabel/labels.py` (13 labels, in that order),
`labelling/schema.py` (`Status`) and `labelling/verifier_agent.py` (`Verification`, `corroboration`).
Everything below marked **assumption** is not fixed by the M9 brief; the backend should match it or tell the
frontend.

### `POST /api/session` → `{ "session_id": string }`

### `POST /api/session/{id}/reports`
- **Assumption: request is `multipart/form-data`** with any of: `text` (one pasted report), `files` (repeated,
  `.txt` / `.pdf`; the server extracts PDF text), `sample=true` (load the built-in 5-report sample patient
  instead; no LLM calls needed). The frontend caps files at 50.
- **Assumption: response is `{ "reports": Report[] }`**, ordered by `report_no` (1-based, upload order; pasted
  text first).
- `Report`:
  ```ts
  { report_no: number, filename: string,
    sections: { indication: Sentence[], comparison: Sentence[], findings: Sentence[], impression: Sentence[] },
    sections_identified: boolean,          // false → every sentence is in findings (as F1..Fn)
    labels: Label[],                       // all 13, including not_mentioned
    rules_only?: boolean }                 // assumption, see below
  Sentence = { id: string, text: string }  // findings F1.., impression I1..; indication/comparison ids are not shown
  Label = { label, status, verification, corroboration: "both"|"findings"|"impression"|"none"|null,
            evidence: [{ sentence_id, text }], reason: string }
  ```
- Empty sections are `[]`, not missing.
- **Assumption: `rules_only: true`** when a report's labels come from the rule checks alone (LLM unavailable,
  e.g. the cost cap); the results page then shows a "Rules only" warning for that report.
- Badge text is derived in the frontend: `verified_rules` / `verified` → "Verified" plus " · both sections",
  " · Findings only" or " · Impression only" from `corroboration`; `verified_impression_only` → "Verified ·
  Impression only"; `corrected` / `suggested` / `unverified` as named. `reason` is shown under the badge when
  non-empty.

### `POST /api/session/{id}/ask`
- Body (JSON): `{ "scope": "report" | "all", "report_no"?: number, "question": string }`; `report_no` is sent
  only for scope `report`. Questions are at most 500 characters.
- Response: `{ answer: string | null, refusal: string | null, citations: [{ report_no, sentence_id }],
  retrieved_sentences: number, retrieved_reports: number }`. Exactly one of `answer` / `refusal` is non-null;
  a refusal may still carry citations. Every cited `sentence_id` must exist in that report's sections
  (clicking a citation switches to the report and highlights the sentence).

### `GET /api/session/{id}/timeline`
- **Assumption: response is `{ "timeline": [{ "label": LabelName, "statuses": { "<report_no>": Status } }] }`**
  (JSON object keys are strings). The grid shows labels that are present or uncertain in at least one report,
  without No Finding. Only requested when there is more than one report.

### Errors
- **Assumption:** non-2xx responses carry `{ "detail": string }` (FastAPI default); the frontend shows
  `detail` to the user, so it should be plain language.

### Session lifetime
The frontend keeps reports only in memory; reloading `/results` starts over at `/upload`. It never deletes the
session explicitly (no `DELETE` endpoint assumed); the backend should expire it.
