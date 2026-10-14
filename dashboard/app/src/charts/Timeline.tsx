import { useMemo, useState, type KeyboardEvent, type PointerEvent } from 'react';
import type { MonthBucket } from '../data/aggregate';
import { formatInt, formatMonth } from '../data/format';
import { ChartFrame, DataTable, Legend } from '../components/ChartFrame';
import { Tip, TipRow, useTip } from '../components/Tip';
import { useWidth } from '../hooks/useSize';
import { monthBounds, niceScale, topRoundedRect } from './scale';
import './Timeline.css';

export interface Range {
  from: string | null;
  to: string | null;
}

/**
 * Stack order matters. Merged is the baseline because it is the series being read; open and issues
 * follow, and closed is last. Green (open) and red (closed) are the pair people with red-green
 * colour blindness cannot tell apart, so the gray issues segment always sits between them.
 */
export const SERIES = [
  { key: 'merged', label: 'Merged pull requests', color: 'var(--c-merged)' },
  { key: 'open', label: 'Open pull requests', color: 'var(--c-open)' },
  { key: 'issues', label: 'Issues', color: 'var(--c-issue)' },
  { key: 'closed', label: 'Closed without merging', color: 'var(--c-closed)' },
] as const;

const HEIGHT = 248;
const MARGIN = { top: 22, right: 8, bottom: 30, left: 34 };
const GAP = 2;

interface Props {
  buckets: MonthBucket[];
  range: Range;
  onRange: (range: Range) => void;
}

function indexRange(buckets: MonthBucket[], range: Range): [number, number] | null {
  if (!range.from && !range.to) return null;
  const from = range.from?.slice(0, 7) ?? '';
  const to = range.to?.slice(0, 7) ?? '9999-99';
  let first = -1;
  let last = -1;
  buckets.forEach((bucket, i) => {
    if (bucket.key >= from && bucket.key <= to) {
      if (first === -1) first = i;
      last = i;
    }
  });
  return first === -1 ? null : [first, last];
}

