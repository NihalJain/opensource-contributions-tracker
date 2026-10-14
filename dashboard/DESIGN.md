# Dashboard design

Notes for anyone changing how the dashboard looks or what it shows.

## Principles

1. **The data is the loudest thing.** One bold element, the merged-pull-request count set in heavy condensed type, carries the page. Everything around it is quiet: no coloured fields, no boxed cards, no gradients, no icons standing in for words.
2. **Lead with impact, explore on demand.** The first screen answers "what has this person or team done?". Filtering and drill-down sit one step below, and every control scopes the whole page.
3. **Show what the tracker measures.** The report's own headline numbers (contribution score, code reviews, commits, rank) are first-class, not buried behind pull request counts.
4. **Every number is reachable without a mouse or a tooltip.** Each chart has a table twin, charts are keyboard operable, and tooltips only repeat what is already on screen.
5. **Small and fast.** No charting library: the charts are plain SVG and HTML, and the JavaScript and CSS together are about 90 kB gzipped. The only other download is the self-hosted font.

## Colour

Structure is neutral: a pale stone paper, near-black ink and gray rules, with no brand colour. Colour is reserved for data and uses the meanings GitHub has taught everyone who reads pull requests: **purple is merged, green is open, blue is an issue, gray is closed without merging.** The accent used for selection and focus is the same purple, so "selected" and "merged" read as one idea: the thing the page is about.

Bars that measure a score or a count rather than an outcome (projects, contributors) are ink, not a hue, so a colour never means two things.

| Role | Light | Dark |
|---|---|---|
| Paper | `#f3f3f0` | `#151517` |
| Surface | `#ffffff` | `#1b1b1d` |
| Ink | `#17181a` | `#ececea` |
| Merged, and the accent | `#8250df` | `#8957e5` |
| Open | `#1a7f37` | `#2ea043` |
| Issue | `#0969da` | `#1f6feb` |
| Closed without merging | `#bcbcb5` | `#55555a` |

The three outcome colours were validated as a set against each theme's chart surface (lightness band, chroma floor, colour-vision-deficiency separation, normal-vision separation, contrast). Purple against blue is the closest pair under tritanopia, below the comfortable margin, so no chart relies on colour alone: each has a legend, 2px gaps between segments, and a table twin. "Closed without merging" is deliberately a de-emphasised gray, not a series colour.

If you change a chart colour, re-validate the set rather than judging by eye. Text never uses a series colour; it uses the ink tokens.

## Type

One family, [Archivo](https://fonts.google.com/specimen/Archivo), self-hosted as a variable font with a width axis. The same family does two jobs by changing width and weight: the large figures are condensed and heavy, and running text is regular width. Large standalone numbers use proportional figures; tabular figures are reserved for columns that must align (the explorer, axis ticks, the project bars).

## Charts

- Bars are at most 24px thick, with a 4px rounded data end and a square baseline.
- Touching marks are separated by a 2px gap in the surface colour, never a stroke.
- Gridlines are solid hairlines. Values are labelled at the tip, and only the peak of the timeline is labelled directly.
- The timeline, project bars and speed bands all work from the same filtered data, and each part ignores the filters that would hide its own choices (the timeline keeps every month so a range can be changed; the project list keeps every project so one can be switched off).

## Accessibility

- Keyboard: every control is reachable and operable; the timeline supports arrow keys, Home, End, Enter and Escape.
- Screen readers: landmarks, a skip link, `aria-pressed` on toggles, `aria-sort` on the table, and a live region for result counts.
- Targets: interactive targets are at least 24 by 24 pixels. Ribbon segments narrower than that are drawn for proportion but not clickable; the project list offers the same control at full size.
- Motion: one entrance animation on the ribbon, removed under `prefers-reduced-motion`.
- Lighthouse (mobile): accessibility, best practices, SEO and agentic browsing all 100.

## Adding a metric

1. Make it available to the page. Metrics that come from the report's CSV need no generator change: add the column to `scripts/contributions.mjs`, to the `Contribution` type, and use it.
2. Aggregate it in `src/data/aggregate.ts` or `insights.ts` with a test beside it.
3. Show it in the component that owns that part of the page, and add it to that chart's table twin.
