/** A small `overview` of a plan by section in the real shape (plan_overview.py), for the new panels. */
export const overviewRaw = {
  facts: {
    day: "2025-05-15", capacity_scenario: "tight", bookings: 120, carried: 20, commercial: 30, tiers: [4, 10, 106], served_tiers: [4, 10, 66],
    served: 80, waiting: 40, trips: 100, fleet_tankers: 1150, trips_per_tanker: 9, reserve_trips: 5, reserve_used_trips: 3, outage_trips: 0,
    booked_trips: 95, scheduled_sections: 1, cut_sections: 0, critical_stops: 0, stations: 2, load_litres: 5000, litres_per_person: 15,
  },
  sections: [
    { group: "section:KONDAPUR (DIV 15)", name: "KONDAPUR (DIV 15)", category: "heavy", bookings: 90, carried: 15, tiers: [4, 8, 78], served_tiers: [4, 8, 48], served: 60, waiting: 30, bookings_per_1000: 2000, peer_bookings_per_1000: 1500, station: "ST01", need_estimated: false, no_water_share: 0.25, fair_share: 9000, scheduled: null, outage: null, critical_litres: 0 },
    { group: "section:MADHAPUR -2", name: "MADHAPUR -2", category: "normal", bookings: 30, carried: 5, tiers: [0, 2, 28], served_tiers: [0, 2, 18], served: 20, waiting: 10, bookings_per_1000: 300, peer_bookings_per_1000: 400, station: "ST01", need_estimated: false, no_water_share: 0.24, fair_share: 4000, scheduled: null, outage: null, critical_litres: 0 },
    { group: "section:BALANAGAR", name: "BALANAGAR", category: "scheduled", bookings: 0, carried: 0, tiers: [0, 0, 0], served_tiers: [0, 0, 0], served: 0, waiting: 0, bookings_per_1000: 119, peer_bookings_per_1000: 997, station: "ST02", need_estimated: false, no_water_share: 0.07, fair_share: 0, scheduled: { litres: 45101, people: 3007, litres_per_person: 15, loads: 9, full: true }, outage: null, critical_litres: 0 },
  ],
  stations: [
    { station_id: "ST01", trips: 80, booked_trips: 80, bookings: { "section:KONDAPUR (DIV 15)": 90, "section:MADHAPUR -2": 30 } },
    { station_id: "ST02", trips: 20, booked_trips: 15, bookings: {} },
  ],
  categories: { heavy_cutoff: 1361.8, heavy_percentile: 75 },
  basis: {},
};

/** Station rows of the plan view whose `served` lists give the queue order. */
export const stationsRaw = [
  { station: "ST01", trips: 80, served: [
    { booking_id: "a", group: "section:KONDAPUR (DIV 15)", position: 1, reason: "TIER_0", lender: null },
    { booking_id: "b", group: "section:MADHAPUR -2", position: 2, reason: "TIER_1", lender: null },
    { booking_id: "c", group: "section:KONDAPUR (DIV 15)", position: 3, reason: "DRR", lender: null },
  ] },
];
