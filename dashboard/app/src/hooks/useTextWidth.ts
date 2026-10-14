import { useCallback, useEffect, useMemo, useState } from 'react';

/**
 * Measures text in the real font, so a label is only drawn where it fits. The measurement is
 * repeated once web fonts finish loading, because the fallback font is wider or narrower.
 */
export function useTextWidth(font: string) {
  const [loaded, setLoaded] = useState(0);
  const context = useMemo(() => document.createElement('canvas').getContext('2d'), []);

  useEffect(() => {
    let cancelled = false;
    document.fonts?.ready.then(() => {
      if (!cancelled) setLoaded((n) => n + 1);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return useCallback(
    (text: string) => {
      if (!context) return text.length * 8;
      context.font = font;
      return context.measureText(text).width;
    },
    // `loaded` is a dependency on purpose: it changes when the fonts become available.
    [context, font, loaded],
  );
}
