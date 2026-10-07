# Bookings, driver routes and SMS test mode (feat/booking-flow)

The chain booking -> plan -> tanker -> delivery code -> water debt, end to end.

## `GET /bookings/locate?lat=&lon=` (resident, field worker, officer, driver)
Which section (and ward) a point is in, so the booking form shows it before sending:
`{inside, section, section_name, ward_id, ward_name, basis}`. Sections are the approximate
section areas (DERIVED; HMWSSB publishes no boundaries). Outside every section: `inside: false`.

## `POST /bookings` (resident, field worker) -> 201
Body: `lat`, `lon`, `category` (home | apartment | hospital | care_home | school | commercial),
`water_at_home` (yes | no | unknown), `phone` (E.164), `language` (en | te | ur | hi), optional
`channel` (app | field_worker), `facility_name` (required for hospital, care home, school),
`basis` (REAL | SYNTHETIC). The server decides the section from the location (422 outside every
section). One open booking per phone number (409). A hospital, care home or school is a claim
(`claim_status: CLAIMED`) planned like a home until an officer verifies it.
Priority (`tier`): verified hospital or care home 0; verified school or no water at home 1;
others 2. The answer is the booking view below; the phone number is never returned (only
`phone_last2`) and never written to the ledger (`booking_created` carries id, section,
category, tier).

## `GET /bookings/{booking_id}` (resident, field worker, officer, driver)
Booking view: `booking_id`, `arrived_at`, `section`, `section_name`, `ward_id`, `lat`, `lon`,
`category`, `facility_name`, `water_at_home`, `claim_status`, `tier`, `priority` (plain words),
`status` (WAITING, EXPIRED after 3 days, ASSIGNED, ON_THE_WAY, CHECKING, DELIVERED,
NOT_CONFIRMED, CANCELLED; the last five read from its delivery), `plan_id`, `tanker_id`,
`station_id`, `trip_n`, `depart`, `arrive`, `delivery` (`delivery_id`, `otp_issued`,
`otp_verified`, `asked_residents`, `replies`, `outcome`, `counts_toward_debt`) or null,
`phone_last2`, `channel`, `basis`.

## `GET /bookings[?day=&status=&claim=&section=]` (officer)
Booking views, newest first, paged, plus `claims_to_check`.

## `POST /bookings/{booking_id}/claim` (officer)
`{decision: VERIFIED | REJECTED, officer_id, reason}`; 409 for a home booking. Logged
(`booking_claim_checked`, reason as SHA-256).

## Plans by section and approval
`POST /plans` with `unit: "section"` takes the bookings that still wait on the day (made before
the day ended, within the 3-day expiry): a section with real bookings is planned from them alone,
the others from the month's totals divided by days. Days from 2025 on are allowed; a day after
2025 uses the same month of 2025 (labelled in `basis.plan`). The plan id hashes the real
bookings, so a new booking makes a new plan. `overview.facts` has `live_bookings` and
`live_sections`; each section row has `live`.
`POST /plans/{id}/approve` on a plan by section gives every served real booking its tanker, trip
and times (route_schedule) and a delivery stop `bk-<booking_id>` at the booking's location, whose
only representative (`bk-<booking_id>-rep`) and only resident (`booker`) is the booker. Logged
`booking_assigned`. A booking stop needs one representative instead of 2-3.
`POST /debt/days/{day}/close` with a plan by section now owes each section the plan's own
bookings that arrived that day (the real ones where a section has them).

## `GET /driver/tankers?day=` and `GET /driver/route?day=&tanker_id=` (driver, officer)
From the day's approved plan by section (404 if none): the tankers carrying real bookings
(`tanker_id`, `station_id`, `trips`, `real_bookings`, `first_depart`), and one tanker's trips
(`n`, `kind`, `name`, `depart`, `arrive`, `back`, `km`, `leg_basis`, `booking` view or null,
`stop_id`). Estimated loads have no booking and need no delivery code.

## SMS test mode: `GET /sms/test-mode`, `GET /sms/outbox?phone=`, `POST /sms/outbox/reply`
Only with `SMS_PROVIDER=outbox` and without sign-in (`AUTH_REQUIRED` unset); otherwise 404 and
`test_mode: false`. Messages are kept in the server's memory and never sent. The outbox lists the
messages to a number (newest first, with the `code` of a delivery-code message); a reply
`{phone, text: "1" | "2"}` answers the latest open "did you get water?" question asked of that
number, as the SMS gateway would. No real SMS provider exists yet (owner decision).
