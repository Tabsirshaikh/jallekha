import type { SectionCategory } from "./planAdapter";

// Colours and plain names shared by the plan-by-section visuals (maps, queue, routes).

export const CATEGORY: Record<SectionCategory, { colour: string; label: string; meaning: string }> = {
  cut: { colour: "#2f6fb0", label: "Water cut today", meaning: "A supply-cut notice covers this section today, so it gets emergency water first: hospitals, then every home up to the minimum." },
  scheduled: { colour: "#d08a2e", label: "Water on a schedule", meaning: "Books far fewer tankers than similar sections nearby, so water is sent anyway without waiting for bookings." },
  heavy: { colour: "#7b5ea7", label: "Books many tankers", meaning: "Among the top quarter of sections for tankers booked per 1,000 homes: the pipes fall short here. Served from the booking queue." },
  normal: { colour: "#9cc9b6", label: "Books now and then", meaning: "Pipes mostly enough; books a tanker now and then. Served from the booking queue." },
  unknown: { colour: "#e3e6e2", label: "Not enough data", meaning: "No count of water connections, so its type cannot be judged." },
};
/** Priority classes of a booking (F8): hospitals first, then homes with no water at home, then fair turns. */
export const TIER = [
  { colour: "#c4473a", label: "Hospitals and care homes", short: "Hospital" },
  { colour: "#dba32b", label: "Homes with no water at home", short: "No water at home" },
  { colour: "#1f7560", label: "Everyone else, in fair turns", short: "Fair turn" },
] as const;
export const REASON_TIER: Record<string, number> = { TIER_0: 0, TIER_1: 1, DRR: 2, FCFS: 2 };

/** Kinds of tanker load on the routes (KINDS order of route_schedule.compact_paths). */
export const KINDS = ["booked", "scheduled", "outage", "critical"] as const;
export const KIND: Record<string, { colour: string; label: string }> = {
  booked: { colour: "#1f7560", label: "Booked" },
  scheduled: { colour: "#d08a2e", label: "Water on a schedule" },
  outage: { colour: "#2f6fb0", label: "Water cut" },
  critical: { colour: "#c4473a", label: "Hospital in a water cut" },
};
