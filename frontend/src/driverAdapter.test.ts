import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { driverMode, fallbackForError, newDeliveryId, outcomeKey } from "./driverAdapter";

describe("driverAdapter", () => {
  it("makes delivery ids D-<yyyymmdd>-<8 hex> that fit the 36-character column", () => {
    const id = newDeliveryId(new Date(2026, 9, 4, 9, 30), () => "0a1b2c3d");
    expect(id).toBe("D-20261004-0a1b2c3d");
    const random = newDeliveryId();
    expect(random).toMatch(/^D-\d{8}-[0-9a-f]{8}$/);
    expect(random.length).toBeLessThanOrEqual(36);
    expect(newDeliveryId()).not.toBe(random);
  });

  it("goes live only for a signed-in driver or the dev token", () => {
    expect(driverMode("signed-in", "driver")).toBe("live");
    expect(driverMode("signed-in", "dev")).toBe("live");
    expect(driverMode("signed-in", "officer")).toBe("notDriver");
    expect(driverMode("anonymous", null)).toBe("signIn");
    expect(driverMode("rejected", null)).toBe("signIn");
    expect(driverMode("unreachable", null)).toBe("unreachable");
    expect(driverMode("checking", null)).toBe("loading");
  });

  it("explains a failed request in plain terms", () => {
    expect(fallbackForError(new ApiError(401, "unauthorized", "x"))).toBe("signIn");
    expect(fallbackForError(new ApiError(403, "forbidden", "x"))).toBe("notDriver");
    expect(fallbackForError(new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(fallbackForError(new ApiError(500, "internal", "x"))).toBe("serverError");
  });

  it("maps the four server outcomes to their labels and leaves pending undecided", () => {
    expect(outcomeKey("Confirmed")).toBe("confirmed");
    expect(outcomeKey("Disputed")).toBe("disputed");
    expect(outcomeKey("Unconfirmed")).toBe("unconfirmed");
    expect(outcomeKey("Failed")).toBe("failed");
    expect(outcomeKey("pending")).toBeNull();
  });
});
