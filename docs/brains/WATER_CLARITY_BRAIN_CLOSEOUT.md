# Water Clarity Brain: closeout (2026-10-12)

**Branch** `brain/water-clarity`, public-safe, based on tag `deployed/sector-engine-00072-way` (the live Engine).
**Not merged. Not deployed.**

## Status

Water Clarity Brain v1.1.0 publishes production Clarity to Brain RTDB `sector-brain` as semantic facts. Sector Ops owns all labels.
- Design: `WATER_CLARITY_BRAIN_INTEGRATION.md` (§0 is the contract, §17 the public/private split).
- Field map: `WATER_CLARITY_BRAIN_MAPPING.md`.

**Last publish:** 2026-10-12 06:52Z, manual run from the Mac.
- 621 / 621 lakes, 0 failures, HEALTHY.
- Readiness: 18 PRODUCTION, 603 BETA.

**Tests:** 35 unittest cases, no network: `cd jobs/water-clarity-brain && python3 -m unittest discover -s tests`. They include public-safety checks on `catalog.json`.

## Public vs private

- This branch holds the runtime, contracts, tests and status-level candidate facts:
  - R3.1: CANDIDATE / CERTIFIED / NOT_DEPLOYED;
  - S2C FULL only on the `r3-usgs-aqr` path; LOWER on `r0-acolite-l1c`.
- Detailed research results are not in this repo. They live in:
  - the gitignored `catalog.private.json`;
  - the private research store (`gs://sector-clarity-candidate`).
- The publisher merges the overlay when it is available.

## Depends on

| Dependency | Why |
|---|---|
| `fix/water-temp-shown-scored` (= `deployed/sector-engine-00072-way`) | Base: the live Engine |
| Output of the production lake-surface job (`feat/clarity-algal-warning`) | Read from its public bucket |
| Sector_Ops `main` | Brain contract and Clarity panels |
| Private research store | Overlay source; optional at runtime |

## Deploy (not done; Michael's go)

`jobs/water-clarity-brain/deploy-job.sh`:
- creates the service account;
- creates the Cloud Run job;
- schedules it at 04:30 CT.

To publish the certification detail, the job also needs read access to the private overlay object (`CLARITY_PRIVATE_CATALOG=gs://…`).

## Known limitations / open

- **Strong:** every lake is NOT_EVALUATED, because production has no consensus model.
- **Unknown fields:** `clarityClass` is null; gauge reading times are unknown.
- **Load:** `/conditions` is called 621 times per run.
- **IAM:** RTDB IAM is project-wide.
- **Publisher duplication:** there are three Brain RTDB publishers (Water Temp in Swift, Wind in Python, Clarity in Python). Consolidate later.
