import { describe, expect, it } from "vitest";
import { parseBookingsCsv } from "./bookingsCsv";

const HEADER = "booking_id,section,arrived_at";

describe("parseBookingsCsv", () => {
  it("reads the required columns and trims the values", () => {
    const { rows, errors } = parseBookingsCsv(`${HEADER}\nB-1, ADARSHNAGAR ,2026-10-03T05:30:00+05:30\nB-2,BAHADURPURA,2026-10-03T06:00:00+05:30\n`);
    expect(errors).toEqual([]);
    expect(rows).toEqual([
      { booking_id: "B-1", section: "ADARSHNAGAR", arrived_at: "2026-10-03T05:30:00+05:30" },
      { booking_id: "B-2", section: "BAHADURPURA", arrived_at: "2026-10-03T06:00:00+05:30" },
    ]);
  });

  it("takes the optional columns, turns the tier into a number and leaves empty cells out", () => {
    const { rows, errors } = parseBookingsCsv(`booking_id,section,arrived_at,consumer_id,category,tier\nB-1,X,2026-10-03T05:30:00+05:30,c-1,commercial,0\nB-2,X,2026-10-03T05:31:00+05:30,,,\n`);
    expect(errors).toEqual([]);
    expect(rows[0]).toEqual({ booking_id: "B-1", section: "X", arrived_at: "2026-10-03T05:30:00+05:30", consumer_id: "c-1", category: "commercial", tier: 0 });
    expect(rows[1]).toEqual({ booking_id: "B-2", section: "X", arrived_at: "2026-10-03T05:31:00+05:30" });
  });

  it("handles quoted fields with commas, a byte order mark, Windows line ends and blank lines", () => {
    const text = `\uFEFF${HEADER}\r\n\r\nB-1,"BIG, SECTION (DIV 3)",2026-10-03T05:30:00+05:30\r\n`;
    const { rows, errors } = parseBookingsCsv(text);
    expect(errors).toEqual([]);
    expect(rows).toEqual([{ booking_id: "B-1", section: "BIG, SECTION (DIV 3)", arrived_at: "2026-10-03T05:30:00+05:30" }]);
  });

  it("says which required column is missing", () => {
    expect(parseBookingsCsv("booking_id,section\nB-1,X").errors).toEqual([{ code: "missingColumn", name: "arrived_at" }]);
  });

  it("says which column it does not know instead of ignoring it", () => {
    const { errors } = parseBookingsCsv(`${HEADER},catagory\nB-1,X,2026-10-03T05:30:00+05:30,x`);
    expect(errors).toEqual([{ code: "unknownColumn", name: "catagory" }]);
  });

  it("names the line of a row with the wrong number of values", () => {
    const { rows, errors } = parseBookingsCsv(`${HEADER}\nB-1,X,2026-10-03T05:30:00+05:30\nB-2,X\n`);
    expect(errors).toEqual([{ code: "rowShape", line: 3, expected: 3, found: 2 }]);
    expect(rows).toHaveLength(1);
  });

  it("names the line of a tier that is not 0, 1 or 2", () => {
    const { errors } = parseBookingsCsv(`${HEADER},tier\nB-1,X,2026-10-03T05:30:00+05:30,7\nB-2,X,2026-10-03T05:30:00+05:30,two`);
    expect(errors).toEqual([{ code: "badTier", line: 2 }, { code: "badTier", line: 3 }]);
  });

  it("gives no rows and no errors for empty text", () => {
    expect(parseBookingsCsv("  \n ")).toEqual({ rows: [], errors: [] });
  });
});
