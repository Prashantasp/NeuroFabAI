"use client";

/**
 * Data-fetching hooks used across the app.
 *
 * Small and purpose-built rather than a data-fetching library: the app has a
 * handful of endpoints and adding one would be a dependency for no gain. What
 * these do guarantee is the behaviour every screen needs — abortable requests,
 * no state updates after unmount, and a `stale` flag so a background refresh
 * never blanks the screen the user is reading.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { errorMessage } from "@/lib/api";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  /** True only on the first load, so refreshes do not show a skeleton. */
  isLoading: boolean;
  isRefreshing: boolean;
}

interface UseAsyncOptions {
  /** Skip fetching entirely (e.g. before a workspace is selected). */
  enabled?: boolean;
  /** Poll interval in ms. Polling pauses while the tab is hidden. */
  refreshInterval?: number;
}

export function useAsync<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  options: UseAsyncOptions = {},
) {
  const { enabled = true, refreshInterval } = options;

  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    isLoading: enabled,
    isRefreshing: false,
  });

  // Keep the latest fetcher without making it a dependency, so an inline
  // closure does not restart the effect on every render. Assigned in an effect
  // rather than during render: mutating a ref while rendering is unsafe under
  // concurrent rendering, and no event can fire before the first effect runs.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const controllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      controllerRef.current?.abort();
    };
  }, []);

  const run = useCallback(async (isBackground: boolean) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setState((prev) => ({
      ...prev,
      isLoading: prev.data === null && !isBackground,
      isRefreshing: isBackground,
      error: isBackground ? prev.error : null,
    }));

    try {
      const data = await fetcherRef.current(controller.signal);
      if (!mountedRef.current || controller.signal.aborted) return;
      setState({ data, error: null, isLoading: false, isRefreshing: false });
    } catch (error) {
      if (!mountedRef.current || controller.signal.aborted) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      setState((prev) => ({
        // A failed background poll keeps the last good data on screen rather
        // than replacing a working view with an error.
        data: isBackground ? prev.data : null,
        error: errorMessage(error),
        isLoading: false,
        isRefreshing: false,
      }));
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setState({ data: null, error: null, isLoading: false, isRefreshing: false });
      return;
    }
    void run(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, run, ...deps]);

  useEffect(() => {
    if (!enabled || !refreshInterval) return;

    const tick = () => {
      // Polling a hidden tab burns quota and battery for nothing.
      if (document.visibilityState === "visible") void run(true);
    };
    const timer = setInterval(tick, refreshInterval);
    document.addEventListener("visibilitychange", tick);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [enabled, refreshInterval, run]);

  const refresh = useCallback(() => run(true), [run]);
  const reload = useCallback(() => run(false), [run]);

  const mutate = useCallback((updater: (current: T | null) => T | null) => {
    setState((prev) => ({ ...prev, data: updater(prev.data) }));
  }, []);

  return { ...state, refresh, reload, mutate };
}

/** Debounce a rapidly changing value (search inputs). */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}

/**
 * Guard an async action against double submission.
 *
 * Returns a stable `run` that ignores calls while one is already in flight,
 * which is what actually prevents the duplicate-submit class of bug — disabling
 * a button alone still loses the race on Enter key repeats.
 */
export function useAction<Args extends unknown[], R>(
  action: (...args: Args) => Promise<R>,
): { run: (...args: Args) => Promise<R | undefined>; isPending: boolean } {
  const [isPending, setIsPending] = useState(false);
  const inFlight = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const actionRef = useRef(action);
  useEffect(() => {
    actionRef.current = action;
  });

  const run = useCallback(async (...args: Args) => {
    if (inFlight.current) return undefined;
    inFlight.current = true;
    setIsPending(true);
    try {
      return await actionRef.current(...args);
    } finally {
      inFlight.current = false;
      if (mountedRef.current) setIsPending(false);
    }
  }, []);

  return { run, isPending };
}
