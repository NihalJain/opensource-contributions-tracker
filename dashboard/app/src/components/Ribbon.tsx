import { useState } from 'react';
import type { ProjectBreakdown } from '../data/aggregate';
import { formatCompact, formatInt } from '../data/format';
import { foldThin } from '../data/ribbon';
import { useWidth } from '../hooks/useSize';
import { useTextWidth } from '../hooks/useTextWidth';
import './Ribbon.css';

interface Props {
  breakdown: ProjectBreakdown;
  selected: string[];
  onToggle: (project: string) => void;
}

/** Horizontal padding inside a segment, both sides together. */
const SEGMENT_PADDING = 26;
/** Projects named in the index before "Show all". A selected project is always shown. */
const COLLAPSED = 10;
/**
 * The narrowest a segment is drawn, in pixels. Anything thinner is folded into one "more" segment
 * of the true combined width: if every sliver were widened to this minimum, a long tail would
 * take space from the projects that matter and the bar would misstate the concentration.
 */
const MIN_SEGMENT = 6;

const percent = (share: number) => (share > 0 && share < 0.01 ? '<1%' : `${Math.round(share * 100)}%`);

/**
 * Where the work went. The bar answers "how concentrated is it?" at a glance, which is exactly
 * what skewed data needs. It can only name segments wide enough to hold a name, so beneath it an
 * index names every project, with its value and share. The index is the accessible control; the
 * bar is a visual summary that mouse users can click and everyone else can ignore.
 */
export function Ribbon({ breakdown, selected, onToggle }: Props) {
  const { ref, width } = useWidth<HTMLUListElement>(960);
  const nameWidth = useTextWidth('600 13px "Archivo Variable", sans-serif');
  const valueWidth = useTextWidth('700 13px "Archivo Variable", sans-serif');
  const [hovered, setHovered] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const { projects, measure } = breakdown;
  const total = projects.reduce((sum, p) => sum + p.value, 0);
  const usable = Math.max(width - 2 * Math.max(projects.length - 1, 0), 0);
  const fmt = (n: number) => (measure === 'score' ? formatCompact(n) : formatInt(n));

  const rows = projects.map((p) => ({
    project: p.project,
    countsOnly: p.countsOnly,
    avatar: p.avatar,
    value: p.value,
    share: total > 0 ? p.value / total : 0,
    text: fmt(p.value),
  }));
  const { drawn, folded, foldedValue } = foldThin(rows, usable, MIN_SEGMENT);
  const indexed = rows.filter((r, i) => showAll || i < COLLAPSED || selected.includes(r.project));
  const hiddenCount = rows.length - indexed.length;
  const anySelected = selected.length > 0;

  return (
    <section className="ribbon" aria-label="Where the work went">
      <div className="ribbon__head">
        <h2 className="ribbon__title">Where the work went</h2>
        <p className="ribbon__measure">{measure === 'score' ? 'by contribution score' : 'by pull requests and issues'}</p>
      </div>

      <ul className="ribbon__bar" ref={ref} aria-hidden="true">
        {drawn.map((row, i) => {
          const room = row.share * usable;
          const showName = room >= nameWidth(row.project) + SEGMENT_PADDING;
          const showValue = room >= valueWidth(row.text) + SEGMENT_PADDING;
          return (
            <li key={row.project} style={{ flexGrow: Math.max(row.value, 0.0001), ['--i' as string]: i }}>
              <span
                className="ribbon__seg"
                data-selected={selected.includes(row.project) || undefined}
                data-dim={(anySelected && !selected.includes(row.project)) || undefined}
                data-hover={hovered === row.project || undefined}
                data-narrow={!showValue || undefined}
                title={row.countsOnly ? `${row.project}: ${row.text} (counted, not itemised)` : `${row.project}: ${row.text}`}
                data-static={row.countsOnly || undefined}
                onClick={row.countsOnly ? undefined : () => onToggle(row.project)}
                onPointerEnter={() => setHovered(row.project)}
                onPointerLeave={() => setHovered(null)}
              >
                {showName ? <span className="ribbon__name">{row.project}</span> : null}
                {showValue ? <span className="ribbon__value">{row.text}</span> : null}
              </span>
            </li>
          );
        })}
        {folded.length > 0 ? (
          <li style={{ flexGrow: Math.max(foldedValue, 0.0001), ['--i' as string]: drawn.length }}>
            <span
              className="ribbon__seg ribbon__seg--rest"
              data-narrow
              title={`${folded.length} smaller projects: ${folded.map((r) => `${r.project} ${r.text}`).join(', ')}`}
            />
          </li>
        ) : null}
      </ul>

      <ul className="ribbon__index" aria-label={`Projects ${measure === 'score' ? 'by contribution score' : 'by pull requests and issues'}`}>
        {indexed.map((row) => {
          const isSelected = selected.includes(row.project);
          if (row.countsOnly) {
            // Nothing to filter to: there are no pull requests or issues behind it, only counts.
            return (
              <li key={row.project}>
                <span className="ribbon__item ribbon__item--static" data-dim={(anySelected && !isSelected) || undefined}>
                  <span className="ribbon__item-name">{row.project}</span>
                  <span className="ribbon__item-value">{row.text}</span>
                  <span className="ribbon__item-share">{percent(row.share)}</span>
                  <span className="visually-hidden">counted, not itemised</span>
                </span>
              </li>
            );
          }
          return (
            <li key={row.project}>
              <button
                type="button"
                className="ribbon__item"
                aria-pressed={isSelected}
                data-dim={(anySelected && !isSelected) || undefined}
                data-hover={hovered === row.project || undefined}
                onClick={() => onToggle(row.project)}
                onPointerEnter={() => setHovered(row.project)}
                onPointerLeave={() => setHovered(null)}
                onFocus={() => setHovered(row.project)}
                onBlur={() => setHovered(null)}
              >
                {row.avatar ? (
                  <img className="ribbon__item-avatar" src={row.avatar} alt="" width="16" height="16" loading="lazy" />
                ) : null}
                <span className="ribbon__item-name">{row.project}</span>
                <span className="ribbon__item-value">{row.text}</span>
                <span className="ribbon__item-share">{percent(row.share)}</span>
              </button>
            </li>
          );
        })}
        {rows.length > COLLAPSED ? (
          <li>
            <button type="button" className="ribbon__more" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll}>
              {showAll ? 'Show fewer' : `Show all ${rows.length}`}
            </button>
            {!showAll && hiddenCount > 0 ? <span className="visually-hidden">{`${hiddenCount} more projects`}</span> : null}
          </li>
        ) : null}
      </ul>
    </section>
  );
}
