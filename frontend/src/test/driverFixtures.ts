/** Driver API responses in the real T10 shapes (copied from a running API with fake data). */
import type { DeliveryView, LocationCheck, StopView } from "../driverAdapter";

export const stop: StopView = {
  stop_id: "E2E-STOP-1", lat: 17.385, lon: 78.4867, basis: "SYNTHETIC",
  representatives: [{ id: "R1", language: "te", phone_last2: "01" }, { id: "R2", language: "en", phone_last2: "02" }],
  representatives_count: 2, residents_count: 3,
};

export const stopsPage = { total: 1, offset: 0, limit: 200, items: [stop] };

export function delivery(id: string, patch: Partial<DeliveryView> = {}): DeliveryView {
  return {
    delivery_id: id, stop_id: "E2E-STOP-1", driver_id: "drv-1", started_at: "2026-10-04T15:20:34.312247Z", geofence_radius_m: null,
    otp_issued: false, otp_expires_at: null, otp_digits: null, wrong_attempts: 0, outside_tries: 0, otp_verified: false,
    sampled_residents: 0, replies: 0, outcome_status: "pending", outcome: null, ...patch,
  };
}

export const issued: Partial<DeliveryView> = { otp_issued: true, otp_expires_at: "2026-10-04T15:30:34.611741Z", otp_digits: 6 };

export const inside: LocationCheck = { status: "inside", inside: true, distance_m: 11.1, radius_m: 150, reason: null };
export const outside: LocationCheck = { status: "outside", inside: false, distance_m: 1667.9, radius_m: 150, reason: null };
export const noLocation: LocationCheck = { status: "no_location", inside: false, distance_m: null, radius_m: 150, reason: null };

export const confirmedOutcome = {
  outcome_status: "Confirmed" as const,
  outcome: { outcome: "Confirmed" as const, rule: "majority", otp_verified: true, yes: 3, no: 0, silent: 0, basis: "SYNTHETIC" },
  counts_toward_debt: true,
  otp_verified: true,
  sampled_residents: 3,
  replies: 3,
};

/** Never rendered: the representatives' full numbers as registered in the test stop. */
export const registeredPhones = ["+919000000001", "+919000000002", "9000000001", "9000000002"];
