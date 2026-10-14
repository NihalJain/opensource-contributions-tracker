import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';
import { formatInt } from '../data/format';
import './FilterMenu.css';

export interface Option {
  value: string;
  label: string;
  count: number;
}

/** A button that opens a small panel; closes on outside click or Escape and restores focus. */
export function Popover({
  label,
  badge,
  active,
  children,
}: {
  label: string;
  badge?: string;
  active?: boolean;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="popover" ref={root}>
      <button
        ref={button}
        type="button"
        className="popover__button"
        data-active={active || undefined}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        <span>{label}</span>
        {badge ? <span className="popover__badge">{badge}</span> : null}
        <svg className="popover__chevron" viewBox="0 0 12 12" width="10" height="10" aria-hidden="true">
          <path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>
      {open ? (
        <div className="popover__panel" id={panelId}>
          {children(() => setOpen(false))}
        </div>
      ) : null}
    </div>
  );
}

interface MenuProps {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
  /** Show a text box to narrow long lists. */
  searchable?: boolean;
}

export function FilterMenu({ label, options, selected, onChange, searchable }: MenuProps) {
  const [needle, setNeedle] = useState('');
  const shown = useMemo(() => {
    const q = needle.trim().toLowerCase();
    return q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options;
  }, [options, needle]);

  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);

  return (
    <Popover label={label} badge={selected.length > 0 ? String(selected.length) : undefined} active={selected.length > 0}>
      {() => (
        <div className="menu">
          {searchable ? (
            <input
              className="menu__search"
              type="search"
              placeholder={`Find in ${label.toLowerCase()}`}
              aria-label={`Find in ${label.toLowerCase()}`}
              value={needle}
              onChange={(e) => setNeedle(e.target.value)}
              autoFocus
            />
          ) : null}
          <ul className="menu__list">
            {shown.map((option) => (
              <li key={option.value}>
                <label className="menu__option">
                  <input
                    type="checkbox"
                    checked={selected.includes(option.value)}
                    onChange={() => toggle(option.value)}
                  />
                  <span className="menu__text" title={option.label}>
                    {option.label}
                  </span>
                  <span className="menu__count">{formatInt(option.count)}</span>
                </label>
              </li>
            ))}
            {shown.length === 0 ? <li className="menu__empty">Nothing matches</li> : null}
          </ul>
          {selected.length > 0 ? (
            <button type="button" className="menu__clear" onClick={() => onChange([])}>
              Clear {label.toLowerCase()}
            </button>
          ) : null}
        </div>
      )}
    </Popover>
  );
}
