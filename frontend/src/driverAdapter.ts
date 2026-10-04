/**
 * Shapes and small rules for the driver screen's live mode (F12 delivery proof, T10 routes
 * `/stops` and `/deliveries`; checked against a running API). No phone number, OTP, nonce or
 * hash is ever part of these shapes: the server does not send them.
 */
import type { ApiError } from "./api";
import type { AuthStatus } from "./auth";

export type Paged<T> = { total: number; offset: number; limit: number; items: T[] };

export type StopRepresentative = { id: string; language: string; phone_last2: string };

export type StopView = {
  stop_id: string;
  lat: number;
  lon: number;
  basis: "REAL" | "SYNTHETIC";
  representatives: StopRepresentative[];
  representatives_count: number;
  residents_count: number;
};

export type OutcomeStatus = "pending" | "Confirmed" | "Disputed" | "Unconfirmed" | "Failed";
export type Outcome = "confirmed" | "disputed" | "unconfirmed" | "failed";

export type DeliveryView = {
  delivery_id: string;
  stop_id: string;
  driver_id: string;
  started_at: string;
  geofence_radius_m: number | null;
  otp_issued: boolean;
  otp_expires_at: string | null;
  otp_digits: number | null;
  wrong_attempts: number;
  outside_tries: number;
  otp_verified: boolean;
  sampled_residents: number;
  replies: number;
  outcome_status: OutcomeStatus;
  outcome: { outcome: OutcomeStatus; rule: string; otp_verified: boolean; yes: number; no: number; silent: number; basis: string } | null;
  /** Only on `GET /deliveries/{id}`: null until the outcome is decided. */
  counts_toward_debt?: boolean | null;
};

export type VerifyResult = "verified" | "already_verified" | "wrong_code" | "expired" | "locked" | "outside_geofence" | "invalid_location" | "no_otp";

export type LocationCheck = {
  status: "inside" | "outside" | "no_location" | "invalid_location";
  inside: boolean;
  distance_m: number | null;
  radius_m: number | null;
  reason: string | null;
};

export type VerifyResponse = { result: VerifyResult; location: LocationCheck; delivery: DeliveryView };

/** Why the screen shows its sample route instead of live stops. */
export type DriverFallback = "signIn" | "notDriver" | "unreachable" | "serverError";

function randomHex(): string {
  const bytes = new Uint8Array(4);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Client-made delivery id `D-<yyyymmdd>-<8 hex>` (19 characters; the column holds 36). */
export function newDeliveryId(now: Date = new Date(), random: () => string = randomHex): string {
  const day = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`;
  return `D-${day}-${random()}`;
}

/** Live only for a signed-in driver (or the local dev token, which the server lets act as any role). */
export function driverMode(status: AuthStatus, role: string | null): "live" | "loading" | DriverFallback {
  if (status === "checking") return "loading";
  if (status === "unreachable") return "unreachable";
  if (status !== "signed-in") return "signIn";
  return role === "driver" || role === "dev" ? "live" : "notDriver";
}

export function fallbackForError(error: ApiError): DriverFallback {
  if (error.status === 401) return "signIn";
  if (error.status === 403) return "notDriver";
  if (error.status === 0) return "unreachable";
  return "serverError";
}

export function outcomeKey(status: OutcomeStatus): Outcome | null {
  return status === "pending" ? null : (status.toLowerCase() as Outcome);
}
