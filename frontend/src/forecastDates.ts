import type { ShortageRow } from "./forecastAdapter";

type Window = { origin: string; from: string; through: string };
function index(month: string) { const [year, number] = month.split("-").map(Number); return year * 12 + number - 1; }
function month(value: number) { return `${Math.floor(value / 12)}-${String(value % 12 + 1).padStart(2, "0")}`; }

export function warningWindow(now = new Date()): Window {
  const parts = new Intl.DateTimeFormat("en", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit" }).formatToParts(now);
  const origin = `${parts.find(p => p.type === "year")!.value}-${parts.find(p => p.type === "month")!.value}`;
  // F6 design: warn for the next three calendar months, measured from today.
  return { origin, from: month(index(origin) + 1), through: month(index(origin) + 3) };
}

export function currentWarnings(rows: ShortageRow[], window: Window): ShortageRow[] {
  return rows.filter(row => row.month >= window.from && row.month <= window.through)
    .map(row => ({ ...row, monthsAhead: index(row.month) - index(window.origin) }));
}
