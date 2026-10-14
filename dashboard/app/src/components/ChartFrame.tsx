import { useId, useState, type ReactNode } from 'react';
import './ChartFrame.css';

interface Props {
  title: string;
  description?: ReactNode;
  /** Legend or controls rendered between the heading and the plot. */
  aside?: ReactNode;
  /** The same numbers as an accessible table; every chart has one. */
  table: ReactNode;
  children: ReactNode;
}

export function ChartFrame({ title, description, aside, table, children }: Props) {
  const [asTable, setAsTable] = useState(false);
  const headingId = useId();

  return (
    <section className="chart" aria-labelledby={headingId}>
      <header className="chart__head">
        <div>
          <h2 id={headingId} className="chart__title">
            {title}
          </h2>
          {description ? <p className="chart__desc">{description}</p> : null}
        </div>
        <button
          type="button"
          className="chart__toggle no-print"
          aria-pressed={asTable}
          onClick={() => setAsTable((v) => !v)}
        >
          {asTable ? 'View chart' : 'View as table'}
        </button>
      </header>
      {aside}
      <div className="chart__body">{asTable ? table : children}</div>
    </section>
  );
}

/** A compact, scrollable data table in the chart's own visual language. */
export function DataTable({ caption, head, rows }: { caption: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="data-table" tabIndex={0} role="region" aria-label={caption}>
      <table>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={h} scope="col" className={i === 0 ? undefined : 'num'}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, r) => (
            <tr key={r}>
              {cells.map((cell, c) => (
                <td key={c} className={c === 0 ? undefined : 'num'}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul className="legend" aria-label="Legend">
      {items.map((item) => (
        <li key={item.label} className="legend__item">
          <span className="legend__key" style={{ background: item.color }} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
