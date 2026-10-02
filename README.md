# JalLekha 2.0

Fair, explainable sharing of tanker water in Hyderabad, built only on data that exists. Built for **PS11: Community Water-Supply Allocation and Complaint Intelligence**.

JalLekha measures water need independently of requests (Census water access, building growth), compares it with who actually gets tankers (real HMWSSB bookings), and recommends a fair allocation of limited tankers by need, previous service and fairness over time. Every decision is explained, contestable and logged.

> Status: planning. The code is built from scratch by a team of four; see the team plan.

## Documents

| File | What it is |
|---|---|
| [docs/JALLEKHA_FINAL_SOLUTION.md](docs/JALLEKHA_FINAL_SOLUTION.md) | The solution: problem, PS11 mapping, research, data sources, features F1-F20, architecture, evaluation, limits |
| [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md) | Who builds what, research step, branches, how to push and merge, timeline |
| [docs/features.csv](docs/features.csv) | Task tracker: owner, branch, dependencies, done-when, status |
| [docs/BRANCH_WORKLOG.md](docs/BRANCH_WORKLOG.md) | Per-branch findings, changes, validation, limitations and handoffs |


## Developer setup

Python 3.11+ and Node.js 22+ are required. Commands work in Windows PowerShell and POSIX shells.

```bash
python tasks.py setup
python tasks.py test
python tasks.py lint
```

Run the API with `.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload` on Windows, or the equivalent `.venv/bin/python` path on POSIX. Run the frontend with `npm run dev --prefix frontend`.

## Three layers

| Layer | Features | Data |
|---|---|---|
| A. Evidence | Water Access Atlas, growth adjustment, Booking Equity + coverage map, under-served detector, surge forecast, shortage early warning | Real (HMWSSB, Census 2011, OSM, Open Buildings, groundwater, weather) |
| B. Allocation | Service models, fair queue, scheduled supply, outage response, water debt in litres | Real rules; daily demand synthetic, calibrated to real monthly totals |
| C. Trust and access | Delivery proof, duplicate engine, multilingual voice/SMS/offline intake, supply notices, explanations + contest, confidence gate, tamper-evident ledger, policy sandbox, ward report cards | Real code; delivery events synthetic and labelled |

## Team workflow (short)

1. Research your features first (`docs/research/<id>.md`), get it reviewed.
2. One branch per task: `feat/<task-id>-<name>` from `main`.
3. Push, open a pull request into `main`, one teammate reviews, squash and merge.
4. Add a focused CI workflow named `<owner>:<task-id>`, update `docs/features.csv`, and document findings, changes, validation, limitations and handoff in `docs/BRANCH_WORKLOG.md`.

Full steps: [docs/TEAM_PLAN.md](docs/TEAM_PLAN.md).

## Previous prototype

v1 (reference only): https://github.com/abhay-hanchate/jallekha
