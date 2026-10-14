import { useEffect, useRef, useState } from 'react';

/** The rendered width of an element, kept current as the layout changes. */
export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.round(entry.contentRect.width));
    });
    observer.observe(element);
    setWidth(Math.round(element.getBoundingClientRect().width) || fallback);
    return () => observer.disconnect();
  }, [fallback]);

  return { ref, width };
}