export function Timeline({ buckets, range, onRange }: Props) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTip();
  const [hover, setHover] = useState<number | null>(null);
  const [focus, setFocus] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ anchor: number; current: number } | null>(null);

  const n = buckets.length;
  const innerW = Math.max(width - MARGIN.left - MARGIN.right, 10);
  const innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const band = innerW / Math.max(n, 1);
  const barW = Math.min(24, Math.max(2, band * 0.7));

  const peak = useMemo(() => {
    let best = -1;
    buckets.forEach((b, i) => {
      if (b.total > 0 && (best === -1 || b.total > buckets[best].total)) best = i;
    });
    return best;
  }, [buckets]);

  const { top, ticks } = useMemo(() => niceScale(Math.max(...buckets.map((b) => b.total), 1)), [buckets]);
  const selected = useMemo(() => indexRange(buckets, range), [buckets, range]);

  const y = (value: number) => MARGIN.top + innerH - (value / top) * innerH;
  const xBand = (i: number) => MARGIN.left + i * band;
  const xCenter = (i: number) => xBand(i) + band / 2;

  const indexAt = (event: PointerEvent<SVGRectElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const raw = Math.floor(((event.clientX - box.left) / box.width) * n);
    return Math.min(Math.max(raw, 0), n - 1);
  };

  const showFor = (i: number) => {
    const bucket = buckets[i];
    show(
      xCenter(i),
      y(bucket.total) - 2,
      <>
        <div className="tip__title">{formatMonth(bucket.start)}</div>
        {bucket.total === 0 ? (
          <div className="tip__note">No activity</div>
        ) : (
          <>
            {SERIES.map((s) =>
              bucket[s.key] > 0 ? (
                <TipRow key={s.key} swatch={s.color} label={s.label} value={formatInt(bucket[s.key])} />
              ) : null,
            )}
            <div className="tip__note">Opened this month, by outcome</div>
          </>
        )}
      </>,
    );
  };

  const commit = (from: number, to: number) => {
    const a = monthBounds(buckets[Math.min(from, to)].key);
    const b = monthBounds(buckets[Math.max(from, to)].key);
    const same = selected && selected[0] === Math.min(from, to) && selected[1] === Math.max(from, to);
    onRange(same ? { from: null, to: null } : { from: a.from, to: b.to });
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (n === 0) return;
    const current = focus ?? (selected ? selected[0] : n - 1);
    let next = current;
    if (event.key === 'ArrowRight') next = Math.min(current + 1, n - 1);
    else if (event.key === 'ArrowLeft') next = Math.max(current - 1, 0);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = n - 1;
    else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      commit(current, current);
      return;
    } else if (event.key === 'Escape') {
      onRange({ from: null, to: null });
      return;
    } else return;
    event.preventDefault();
    setFocus(next);
    showFor(next);
  };

  // Year labels go at each January, plus the first month if the series starts mid-year. Greedy
  // from the left: a label is dropped when it would sit closer than MIN_LABEL_GAP to the last one.
  const MIN_LABEL_GAP = 40;
  const januaries = buckets.map((b, i) => ({ b, i })).filter(({ b }) => b.key.endsWith('-01'));
  const yearLabels: { b: MonthBucket; i: number }[] = [];
  let lastX = -Infinity;
  for (const entry of januaries) {
    const x = xBand(entry.i);
    if (x - lastX >= MIN_LABEL_GAP) {
      yearLabels.push(entry);
      lastX = x;
    }
  }
  if (n > 0 && !buckets[0].key.endsWith('-01')) {
    const next = yearLabels[0];
    if (!next || xBand(next.i) - xBand(0) >= MIN_LABEL_GAP) yearLabels.unshift({ b: buckets[0], i: 0 });
  }

  const table = (
    <DataTable
      caption="Pull requests and issues opened per month, by outcome"
      head={['Month', ...SERIES.map((s) => s.label), 'Total']}
      rows={buckets.map((b) => [
        formatMonth(b.start),
        ...SERIES.map((s) => formatInt(b[s.key])),
        formatInt(b.total),
      ])}
    />
  );

  const dragBounds = drag ? [Math.min(drag.anchor, drag.current), Math.max(drag.anchor, drag.current)] : null;

  return (
    <ChartFrame
      title="Activity over time"
      description="Pull requests and issues by the month they were opened. Drag across months to filter everything on the page."
      aside={<Legend items={SERIES.map((s) => ({ label: s.label, color: s.color }))} />}
      table={table}
    >
      <div
        ref={ref}
        className="timeline"
        tabIndex={0}
        role="group"
        aria-label="Activity timeline. Use the left and right arrow keys to move between months, Enter to filter to a month, Escape to clear."
        onKeyDown={onKeyDown}
        onBlur={() => {
          setFocus(null);
          hide();
        }}
      >
        <svg width={width} height={HEIGHT} role="presentation">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(t)} y2={y(t)} className="timeline__grid" />
              <text x={MARGIN.left - 8} y={y(t)} dy="0.32em" textAnchor="end">
                {t}
              </text>
            </g>
          ))}
          <line
            x1={MARGIN.left}
            x2={width - MARGIN.right}
            y1={y(0)}
            y2={y(0)}
            className="timeline__axis"
          />

          {dragBounds ? (
            <rect
              x={xBand(dragBounds[0])}
              y={MARGIN.top}
              width={(dragBounds[1] - dragBounds[0] + 1) * band}
              height={innerH}
              className="timeline__drag"
            />
          ) : null}
          {hover !== null && !drag ? (
            <rect x={xBand(hover)} y={MARGIN.top} width={band} height={innerH} className="timeline__hover" />
          ) : null}
          {focus !== null ? (
            <rect x={xBand(focus)} y={MARGIN.top} width={band} height={innerH} className="timeline__focus" />
          ) : null}

          {buckets.map((bucket, i) => {
            const inRange = !selected || (i >= selected[0] && i <= selected[1]);
            let cumulative = 0;
            const visible = SERIES.filter((s) => bucket[s.key] > 0);
            return (
              <g key={bucket.key} opacity={inRange ? 1 : 0.28}>
                {visible.map((s, k) => {
                  const lower = y(cumulative);
                  cumulative += bucket[s.key];
                  const upper = y(cumulative);
                  const isTop = k === visible.length - 1;
                  const segmentTop = isTop ? upper : upper + GAP / 2;
                  const segmentBottom = k === 0 ? lower : lower - GAP / 2;
                  const h = Math.max(segmentBottom - segmentTop, 1);
                  const x = xCenter(i) - barW / 2;
                  return isTop ? (
                    <path key={s.key} d={topRoundedRect(x, segmentTop, barW, h, 4)} fill={s.color} />
                  ) : (
                    <rect key={s.key} x={x} y={segmentTop} width={barW} height={h} fill={s.color} />
                  );
                })}
              </g>
            );
          })}

          {peak >= 0 && n > 1 ? (
            <text
              x={xCenter(peak)}
              y={y(buckets[peak].total) - 6}
              textAnchor={peak > n - 4 ? 'end' : peak < 3 ? 'start' : 'middle'}
              className="timeline__peak"
            >
              {formatInt(buckets[peak].total)} in {formatMonth(buckets[peak].start)}
            </text>
          ) : null}

          {yearLabels.map(({ b, i }) => (
            <g key={b.key}>
              <line x1={xBand(i)} x2={xBand(i)} y1={y(0)} y2={y(0) + 5} className="timeline__axis" />
              <text x={xBand(i) + 3} y={HEIGHT - 10}>
                {b.key.slice(0, 4)}
              </text>
            </g>
          ))}

          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={innerW}
            height={innerH + 6}
            fill="transparent"
            className="timeline__hit"
            onPointerMove={(event) => {
              const i = indexAt(event);
              setHover(i);
              showFor(i);
              if (drag) setDrag({ anchor: drag.anchor, current: i });
            }}
            onPointerLeave={() => {
              setHover(null);
              if (!drag) hide();
            }}
            onPointerDown={(event) => {
              event.currentTarget.setPointerCapture(event.pointerId);
              const i = indexAt(event);
              setDrag({ anchor: i, current: i });
            }}
            onPointerUp={(event) => {
              if (!drag) return;
              commit(drag.anchor, indexAt(event));
              setDrag(null);
            }}
            onPointerCancel={() => setDrag(null)}
          />
        </svg>
        <Tip tip={tip} width={width} />
      </div>
    </ChartFrame>
  );
}
