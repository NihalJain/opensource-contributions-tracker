# Dashboard design

Notes for anyone changing how the dashboard looks or what it shows.

## Principles

1. **The data is the loudest thing.** One bold element, the merged-pull-request count set in heavy condensed type, carries the page. Everything around it is quiet: no coloured fields, no boxed cards, no gradients, no icons standing in for words.
2. **Lead with impact, explore on demand.** The first screen answers "what has this person or team done?". Filtering and drill-down sit one step below, and every control scopes the whole page.
3. **Show what the tracker measures.** The report's own headline numbers (contribution score, code reviews, commits, rank) are first-class, not buried behind pull request counts.
4. **Every number is reachable without a mouse or a tooltip.** Each chart has a table twin, charts are keyboard operable, and tooltips only repeat what is already on screen.
5. **Small and fast.** No charting library: the charts are plain SVG and HTML, and the JavaScript and CSS together are about 90 kB gzipped. The only other download is the self-hosted font.

## Colour

Structure is neutral: a pale stone paper, near-black ink and gray rules, with no brand colour. Colour is reserved for data and uses the status colours people already read on GitHub: **purple is a merged pull request, green is an open one, red is one closed without merging, and gray is an issue**, a different kind of item that is kept quiet. **Blue is the interface accent** (selection, focus, primary actions), as it is for links on GitHub. No data series uses blue, so a colour never means two things.

Bars that measure a score or a count rather than an outcome (projects, contributors) are ink, not a hue. In the explorer a closed *issue* keeps a gray dot, because resolved work is not a rejection.

| Role | Light | Dark |
|---|---|---|
| Paper | `#f3f3f0` | `#151517` |
| Surface | `#ffffff` | `#1b1b1d` |
| Ink | `#17181a` | `#ececea` |
| Merged | `#8250df` | `#8957e5` |
| Open | `#1a7f37` | `#2ea043` |
| Closed without merging | `#cf222e` | `#da3633` |
| Issues | `#6e7781` | `#7d8590` |
| Interface accent | `#0969da` | `#1f6feb` |

**Red and green are the classic colour-blindness pair**, so a stack never puts them side by side. The order is always merged, open, issues, closed: merged sits on the baseline because it is the series being read, and the gray issues segment sits between green and red. The validator measures green directly beside red at a deuteranopia ΔE of only 5.5 in light mode and 3.1 in dark mode (both fail); with gray between them the closest pair measures 9.3 and 10.3. The three chromatic colours were validated against each theme's chart surface (lightness band, colour-vision-deficiency separation, normal-vision separation, contrast). Gray is deliberately the de-emphasis role rather than a series colour, which is why it sits outside the chroma floor.

No chart relies on colour alone: each has a legend in the stack's order, 2px gaps between segments, and a table twin.

If you change a chart colour or the stack order, re-validate the set rather than judging by eye. Text never uses a series colour; it uses the ink tokens.

## Type

One family, [Archivo](https://fonts.google.com/specimen/Archivo), self-hosted as a variable font with a width axis. The same family does two jobs by changing width and weight: the large figures are condensed and heavy, and running text is regular width. Large standalone numbers use proportional figures; tabular figures are reserved for columns that must align (the explorer, axis ticks, the project bars).

## Charts

- Bars are at most 24px thick, with a 4px rounded data end and a square baseline.
- Touching marks are separated by a 2px gap in the surface colour, never a stroke.
- Gridlines are solid hairlines. Values are labelled at the tip, and only the peak of the timeline is labelled directly.
- The timeline, project bars and speed bands all work from the same filtered data, and each part ignores the filters that would hide its own choices (the timeline keeps every month so a range can be changed; the project list keeps every project so one can be switched off).

## The project bar

Real contribution data is skewed: one project is often 80% of the score. A proportional bar is the right form for that story, but it can only name a segment wide enough to hold its name, so on skewed data most segments are unlabelled slivers. Two decisions follow:

- **Name everything beneath it.** An index lists every project with its value and share, ten at first with "Show all" for longer tails, and the bar and index highlight together.
- **Never widen slivers.** Forcing every thin segment to a minimum width lets a long tail take space from the projects that matter, so the bar misstates the concentration (measured: a project holding 52% of the score was drawn at 8% before this rule). Segments under 6px are folded into one outlined "smaller projects" segment of their true combined width.

## Accessibility

- Keyboard: every control is reachable and operable; the timeline supports arrow keys, Home, End, Enter and Escape.
- Screen readers: landmarks, a skip link, `aria-pressed` on toggles, `aria-sort` on the table, and a live region for result counts.
- Targets: interactive targets are at least 24 by 24 pixels. The proportional bar in the hero is a visual summary, hidden from assistive technology and not focusable; the project index beneath it carries every project as a full-size control.
- Motion: one entrance animation on the ribbon, removed under `prefers-reduced-motion`.
- Lighthouse (mobile): accessibility, best practices, SEO and agentic browsing all 100.

## Adding a metric

1. Make it available to the page. Metrics that come from the report's CSV need no generator change: add the column to `scripts/contributions.mjs`, to the `Contribution` type, and use it.
2. Aggregate it in `src/data/aggregate.ts` or `insights.ts` with a test beside it.
3. Show it in the component that owns that part of the page, and add it to that chart's table twin.
