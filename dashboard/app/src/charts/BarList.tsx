import type { ReactNode } from 'react';
import './BarList.css';

export interface BarRow {
  key: string;
  label: string;
  value: number;
  /** Quiet second line under the label. */
  detail?: ReactNode;
  /** Shown before the label, e.g. an avatar. */
  leading?: ReactNode;
  /** Nested rows are indented and slightly smaller. */
  nested?: boolean;
  /** The value as written next to the bar; defaults to the number. */
  display?: string;
}

interface Props {
  rows: BarRow[];
  ariaLabel: string;
  /** Rows in this set are emphasised and the rest recede. */
  selected?: string[];
  onSelect?: (key: string) => void;
  /** Bar colour as a CSS value. */
  color?: string;
}

/** Fraction of the track a full-scale bar fills, leaving room for the value at its tip. */
const FULL = 0.84;

/** Horizontal bars with the value at the tip. One colour: position, not hue, carries the ranking. */
export function BarList({ rows, ariaLabel, selected = [], onSelect, color = 'var(--c-bar)' }: Props) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  // Top-level rows recede once something is selected. Nested rows (a project's repositories) are
  // the selection's own detail, so they only recede when one of them is itself the selection.
  const anyTopSelected = rows.some((r) => !r.nested && selected.includes(r.key));
  const anyNestedSelected = rows.some((r) => r.nested && selected.includes(r.key));

  return (
    <ul className="bars" aria-label={ariaLabel}>
      {rows.map((row) => {
        const isSelected = selected.includes(row.key);
        const dim = row.nested ? anyNestedSelected && !isSelected : (anyTopSelected || anyNestedSelected) && !isSelected;
        const body = (
          <>
            <span className="bars__label">
              {row.leading}
              <span className="bars__text">
                <span className="bars__name" title={row.label}>
                  {row.label}
                </span>
                {row.detail ? <span className="bars__detail">{row.detail}</span> : null}
              </span>
            </span>
            <span className="bars__track" aria-hidden="true">
              <span
                className="bars__bar"
                style={{ width: `${Math.max((row.value / max) * FULL * 100, row.value > 0 ? 0.8 : 0)}%`, background: color }}
              />
              <span className="bars__value" style={{ left: `calc(${(row.value / max) * FULL * 100}% + 8px)` }}>
                {row.display ?? row.value}
              </span>
            </span>
          </>
        );

        return (
          <li key={row.key} className={row.nested ? 'bars__row bars__row--nested' : 'bars__row'}>
            {onSelect ? (
              <button
                type="button"
                className="bars__item"
                data-dim={dim || undefined}
                aria-pressed={isSelected}
                onClick={() => onSelect(row.key)}
              >
                {body}
                <span className="visually-hidden">{`${row.label}: ${row.display ?? row.value}`}</span>
              </button>
            ) : (
              <div className="bars__item" data-dim={dim || undefined}>
                {body}
                <span className="visually-hidden">{`${row.label}: ${row.display ?? row.value}`}</span>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
