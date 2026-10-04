/** Reads the day's bookings from CSV text (pasted or from a file) for POST /plans.
 * Columns: booking_id, section, arrived_at (required); consumer_id, category, tier (optional).
 * Only the shape is checked here; the server checks the values (sections, time zones, categories)
 * and lists what is wrong. A column it does not know is reported, never silently dropped. */

export type BookingRow = { booking_id: string; section: string; arrived_at: string; consumer_id?: string; category?: string; tier?: number };

export type CsvProblem =
  | { code: "missingColumn"; name: string }
  | { code: "unknownColumn"; name: string }
  | { code: "rowShape"; line: number; expected: number; found: number }
  | { code: "badTier"; line: number };

const REQUIRED = ["booking_id", "section", "arrived_at"] as const;
const OPTIONAL = ["consumer_id", "category", "tier"] as const;

type Record = { cells: string[]; line: number };

/** Splits text into records, honouring double quotes (a quoted field may hold commas). */
function records(text: string): Record[] {
  const out: Record[] = [];
  let cells: string[] = [];
  let cell = "";
  let quoted = false;
  let line = 1;
  let start = 1;
  const push = () => {
    cells.push(cell);
    if (cells.some((value) => value.trim() !== "")) out.push({ cells, line: start });
    cells = [];
    cell = "";
  };
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    if (quoted) {
      if (char === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (char === '"') quoted = false;
      else {
        if (char === "\n") line++;
        cell += char;
      }
    } else if (char === '"') quoted = true;
    else if (char === ",") {
      cells.push(cell);
      cell = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && text[i + 1] === "\n") i++;
      push();
      line++;
      start = line;
    } else cell += char;
  }
  if (cell !== "" || cells.length > 0) push();
  return out;
}

export function parseBookingsCsv(raw: string): { rows: BookingRow[]; errors: CsvProblem[] } {
  const all = records(raw.replace(/^\uFEFF/, ""));
  if (all.length === 0) return { rows: [], errors: [] };
  const header = all[0].cells.map((name) => name.trim());
  const errors: CsvProblem[] = [];
  for (const name of REQUIRED) if (!header.includes(name)) errors.push({ code: "missingColumn", name });
  for (const name of header) if (!(REQUIRED as readonly string[]).includes(name) && !(OPTIONAL as readonly string[]).includes(name)) errors.push({ code: "unknownColumn", name });
  if (errors.length > 0) return { rows: [], errors };

  const rows: BookingRow[] = [];
  for (const record of all.slice(1)) {
    if (record.cells.length !== header.length) {
      errors.push({ code: "rowShape", line: record.line, expected: header.length, found: record.cells.length });
      continue;
    }
    const values = Object.fromEntries(header.map((name, index) => [name, record.cells[index].trim()]));
    const row: BookingRow = { booking_id: values.booking_id, section: values.section, arrived_at: values.arrived_at };
    if (values.consumer_id) row.consumer_id = values.consumer_id;
    if (values.category) row.category = values.category;
    if (values.tier) {
      if (!/^[012]$/.test(values.tier)) {
        errors.push({ code: "badTier", line: record.line });
        continue;
      }
      row.tier = Number(values.tier);
    }
    rows.push(row);
  }
  return { rows, errors };
}
