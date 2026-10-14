# Wind — recommended production envelope, deploy and rollback path (prepared; NOTHING deployed)

## Recommended production envelope (if exposure validates; surface optional)
- Provider wind (speed, direction, forecast gust) with source, units and age: ready now.
- Bank guidance only inside the NORMAL OPERATING ENVELOPE: sustained forecast 5-12 mph, forecast age <= 6 h, geometry AUDITED or ESTIMATED (never POINT_ONLY), bank not below resolution. Outside: "Use caution" / "Not enough information".
- Words: Protected / Moderately exposed / Exposed; confidence capped at "medium" until exposure is VALIDATED; surface words only if surface passes; otherwise withheld.
- Strong-event claims stay NOT_VALIDATED / LIMITED; gust shown as a forecast with "runs low in strong wind".

## What the hourly job does (audit)
`wind-hourly` (`5 * * * *`): archive NBM / RTMA / METAR (the prospective evidence, kept) then Brain publish: 4 lake states, registry, validation, sources, health, activity. This branch removes the only large avoidable write: fleet rows for ~600 non-live lakes are no longer rewritten hourly (live lakes plus changed readiness each run, full refresh every 24 h). Bank-detail rewrites are skipped when the input fingerprint is unchanged. Archive and prediction preservation untouched.

## Deploy path (needs explicit approval; the Wind deployment is currently a PREREQUISITE BRANCH item)
Live: `wind-hourly` generation 4, image `sha256:410e7c46c57b98f3f8ce9a2a3bee1f8694587d9122020ba375dd7126854a2746`, build `main@e6a5026f5d0f`, scheduler `5 * * * *`. Deploy script: `jobs/wind-hourly/deploy-job.sh`.
Before deploying: (1) `pytest` green (156 on this branch); (2) confirm base lineage includes the current shared platform (do not deploy around newer shared lineage); (3) one manual execution with `--args` dry/`hourly` and check the log line `windbrain {"ok": true ...}` and `fleetPathsWritten`; (4) confirm `/scores/wind` still 3.3 and the registry now carries `scores.canonicalRef`; (5) Sector Ops should prefer the canonical score first so the Wind Brain page never blanks.
## Rollback
Redeploy the previous image: `gcloud run jobs update wind-hourly --region us-central1 --image <previous sha above>`; scheduler untouched; archive keeps accruing during and after. Rollback is a documented, mechanical step; it has NOT been exercised because no deploy was authorised.

## Reliability gate automation
`reliability_gate.py` (inside the existing hourly publish) evaluates the 30-day prospective gate once, on or after 2026-11-07, records the verdict at `brain/wind/reliability_gate.json` and raises one activity event. **It only runs if the new code is deployed before then** (the live job is an older build). If it is not deployed, the weekly `run_cycle.py` still shows the same dimension; see DECISION_QUEUE D7.
