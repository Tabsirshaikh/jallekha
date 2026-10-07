// Where a tanker is at a minute of the day, from its trips in the approved plan: filling at its
// station, driving out, emptying the tank at the stop, or driving back to fill again. Shared by
// the officer's route map (PlanRoutes) and the driver's route simulation (DriverRouteSim).

/** Minutes to fill the tank at the station before each trip (ALLOCATION_CONFIG.fill_minutes). */
export const FILL = 20;

export const minute = (hhmm: string) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
export const clock = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`;

/** One trip as drawn: where it goes on the drawing and when (minutes after midnight). */
export type Leg = { x: number; y: number; dep: number; arr: number; unl: number; back: number; kind: number };
export type SpotState = "out" | "unload" | "back" | "fill";
/** `i`: which trip (index into the legs). */
export type Spot = { x: number; y: number; state: SpotState; kind: number; i: number };

/** Where a tanker is at minute `t`, or null before its day starts and after it ends. */
export function spotAt(trips: Leg[], home: [number, number], t: number): Spot | null {
  for (let i = 0; i < trips.length; i++) {
    const { x, y, dep, arr, unl, back, kind } = trips[i];
    if (t < dep - FILL) return null;
    if (t > back) continue;
    if (t < dep) return { x: home[0], y: home[1], state: "fill", kind, i };
    if (t < arr) { const f = (t - dep) / Math.max(1, arr - dep); return { x: home[0] + (x - home[0]) * f, y: home[1] + (y - home[1]) * f, state: "out", kind, i }; }
    if (t < unl) return { x, y, state: "unload", kind, i };
    const f = (t - unl) / Math.max(1, back - unl);
    return { x: x + (home[0] - x) * f, y: y + (home[1] - y) * f, state: "back", kind, i };
  }
  return null;
}
