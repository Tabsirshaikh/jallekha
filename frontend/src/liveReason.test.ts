import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import { canFetchOfficerData, liveReason } from "./liveReason";

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
