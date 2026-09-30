# JalLekha 2.0: team plan (4 people, new repository)

What to build and why: `docs/JALLEKHA_FINAL_SOLUTION.md`. Progress: `docs/features.csv` (one row per task, with owner, branch, dependencies and a done-when check).

## 1. Repository and branches

- Repository: https://github.com/Tabsirshaikh/jallekha (owner: Tabsirshaikh). All four people are collaborators.
- `main` is protected: no direct pushes, one approving review required.
- One short branch per task, named in `features.csv` (e.g. `feat/f1-atlas`). Pull request into `main`, one teammate reviews, merge, delete the branch.
- The old prototype (https://github.com/abhay-hanchate/jallekha) stays as it is (v1 reference). Nothing is merged between the two.

```
main ◄── PR ── feat/<task>   (one task per branch, small PRs, merge daily if possible)
```

## 2. Setup (each person, once)

```bash
git clone https://github.com/Tabsirshaikh/jallekha.git
cd jallekha
python tasks.py setup     # after S1 is merged: backend venv + frontend packages
python tasks.py test
```

## 3. Daily workflow

```bash
git checkout main && git pull
git checkout -b feat/<task-id>-<short-name>
# work, then
git add <files> && git commit -m "<task-id>: what changed"
git push -u origin feat/<task-id>-<short-name>
# every morning
git fetch origin && git merge origin/main
```

Finish: tests + lint pass → set the row to `IN_REVIEW` with the PR link → PR into `main` → review → merge → row `DONE`.

**Rules**
- Only touch files your task lists; ask the owner of another area for changes there.
- Config: each area has its own section (`config/evidence.py`, `config/allocation.py`, ...) so nobody edits the same file.
- One database table per model file.
- No hand-typed data; every derived column has a `_basis` column; synthetic data labelled on screen.
- Every service function has unit tests; routers stay thin.
- Numbers on slides come only from `data/verification/V-VERIFY_REVIEW.md`.

## 3a. How to push your work and merge it into main (step by step)

**1. Start from the latest main**
```bash
git checkout main
git pull origin main
git checkout -b feat/<task-id>-<short-name>      # e.g. feat/e1-crosswalk
```
In `docs/features.csv` set your row's `status` to `IN_PROGRESS`.

**2. Commit small, push often (at least once a day)**
```bash
git status                                  # see what changed
git add <only the files you changed>        # never "git add ." blindly
git commit -m "E1: census crosswalk with location check"
git push -u origin feat/e1-crosswalk        # first push; later just: git push
```

**3. Keep your branch up to date with main (every morning, and before opening a PR)**
```bash
git fetch origin
git merge origin/main
```
If Git reports a conflict: open each conflicted file, keep the correct lines, delete the `<<<<<<<`, `=======`, `>>>>>>>` markers, then
```bash
git add <fixed files>
git commit            # completes the merge
python tasks.py test  # make sure nothing broke
git push
```
If the conflict is in someone else's area, ask them before choosing.

**4. Open a pull request**
1. `python tasks.py test` and `python tasks.py lint` pass on your machine.
2. On GitHub: **Pull requests → New pull request**, base = `main`, compare = your branch.
3. Title: `<task-id>: <what it does>`. Description: what you built, how you tested it (command + result), data used and its basis, anything not done.
4. In `features.csv` set `status` to `IN_REVIEW` and paste the PR link in `pr` (commit this on your branch).
5. Request a review from one teammate (for research notes: one teammate + the owner).

**5. Review**
- Reviewer checks: done-when in `features.csv` is met, tests exist and pass, no hand-typed data, only the task's files changed, synthetic data labelled.
- Reviewer comments or approves. The author fixes comments with new commits on the same branch and pushes; the PR updates by itself.

**6. Merge**
- After approval (and CI green), the **author** clicks **Squash and merge** on GitHub, then **Delete branch**.
- Then everyone updates:
```bash
git checkout main
git pull origin main
git branch -d feat/e1-crosswalk     # delete your local copy
```
- Set the row's `status` to `DONE` (in your next PR, or a one-line PR).

**Never:** push directly to `main`, force-push a shared branch, merge your own PR without a review, or commit secrets, `.env` files, databases, `node_modules/` or virtual environments.

## 4. Who builds what

| Person | Area | Features |
|---|---|---|
| **P1** | Data and evidence | F1 Atlas, F2 growth adjustment, F3 Booking Equity + coverage map, F4 under-served detector, data fetches |
| **P2** | Allocation and simulation | F7 service models, F8 fair queue, F9 scheduled supply, F10 outage, F11 water debt, routing, F19 sandbox |
| **P3** | Forecast, access and trust backend | F5 forecast, F6 shortage warning, F12 delivery proof, F13 duplicates, F14 intake + voice, F15 notices, F16 explanations + contest, F17 confidence, F18 ledger, API |
| **P4** | Frontend and demo | Officer console, resident app, driver app, field-worker mode, i18n (te, ur, hi, en), F20 report cards, Impact page, docs, demo |

### Step 0 for everyone: research before building (rows R-P1 to R-P4)

Before writing any feature code, each person re-researches **their own features** from scratch, even where the solution document already gives an answer. The goal is to find a more accurate dataset or a better-proven method, not to confirm what is written.

For each feature you own:
1. **Data sources:** search for newer, finer-grained or more official data than the one listed (government portals, National Water Data Portal, data.gov.in, OpenCity, Census/NADA, HDX, Earth Engine, OSM, RTI replies, research datasets). Download a sample and check it: coverage of Hyderabad, date, licence, whether it can be read by code.
2. **Methods:** search papers (Google Scholar, arXiv, Semantic Scholar) and open-source repos for how others solved the same problem; prefer methods with published evaluation and working code. Check that each paper the solution cites says what we claim.
3. **Existing systems:** how other cities or utilities do it (Bengaluru, Chennai, Delhi, Pune, international).
4. **Write it down** in `docs/research/<your-id>.md` (max 2 pages): for each feature, sources checked (link + date), what you found, and a decision **keep / change / add** with the reason. Every claim needs a link.
5. **Review:** open a PR with the note; one teammate and the owner review it. Changes to the solution document go in the same PR. Build only after it is merged.

Time box: 2 days. Stop earlier if nothing better is found; "no better source found" with the list of what you checked is a valid result.

| Person | Research focus |
|---|---|
| **P1** | Newer ward-level population and water-access data (post-2011 surveys, GHMC/HMWSSB open data, NFHS, slum lists), 2009-to-2016 ward crosswalk sources, building/population rasters (Open Buildings, WorldPop, GHS-POP), section boundaries, spatial under-reporting models (BYM2, Agostini et al.) |
| **P2** | Fair scheduling and allocation methods (deficit round robin, max-min, fair allocation with routing, humanitarian deprivation cost), real filling-station locations and fleet data, tanker booking practice in other cities, how to evaluate against FCFS |
| **P3** | Demand forecasting on short monthly series, conformal intervals, groundwater/reservoir data, duplicate detection and multilingual text similarity, Telugu/Urdu speech recognition, OTP delivery-proof practice, explanation and contest methods |
| **P4** | Accessible low-literacy and multilingual UI (Telugu, Urdu RTL), offline-first PWAs, IVR/missed-call/SMS patterns, field-worker apps, how public dashboards show data quality and uncertainty |

**Week 0 (day 1-2, shared):** R-P1 to R-P4 research (everyone, in parallel), S1 skeleton (P3), S2 port verified data (P1), S3 port v1 modules with tests (P2), S4 design system + app shells (P4). Setup tasks (S1-S4) may run alongside research; feature tasks start only after the owner's research note is merged. Everyone waits for S1 before other PRs.

### P1 order
R-P1 research → S2 → D-fetch (boundaries, Open Buildings, groundwater, OSM filling points) → E1 wards + Census crosswalk → E2 ward evidence table (**others wait for this: merge early**) → E3 growth adjustment → E4 booking equity → E5 under-served detector → E6 coverage map.

### P2 order
R-P2 research → S3 → A1 booking replay (no dependency) → A2 service models + need weights → A3 fair queue → A4 scheduled supply + routing → A5 outage response → A6 water debt (needs T3) → A7 daily planner → A8 sandbox.

### P3 order
R-P3 research (S1 in parallel) → T1 duplicate engine (no dependency) → T2 forecast + backtest → T3 delivery proof → T4 intake + voice → T5 notices → T6 ledger → T7 explanations + contest → T8 shortage warning → T9 confidence → T10 API for all screens (agree JSON shapes with P4 in week 1).

### P4 order
R-P4 research → S4 → U1 i18n te/ur/hi/en (no dependency) → U2 resident app + offline → U3 field-worker mode → U4 driver app → U5 Atlas / Equity / Under-served screens → U6 forecast + shortage screen → U7 plan screen (queue, schedule, sliders, confidence tick) → U8 explanations + contest → U9 Impact page with badges → U10 ward report cards → X1 docs + demo.

Screens are built against JSON fixtures in the agreed shape first, then switched to the API.

## 5. Dependencies

```
R-P1..R-P4 ─► each person's feature tasks
S1 ─► everyone
D-fetch ─► E1 ─► E2 ward evidence ─► E3, E4, E5, A2, T7, T9, U5
A1 + A3 + A4 + T1 ─► A8 sandbox ─► T9 threshold, U9
T3 delivery outcomes ─► A6 debt ─► A7 planner ─► U7
T2 forecast ─► T8 shortage ─► U6
T10 API ─► all real (non-fixture) screens
```

## 6. Timeline (4 weeks)

| Week | Goal |
|---|---|
| 1 | Research notes R-P1 to R-P4 merged (days 1-2); S1-S4 merged; data fetched; E1-E2 merged; A1, T1, U1 done; API shapes agreed |
| 2 | E3-E5, A2-A4, T2-T4 merged; screens on fixtures |
| 3 | E6, A5-A7, T5-T8 merged; screens on the real API; U7-U8 |
| 4 | A8, T9-T10, U9-U10, X1; full test + lint; demo rehearsal; release tag |

## 7. Open decisions (owner)

- Q1: which filling points to show (OSM stand-ins are ASSUMED).
- Q2: whether reservoir levels are used (only if a machine-readable source is verified).
