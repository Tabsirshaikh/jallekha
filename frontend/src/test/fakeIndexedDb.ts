/**
 * The smallest IndexedDB stand-in the resident and field-worker queues need (jsdom has none):
 * open with upgrade, getAll and put on stores keyed by `id`. Rows are copied in and out.
 */
type Row = { id: string } & Record<string, unknown>;
type Request<T> = { result: T; error: null; onsuccess: (() => void) | null; onerror: (() => void) | null; onupgradeneeded?: (() => void) | null };

const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const later = (fn: () => void) => setTimeout(fn, 0);

export function fakeIndexedDb(seed: Record<string, Record<string, Row[]>> = {}) {
  const databases = new Map<string, Map<string, Map<string, Row>>>();
  for (const [name, stores] of Object.entries(seed)) {
    databases.set(name, new Map(Object.entries(stores).map(([store, rows]) => [store, new Map(rows.map((row) => [row.id, copy(row)]))])));
  }

  function database(stores: Map<string, Map<string, Row>>) {
    return {
      createObjectStore(store: string) {
        stores.set(store, new Map());
      },
      transaction(store: string) {
        const rows = stores.get(store) ?? new Map<string, Row>();
        stores.set(store, rows);
        const transaction = {
          oncomplete: null as (() => void) | null,
          onerror: null as (() => void) | null,
          error: null,
          objectStore() {
            return {
              getAll() {
                const request: Request<Row[]> = { result: [], error: null, onsuccess: null, onerror: null };
                later(() => {
                  request.result = [...rows.values()].map(copy);
                  request.onsuccess?.();
                });
                return request;
              },
              put(value: Row) {
                rows.set(value.id, copy(value));
                later(() => transaction.oncomplete?.());
              },
            };
          },
        };
        return transaction;
      },
    };
  }

  return {
    rows(name: string, store: string): Row[] {
      return [...(databases.get(name)?.get(store)?.values() ?? [])].map(copy);
    },
    open(name: string) {
      const request: Request<ReturnType<typeof database> | null> = { result: null, error: null, onsuccess: null, onerror: null, onupgradeneeded: null };
      later(() => {
        const existing = databases.get(name);
        const stores = existing ?? new Map<string, Map<string, Row>>();
        databases.set(name, stores);
        request.result = database(stores);
        if (!existing) request.onupgradeneeded?.();
        request.onsuccess?.();
      });
      return request;
    },
  };
}
