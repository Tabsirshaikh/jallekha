import { useCallback, useEffect, useState } from "react";
import { ApiError, apiFetch, onTokenChange } from "./api";

export type ApiState<T> = {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  /** True only when `data` was just served by the API. Screens show their labelled snapshot otherwise. */
  live: boolean;
  reload: () => void;
};

type Settled<T> = { key: string; data: T | null; error: ApiError | null };

/** GET `path` and keep the result; pass `null` to stay idle. Refetches when the path or token changes. */
export function useApi<T>(path: string | null): ApiState<T> {
  const [version, setVersion] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const key = path === null ? null : `${path}|${version}`;

  useEffect(() => onTokenChange(() => setVersion((v) => v + 1)), []);

  useEffect(() => {
    if (key === null || path === null) return;
    const controller = new AbortController();
    apiFetch<T>(path, { signal: controller.signal })
      .then((data) => setSettled({ key, data, error: null }))
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        const error = cause instanceof ApiError ? cause : new ApiError(0, "network_error", "The server could not be reached");
        setSettled({ key, data: null, error });
      });
    return () => controller.abort();
  }, [key, path]);

  // A result only counts for the request that produced it; anything else is still loading.
  const current = settled !== null && settled.key === key ? settled : null;
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return {
    data: current?.data ?? null,
    error: current?.error ?? null,
    loading: key !== null && current === null,
    live: current !== null && current.error === null && current.data !== null,
    reload,
  };
}
