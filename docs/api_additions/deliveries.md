# API additions: stops, delivery list, persistent delivery store (Wave 1, agent B)

To be merged into `docs/api_shapes.md` section 13 by the lead. `docs/openapi.json` must be
regenerated (`python scripts/api/export_openapi.py`): the new paths are `/stops`,
`/stops/{stop_id}` and `GET /deliveries`, and the `Start` body of `POST /deliveries` now has
length limits.

## What changed for the existing delivery routes

- Stops and delivery states are now kept in the database (`backend/app/services/delivery_store.py`),
  not in memory. A delivery survives a server restart; a reloaded state is equal to the one saved.
- `POST /deliveries` answers 404 only when the stop is really not registered (`POST /stops` first).
- Response shapes of `POST /deliveries`, `POST /deliveries/{id}/otp`, `.../otp/verify`,
  `.../replies` and `GET /deliveries/{id}` are unchanged.
- `POST /deliveries` body: `delivery_id` 1-36 characters, `stop_id` and `driver_id` 1-64
  characters (database column widths); longer values give 422 `validation_error`.

Tables (created by `create_all`, no migration needed for an empty database):

| Table | New? | Holds |
|---|---|---|
| `delivery_stop` | new | `stop_id` (unique), `lat`, `lon`, `basis` (REAL / SYNTHETIC) |
| `representative` | existing | one row per representative: `id`, `stop_id`, `phone`, `language`, `active`, `basis` |
| `resident` | new | `stop_id`, `resident_id` (unique per stop), `phone`, `language`, `basis` |
| `delivery` | existing | one row per delivery; `id` = `delivery_id`; OTP as nonce + hash only |
| `delivery_roster` | new | the delivery's representatives (copied at start) and sampled residents, in order, with the order replies were counted |
| `resident_response` | existing | one row per sampled resident; `answer` empty while silent |
| `delivery_outcome` | existing | the decided outcome, once |

Phone numbers are stored only in `representative.phone` and `resident.phone`. The plain OTP is
never stored; its nonce and hash only in `delivery.otp_nonce` / `delivery.otp_code_hash`.

## `POST /stops`

- **Built from:** `services/delivery_store.py` `DeliveryStore.put_stop`
- **Roles:** officer
- **Request:** JSON body. Unknown fields are rejected.

| Field | Type | Rule |
|---|---|---|
| `stop_id` | string | 1-64 characters, letters, digits and `. _ : -` only |
| `lat` | number | -90 to 90 |
| `lon` | number | -180 to 180 |
| `representatives` | array | 2-3 items (F12; `TRUST_CONFIG.delivery_representatives_min/max`) |
| `representatives[].id` | string | 1-36 characters, same character set; unique within the stop and not used by any other stop |
| `representatives[].phone` | string | E.164: `+` then 8-15 digits, no spaces (`STOP_CONFIG.phone_pattern`) |
| `representatives[].language` | string | `en`, `te`, `ur` or `hi` (`ACCESS_CONFIG.supported_languages`) |
| `residents` | array | at most 500 items; at least 3 residents whose id is not a representative id (F12 samples 3-5) |
| `residents[].id` | string | 1-64 characters, same character set; unique within the stop |
| `residents[].phone` | string | E.164 as above; unique within the stop (replies are matched on the last 10 digits) |
| `residents[].language` | string | as above |
| `basis` | string | `REAL` or `SYNTHETIC` |

- **Response (200):** the stop view (below).
- **Errors:** 401 `unauthorized` (no or bad token), 403 `forbidden` (not an officer),
  409 `conflict` (stop id already registered, or a representative id already used),
  422 `validation_error` with `details: [{loc, msg, type}]`. The submitted values are never
  echoed in an error (they may be phone numbers).

### Stop view

| Field | Type | Notes |
|---|---|---|
| `stop_id` | string | |
| `lat` | number | |
| `lon` | number | |
| `basis` | string | `REAL` or `SYNTHETIC` |
| `representatives` | array | in id order |
| `representatives[].id` | string | what the driver sends as `representative_id` to request the OTP |
| `representatives[].language` | string | |
| `representatives[].phone_last2` | string | last 2 digits of the number only, to tell representatives apart |
| `representatives_count` | integer | |
| `residents_count` | integer | residents are never listed |

No phone number appears in any stop response.

## `GET /stops`

- **Roles:** officer, driver
- **Request:** query `offset` (>= 0, default 0), `limit` (1-200, default 50)
- **Response (200):** `{total, offset, limit, items: [stop view]}`, in `stop_id` order
- **Errors:** 401, 403, 422 (bad paging)

## `GET /stops/{stop_id}`

- **Roles:** officer, driver
- **Response (200):** the stop view
- **Errors:** 401, 403, 404 `not_found`

## `GET /deliveries`

- **Built from:** `DeliveryStore.list_deliveries`, then T3 `close_delivery` per delivery (as
  `GET /deliveries/{id}` does: an outcome that can be decided now is decided and saved first)
- **Roles:** officer, driver
- **Request:** query `driver_id`, `stop_id` (exact match, optional), `outcome_status`
  (`pending` | `Confirmed` | `Disputed` | `Unconfirmed` | `Failed`, optional), `offset`
  (>= 0, default 0), `limit` (1-200, default 50)
- **Response (200):** `{total, offset, limit, items}`; deliveries in start order; each item has
  the same fields as the `POST /deliveries` response (`delivery_id`, `stop_id`, `driver_id`,
  `started_at`, `geofence_radius_m`, `otp_issued`, `otp_expires_at`, `otp_digits`,
  `wrong_attempts`, `outside_tries`, `otp_verified`, `sampled_residents`, `replies`,
  `outcome_status`, `outcome`). `total` counts after the filters.
- **Errors:** 401, 403, 422 (unknown `outcome_status`, bad paging)
