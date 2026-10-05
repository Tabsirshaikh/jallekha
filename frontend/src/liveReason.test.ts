import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { canFetchOfficerData, canFetchWardCard, liveReason, wardCardReason } from "./liveReason";

describe("liveReason", () => {
  it("asks for sign-in, a new token or an officer role before any request", () => {
    expect(liveReason("anonymous", null, null)).toBe("signIn");
    expect(liveReason("rejected", null, null)).toBe("rejected");
    expect(liveReason("signed-in", "driver", null)).toBe("notOfficer");
    expect(liveReason("unreachable", null, null)).toBe("unreachable");
    expect(liveReason("checking", null, null)).toBeNull();
  });

  it("explains a failed request for a signed-in officer", () => {
    expect(liveReason("signed-in", "officer", null)).toBeNull();
    expect(liveReason("signed-in", "officer", new ApiError(401, "unauthorized", "x"))).toBe("rejected");
    expect(liveReason("signed-in", "officer", new ApiError(403, "forbidden", "x"))).toBe("notOfficer");
    expect(liveReason("signed-in", "officer", new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(liveReason("signed-in", "officer", new ApiError(500, "internal_error", "x"))).toBe("error");
  });

  it("only fetches for a signed-in officer", () => {
    expect(canFetchOfficerData("signed-in", "officer")).toBe(true);
    expect(canFetchOfficerData("signed-in", "resident")).toBe(false);
    expect(canFetchOfficerData("checking", null)).toBe(false);
  });
});

describe("ward card access", () => {
  it("fetches for a signed-in officer, resident or councillor only", () => {
    expect(canFetchWardCard("signed-in", "officer")).toBe(true);
    expect(canFetchWardCard("signed-in", "resident")).toBe(true);
    expect(canFetchWardCard("signed-in", "councillor")).toBe(true);
    expect(canFetchWardCard("signed-in", "driver")).toBe(false);
    expect(canFetchWardCard("signed-in", "field_worker")).toBe(false);
    expect(canFetchWardCard("anonymous", null)).toBe(false);
    expect(canFetchWardCard("checking", "resident")).toBe(false);
  });

  it("explains why the ward card is not live", () => {
    expect(wardCardReason("anonymous", null, null)).toBe("signIn");
    expect(wardCardReason("rejected", null, null)).toBe("rejected");
    expect(wardCardReason("unreachable", null, null)).toBe("unreachable");
    expect(wardCardReason("checking", null, null)).toBeNull();
    expect(wardCardReason("signed-in", "driver", null)).toBe("notOfficer");
    expect(wardCardReason("signed-in", "resident", null)).toBeNull();
    expect(wardCardReason("signed-in", "resident", new ApiError(401, "unauthorized", "x"))).toBe("rejected");
    expect(wardCardReason("signed-in", "resident", new ApiError(403, "forbidden", "x"))).toBe("notOfficer");
    expect(wardCardReason("signed-in", "councillor", new ApiError(0, "network_error", "x"))).toBe("unreachable");
    expect(wardCardReason("signed-in", "officer", new ApiError(500, "internal_error", "x"))).toBe("error");
  });
});
