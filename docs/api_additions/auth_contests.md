# API additions: identity, councillor role, contest read routes

For the lead to fold into `docs/api_shapes.md` (sections 1 and 11). Errors use the shared shape
`{"error": {"code", "message", "details"}}`. All ids in examples are synthetic.

## 1. Token-bound identity

`API_TOKENS` is a comma-separated list of `role:token[:user_id]` pairs. The user id is optional,
so existing values keep working.

```
API_TOKENS=officer:<token>:officer-demo-01,resident:<token>:resident-demo-01,driver:<token>
```

- Roles: `officer`, `driver`, `resident`, `field_worker`, `councillor` (councillor: OPEN, owner to
  confirm).
- A user id starts with a letter and uses letters, digits, `_`, `.` or `-` (at most 64
  characters), so it can never be a phone number.
- A malformed pair (unknown role, empty token, empty or invalid user id) is ignored: its token is
  not accepted at all, rather than accepted with the wrong identity.
- The dev token (`API_DEV_TOKEN`) has role `dev` and no user id. Tokens without a user id behave
  as before.

### `GET /auth/me`

Any valid user-role token (including the dev token). The token is never echoed; the gateway
credential is not a user.

```json
{ "role": "resident", "user_id": "resident-demo-01" }
```

`user_id` is `null` for a token without one. Dev token: `{"role": "dev", "user_id": null}`.
Errors: 401 without a valid token.

## 2. Councillor role

| Route | councillor |
| --- | --- |
| `POST /contests` | yes (files as itself) |
| `GET /contests`, `GET /contests/{id}` | yes, own contests only |
| `GET /explain/wards/{id}`, `GET /explain/bookings/{id}` | yes (wherever residents may) |
| `GET /wards/{id}/report-card`, `GET /wards/{id}/sms-summary` | yes (wherever residents may) |
| `POST /contests/{id}/reply` | no, 403 (officer only) |
| `POST /plans/{id}/approve` and every other officer-only route | no, 403 |
| `POST /intake/batch` | no (unchanged: resident, field_worker) |

## 3. `POST /contests` (changed behaviour)

Callable by `resident` and `councillor` (and the dev token); `driver` / `field_worker` get 403.

- If the token carries a user id, `filed_by` defaults to it. A different `filed_by` in the body is
  403 `forbidden`.
- For a token without a user id, and for the dev token, `filed_by` is taken from the body as
  before (missing or invalid: 422).
- The stored `role` is the caller's role (`resident` or `councillor`). A `role` in the body is
  ignored. The dev token keeps using the body's `role`.
- Response unchanged (`{status, contest_id, reply_id, ledger_seq, error}`).

## 4. `GET /contests`

Roles: `officer`, `resident`, `councillor` (and dev). Newest first.

Query: `status` (`open` | `replied`), `target_type` (`ward` | `booking`), `target_id`, `offset`
(default 0), `limit` (default 50, max 200). An unknown `status` / `target_type` is 422.

- Officer and dev token: every contest, with the filters.
- Resident and councillor: only contests whose `filed_by` is the token's user id (the same
  filters apply inside that set). There is no `filed_by` parameter. A resident or councillor
  token without a user id cannot be identified and gets 403 `forbidden`.

```json
{
  "total": 1,
  "offset": 0,
  "limit": 50,
  "items": [
    {
      "contest_id": "1e030438-fcb3-4f50-ac47-d8baec77a857",
      "created_at": "2026-10-03T05:00:00+00:00",
      "filed_by": "resident-demo-01",
      "role": "resident",
      "target_type": "ward",
      "target_id": "relation/7848799",
      "reason_code": "need_data_wrong",
      "reason_text": "Our lane has no tap connection; the ward figure looks too low.",
      "status": "open"
    }
  ]
}
```

`reason_text` is the text as stored: the service already replaced phone-like digit runs with
`[number removed]` when the contest was filed. No phone numbers are stored or returned.

## 5. `GET /contests/{contest_id}`

Roles: `officer`, `resident`, `councillor` (and dev). Officer and dev: any contest. Resident and
councillor: only their own; someone else's contest and an unknown id are both 404 `not_found`
(a token without a user id: 403). Returns the item above plus `reply`:

```json
{
  "contest_id": "1e030438-fcb3-4f50-ac47-d8baec77a857",
  "status": "replied",
  "...": "other contest fields as in the list item",
  "reply": {
    "reply_id": "bddaa77e-58c9-4dc9-8cb9-93b071a32111",
    "created_at": "2026-10-03T06:00:00+00:00",
    "officer_id": "officer-7",
    "outcome_code": "ranking_stands",
    "reason_text": "Census 2011 shows piped water for most households; field check scheduled."
  }
}
```

`reply` is `null` while the contest is open. Times are ISO 8601 UTC.
