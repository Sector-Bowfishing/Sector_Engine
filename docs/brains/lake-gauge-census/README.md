# Lake gauge census (LGC-2026-11-23)

Status: tool and pre-registered rules only. **Nothing has been fetched.** No binding, accepted list, `LakeSourceBindingsGenerated.swift`,
knowledge release, score or rubric changes here.

## Why

Lake coverage is 294 of 621 directory lakes (47%). The `coverage` dimension of `lake-brain-score-v1` moves from 5 to 7 at 50%, which
needs 311 reviewed lakes (+17). The new lakes must be gauge-grade (`sourceCapability.level` `DIRECT_OPERATOR_POOL` or
`DIRECT_LAKE_GAUGE`), or they lower the `sourceAuthority` share. SWOT is excluded until decision R10.

The same pass also serves the operator-truth validation v3 (discovery-first, after PR #243 found only 7 lakes with independent truth):
for every bound lake it lists series that are **not** the lake's bound primary, fallback or history series, with independence evidence.

## Files

| File | What |
|---|---|
| [`LGC-2026-11-23.rules.json`](LGC-2026-11-23.rules.json) + `.sha256` | The pre-registered rules: hosts and terms, classification cues, stage A selection (S1–S9), independence tiers, stage B binding review (R1–R9, checks (b)–(d), the 15 ft history/live rule), the no-relaxation clause, and `notBefore` 2026-12-01 |
| [`MINI_REQUEST_DRAFT.md`](MINI_REQUEST_DRAFT.md) | Draft Sector_Ops #51 request for the Mac mini (not posted) |
| `tools/research/lake_gauge_census.py` | The census (GET only, metadata only) |
| `tools/research/tests/test_lake_gauge_census.py` + `fixtures/lake_gauge_census/world.json` | 18 offline tests on a synthetic world |

## How the census works

1. **Targets** (offline, committed files only): the 621 lakes of `brains/moon/runtime/knowledge/lakes-directory.json`; purpose `BINDING`
   for the 327 lakes outside the reviewed set; purpose `INDEPENDENT_TRUTH` for every lake with a binding (294 reviewed + 4 candidate
   rows). Bound series come from `LakeSourceBindingsGenerated.swift` and the five hand-written pilots. The sha256 of every input goes
   into the output.
2. **Outlines**: the public Lake Registry (`sector-lake-registry`, `registry/lakes.v1.json` and each lake's analysis outline). A lake
   with no outline is `POINT_ONLY`: its candidates can never be shortlisted, only sent to hand review (R1 cannot be evaluated).
3. **Positive controls** first: Allegheny Reservoir PA (USGS 03012520 62615, CWMS `Kinzua-Lake…RESOPS`), Bluestone Lake WV (USGS
   03179800 62614, CWMS `Bluestone-Lake…OBS`), Alcova Reservoir WY (RISE 114). A provider whose known series is not rediscovered as a
   pool is disabled for the whole run and reported (this catches an API shape change before it produces a silent zero).
4. **Discovery** per lake, inside the outline's bounding box plus 1.5 km:
   - USGS WaterServices site catalog for parameters 62614, 62615, 00062 (OGC API fallback when WaterServices fails);
   - CWMS Data API location catalog per district office, then the `Elev` time-series catalog (with extents) of each nearby location;
   - RISE locations, then their catalog items whose title names an elevation.
5. **Classification** from metadata: `POOL`, `TAILWATER`, `RIVER`, `RULE_CURVE` (guide/rule/forecast series, the 2026-11-21 trap) or
   `UNKNOWN`, from station names, CWMS sub-location / sub-parameter / version and the position against the outline.
6. **Freshness and cadence** from catalog extents; for shortlisted USGS pools, the last 12 h of instantaneous-value **time stamps**
   (values are dropped at parse time and never written or cached).
7. **Verdicts**: `BINDING` candidates get `SHORTLIST` / `HAND_REVIEW` / `REJECT` with the S-rule reasons; bound lakes' candidates get an
   independence tier (`INDEPENDENT_AGENCY`, `INDEPENDENT_SITE`, `UNCERTAIN`, `NOT_INDEPENDENT`) and `eligibleForV3`.

Safety: GET only; hosts allowlisted (USGS, USACE CDA, USBR RISE, the Lake Registry); `www.tva.com`, NWPS, HADS and SWOT are never
queried; robots.txt is honoured per host; 1 s between requests per host; a 9,000-request budget; writes only to `--out`.

## After the census

The census output is a shortlist, not a batch. The next binding batch is built after PR #243 has run, by the stage B rules in the
rules file (the same R1–R9 and checks (b)–(d) as batches 1 and 2), with level values read at that point. Any FAIL is held. The
≥ 311 target never changes a rule after values are seen.
