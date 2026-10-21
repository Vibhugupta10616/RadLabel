# RadLabel website design reference (approved mockup)

These four files are the approved visual design for the website (M9c). They are
mockup sources, not production code:

- `Landing.dc.html` — landing page (hero animation, four steps, feature blocks,
  chatbot comparison, safety band, CTA, footer)
- `Main.dc.html` — upload page
- `Results.dc.html` — results page: report list, report text with evidence
  highlighting, finding cards with badges, "Ask about this report" and
  "Ask across all reports" tabs, findings-over-time grid
- `Phone.dc.html` — results on a phone (still shows "Report 1 of 3"; the real
  sample patient has 5 reports)

Format notes:
- Plain HTML with inline styles. `{{name}}` placeholders, `<sc-for>` (loops),
  `<sc-if>` (conditions) and the `class Component extends DCLogic` script are the
  mockup tool's templating: read them as "this repeats" / "this shows when…" and the
  script's data as example content. Don't copy that templating into React.
- `<helmet><style>` holds the CSS animations (keyframes): highlight sweep, pop-in,
  float, typing reveal, growing bars, scroll fade-up, hover lift, and the
  `prefers-reduced-motion` switch-off.
- `support.js` is the mockup tool's runtime and is not included; it isn't needed.
- Links like `Results.dc.html` mean "go to the results page".

Rebuild the look in React + Tailwind + Framer Motion; take colours, sizes, spacing,
copy, layout and animation timing from these files. Data shown in them (the sample
patient, numbers) is illustrative: real labels come from the API, and every number on
the site must come from README §10.
