/** Round a maximum up to a tidy axis: a step of 1, 2, 5 or 10 times a power of ten. */
export function niceScale(max: number, target = 4): { top: number; step: number; ticks: number[] } {
  const raw = Math.max(max, 1) / target;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const fraction = raw / magnitude;
  const step = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * magnitude;
  const top = Math.max(Math.ceil(max / step) * step, step);
  const ticks: number[] = [];
  for (let value = 0; value <= top + step / 1e6; value += step) ticks.push(Math.round(value * 1e6) / 1e6);
  return { top, step, ticks };
}

/** A rectangle with only its top corners rounded: square at the baseline, rounded at the data end. */
export function topRoundedRect(x: number, y: number, w: number, h: number, radius: number): string {
  const r = Math.max(0, Math.min(radius, w / 2, h));
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

/** The first and last day of a `YYYY-MM` month as `YYYY-MM-DD`. */
export function monthBounds(key: string): { from: string; to: string } {
  const [year, month] = key.split('-').map(Number);
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
  return { from: `${key}-01`, to: `${key}-${String(last).padStart(2, '0')}` };
}
