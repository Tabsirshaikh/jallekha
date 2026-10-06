# Section field observations (F4 ground truth)

Officer and field-worker bearer tokens can use all four routes:

- `GET /field-checks/sections?offset=0&limit=200`: flagged exact sections with the latest
  ledger-linked `latest_outcome` for that section/year, or null. Section source fields retain
  their basis labels. This list is for visits; it cannot change allocation or entitlement.
- `POST /field-checks/outcomes`: `{id: UUID, section_id, could_not_book: "yes" | "no" | "unclear",
  checked_on: "YYYY-MM-DD", note: string}`. Date cannot be in the future in Asia/Calcutta;
  note is at most 2,000 characters [ASSUMED]. Only current flagged section identities are accepted.
  The response is the saved observation (REAL self-report), including `recorded_by`,
  `note_sha256`, `screening_sha256`, and `ledger_missing`.
- `GET /field-checks/outcomes?offset=0&limit=200`: saved observations, newest visit date first.
- `GET /field-checks/summary`: distinct section/year outcomes, decisive yes/no count,
  unclear count, pending ledger count, precision or null, and minimum sample [ASSUMED: 30].

The latest dated ledger-linked visit per section/year counts. Repeated visits do not add
independent observations; unclear outcomes are excluded from the precision denominator.
Precision is yes / (yes + no), only after 30 distinct decisive outcomes. It measures visited
flags only, not recall, city-wide access, or an unbiased sample. There are 12 current flags,
so this release cannot yet reach 30 independent outcomes. No outcomes are seeded as real.

Notes remain in `section_check_outcome`; the new ledger event `section_check_recorded`
holds identifiers, outcome/date and SHA-256 digests, never note text. A failed ledger append
leaves the observation pending; it is excluded from precision. Retry the identical UUID/body
to link it. A reused UUID with different answers is rejected. An already-linked entry is reused
on recovery after an interrupted save. `screening_sha256` identifies the server flag at entry.

Bind tokens to user IDs (`role:token:user_id`) for person-level attribution. Unbound tokens
record the authenticated role; clients cannot supply a claimed recorder identity.
The table is registered in SQLAlchemy and created automatically; no migration is introduced.

U3 and U5 share the same form, four-language text and live service. Signed-out users can see
the saved screening data but cannot submit observations. Officer overview counts exact sections,
and visited section cards show the latest result. Data/API retain basis labels, screens use words.
