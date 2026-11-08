import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";

interface AsyncState<T> {
  data?: T;
  error?: Error;
  loading: boolean;
}

/**
 * Runs `fn` whenever `deps` change. Changing deps clears the previous data;
 * `reload()` refetches but keeps showing the current data until the new data arrives.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList) {
  const [state, setState] = useState<AsyncState<T>>({ loading: true });
  const [nonce, setNonce] = useState(0);
  const lastNonce = useRef(nonce);

  useEffect(() => {
    let cancelled = false;
    const isReload = lastNonce.current !== nonce;
    lastNonce.current = nonce;
    setState((s) => (isReload ? { ...s, loading: true } : { loading: true }));

    fn().then(
      (data) => !cancelled && setState({ data, loading: false }),
      (error: unknown) =>
        !cancelled && setState({ error: error instanceof Error ? error : new Error(String(error)), loading: false }),
    );
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps are supplied by the caller
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}
