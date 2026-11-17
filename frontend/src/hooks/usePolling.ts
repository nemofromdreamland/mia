import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

const INTERVAL_MS = 2000;
const OFFLINE_INTERVAL_MS = 5000;
const FAILURES_BEFORE_OFFLINE = 3;

type PollingOptions<T> = { enabled: boolean; onData: (data: T) => void };

/**
 * Calls `fn` every 2 s while enabled and the tab is visible (Design section 7.2).
 * After 3 network failures in a row: `offline = true` and 5 s between calls,
 * until the first good response.
 */
export function usePolling<T>(fn: () => Promise<T>, options: PollingOptions<T>): { offline: boolean } {
  const { enabled } = options;
  const [offline, setOffline] = useState(false);
  const fnRef = useRef(fn);
  const onDataRef = useRef(options.onData);

  useEffect(() => {
    fnRef.current = fn;
    onDataRef.current = options.onData;
  });

  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    let active = true;

    const schedule = () => {
      clearTimeout(timer);
      if (!active || document.hidden) return;
      const delay = failures >= FAILURES_BEFORE_OFFLINE ? OFFLINE_INTERVAL_MS : INTERVAL_MS;
      timer = setTimeout(tick, delay);
    };

    const tick = async () => {
      try {
        const data = await fnRef.current();
        if (!active) return;
        failures = 0;
        setOffline(false);
        onDataRef.current(data);
      } catch (err) {
        if (!active) return;
        if (err instanceof ApiError && err.code === "network") {
          failures += 1;
          if (failures >= FAILURES_BEFORE_OFFLINE) setOffline(true);
        }
      }
      schedule();
    };

    const onVisibility = () => (document.hidden ? clearTimeout(timer) : schedule());

    document.addEventListener("visibilitychange", onVisibility);
    schedule();
    return () => {
      active = false;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [enabled]);

  return { offline };
}
