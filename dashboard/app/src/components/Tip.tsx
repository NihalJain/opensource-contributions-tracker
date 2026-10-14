import { useCallback, useState, type ReactNode } from 'react';
import './Tip.css';

export interface TipState {
  /** Position relative to the chart container, in pixels. */
  x: number;
  y: number;
  content: ReactNode;
}

export function useTip() {
  const [tip, setTip] = useState<TipState | null>(null);
  const show = useCallback((x: number, y: number, content: ReactNode) => setTip({ x, y, content }), []);
  const hide = useCallback(() => setTip(null), []);
  return { tip, show, hide };
}

const HALF_WIDTH = 112;

/** A tooltip that stays inside its container. Place it inside a `position: relative` box. */
export function Tip({ tip, width }: { tip: TipState | null; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x, HALF_WIDTH), Math.max(width - HALF_WIDTH, HALF_WIDTH));
  return (
    <div className="tip" role="status" style={{ left, top: tip.y }}>
      {tip.content}
    </div>
  );
}

export function TipRow({ swatch, label, value }: { swatch?: string; label: string; value: ReactNode }) {
  return (
    <div className="tip__row">
      {swatch ? <span className="tip__key" style={{ background: swatch }} aria-hidden="true" /> : null}
      <span className="tip__value">{value}</span>
      <span className="tip__label">{label}</span>
    </div>
  );
}
