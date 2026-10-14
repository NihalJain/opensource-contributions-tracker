import { useCallback, useEffect, useState } from 'react';
import { loadDataset } from '../data/load';
import type { Dataset } from '../data/types';

export type DatasetState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: Dataset };

export function useDataset(): { state: DatasetState; reload: () => void } {
  const [state, setState] = useState<DatasetState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    loadDataset(controller.signal)
      .then((data) => setState({ status: 'ready', data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({ status: 'error', message: error instanceof Error ? error.message : 'The data could not be loaded.' });
      });
    return () => controller.abort();
  }, [attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { state, reload };
}
