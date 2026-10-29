"use client";

import { useEffect, useRef, useState } from "react";

export function useWidth<T extends HTMLElement>(initial = 800) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    if (!ref.current) return;
    const obs = new ResizeObserver(([entry]) => setWidth(Math.max(260, entry.contentRect.width)));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, width] as const;
}

export function usePolling<T>(load: (signal: AbortSignal) => Promise<T>, everyMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () =>
      load(ctrl.signal)
        .then((d) => { setData(d); setError(null); })
        .catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); })
        .finally(() => setLoading(false));
    setLoading(true);
    tick();
    const timer = everyMs > 0 ? setInterval(tick, everyMs) : undefined;
    return () => { ctrl.abort(); clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}
