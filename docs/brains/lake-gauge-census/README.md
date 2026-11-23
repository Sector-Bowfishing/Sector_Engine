# Lake gauge census (LGC-2026-11-23.5)

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
| [`LGC-2026-11-23.5.rules.json`](LGC-2026-11-23.5.rules.json) + `.sha256` (`befcc41d…`) | **Current** pre-registered rules (committed alone, before the code that follows them), including the run binding and origin-evidence registration; hosts and terms, classification cues, stage A selection (S1–S9), independence tiers and the unlabelled-CWMS border rule, stage B binding review (R1–R9, checks (b)–(d), the 15 ft history/live rule), the no-relaxation clause, and `notBefore` 2026-12-01T12:00Z |
| [`LGC-2026-11-23.4.rules.json`](LGC-2026-11-23.4.rules.json) + `.sha256` | Fourth registration, kept byte for byte, **superseded and never used** ([why](LGC-2026-11-23.4.SUPERSEDED.md)); the tool refuses it |
| [`LGC-2026-11-23.3.rules.json`](LGC-2026-11-23.3.rules.json) + `.sha256` | Third registration, kept byte for byte, **superseded and never used** ([why](LGC-2026-11-23.3.SUPERSEDED.md)); the tool refuses it |
| [`LGC-2026-11-23.2.rules.json`](LGC-2026-11-23.2.rules.json) + `.sha256` | Second registration, kept byte for byte, **superseded and never used** ([why](LGC-2026-11-23.2.SUPERSEDED.md)); the tool refuses it |
| [`LGC-2026-11-23.rules.json`](LGC-2026-11-23.rules.json) + `.sha256` | First registration, kept byte for byte, **superseded and never used** ([why](LGC-2026-11-23.SUPERSEDED.md)); the tool refuses it |
| [`MINI_REQUEST_DRAFT.md`](MINI_REQUEST_DRAFT.md) | Draft Sector_Ops #51 request for the Mac mini (not posted) |
| `tools/research/lake_gauge_census.py` | The census (GET only, metadata only) |
| `tools/research/lake_census_run_ledger.py` | The run ledger (hash-chained, append-only). A local copy with the same shape as the Wind run ledger; it will be replaced by the shared `tools/research/protocol_run_ledger.py` once that PR merges |
| `tools/research/tests/test_lake_gauge_census.py` + `fixtures/lake_gauge_census/world.json` | 107 offline tests on a synthetic world (plus `tva_robots.txt`, TVA's `Disallow: /` file) |

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
5. **Classification** from metadata: `POOL`, `TAILWATER`, `RIVER`, `RULE_CURVE` or `UNKNOWN`, from station names, CWMS
   sub-location / sub-parameter / version, RISE item titles and the position against the outline. Guide, curve, rule, plan, target,
   forecast, conservation, flood, control, inflow, upper, lower, top, bottom in a version, sub-parameter or item title mean a plan
   series (the 2026-11-21 trap), and so does a latest time in the future. A CWMS sub-location Upper/Lower is UNKNOWN.
6. **Freshness and cadence** from catalog extents; for the BINDING pre-shortlist only (USGS POOL rows passing S1–S3 and S6), the
   last 12 h of instantaneous-value **time stamps** (values are dropped at parse time and never written or cached).
7. **Verdicts**: `BINDING` candidates get `SHORTLIST` / `HAND_REVIEW` / `REJECT` with the S-rule reasons; bound lakes' candidates get an
   independence tier (`INDEPENDENT_AGENCY`, `INDEPENDENT_SITE`, `UNCERTAIN`, `NOT_INDEPENDENT`) and `eligibleForV3`.

**Independence is conservative.** A CWMS version that names USGS, USBR (or BOR / Reclamation) or CDEC (or DWR) is a copy of that
agency's gauge (`USGS_COPY`, `USBR_COPY`, `CDEC_COPY`): NOT_INDEPENDENT when the lake already has a bound series of that agency,
UNCERTAIN otherwise. A version that names NWS/NWPS/HADS is a redistribution. Any other CWMS version is `USACE_UNLABELLED`: its origin is
unknown, because districts publish other agencies' gauges under their own version names. **Any pair with an unlabelled CWMS series on
either side is `UNCERTAIN`**, including two unlabelled series (both can derive from one upstream sensor, and CWMS location coordinates
are not sensor coordinates). Two CWMS series with the same base location (`Kinzua-Lake`, `Kinzua-Tailwater`, `Kinzua`) are
`NOT_INDEPENDENT`; a derived version (Best, Rev, Comp, Calc, CCP) is a derivation (NOT_INDEPENDENT at the same base, UNCERTAIN
otherwise). A RISE item is USBR only when its own metadata names Reclamation; otherwise it is `RISE_UNCONFIRMED` (RISE republishes
other agencies' data), which, like an unlabelled CWMS series, is origin-unknown against every family: `UNCERTAIN` in either direction.
Derived versions match by substring (Rev2, Revised, Computed, Calc1), and base locations compare case-insensitively. Only an entry in a reviewed origin-evidence file
(`--origin-evidence`: USACE for a CWMS series, e.g. a USACE sensor id or a documented non-USGS DCP; USBR for a RISE item) changes
that, and only when the file's sha256 is listed in the rules or registered with `register-evidence` before census run #1. Evidence
for a series whose version already names an agency is refused. None exists yet.

**Run binding.** `controls` and `census` take `--research-folder` (the Lake research folder; or `SECTOR_RESEARCH_ROOT`), never `--out`.
The binding for a rules id is `<research folder>/gauge-census/binding/<rulesId>/`: a hash-chained, append-only `ledger.jsonl`, the
shared metadata cache, and write-once run folders (`controls-run-<n>/`, `census-run-<n>/`). Only census run #1 counts: a run that
ends before writing anything is ABORTED_NO_RESULT and may be retried (with `--skip-controls` only if its controls passed); a
COMPLETED or FAILED run blocks every later one. The START line records every argument, the tool and rules hashes, the input hashes,
the registry source and the cache tree hash; the END line records the output hashes, the registry index and outline hashes, the
cache tree hash after the run and the request, retry and cache-hit counts. Cache hits are lines in `requests.jsonl`.

**Structural cap for v3.** A bound lake whose binding includes a TVA, NWPS or HADS gauge has no coordinates for that gauge, so every
candidate there is `UNCERTAIN`. From the committed bindings, only **130 of 298** bound lakes (129 of 294 reviewed) can get an
`INDEPENDENT_*` row at all, and the border rule lowers that further for lakes bound to unlabelled CWMS series. The census reports the
live figure (`summary.structuralCap`). Bound RISE items take their coordinates from the RISE locations already fetched.

Safety: GET only; hosts allowlisted (USGS, USACE CDA, USBR RISE, the Lake Registry); `www.tva.com`, NWPS, HADS and SWOT are never
queried; no request before 2026-12-01T12:00Z (in the fetcher, so every subcommand); redirects never followed; robots.txt per RFC 9309
(401/403/429, 5xx, a redirect or no answer = disallow, recorded `ROBOTS_DISALLOWED` per path); `tva.com`, NWPS and HADS are refused by the fetcher even if a rules file listed them (TVA's robots.txt is `Disallow: /`); 1 s between requests per host; every retry counts against a
12,000-request budget; a failed request, chunk or lake is recorded under `errorsByStage` and the run still writes its output
(`budgetExhausted` says when it stopped early). A failed CWMS office catalog is never cached as empty: it is retried for the next lake
(at most 3 failures per office), and every lake discovered while it was down is marked `CWMS_OFFICE_UNAVAILABLE`. **Every discovery failure marks
the lake incomplete**, never "no candidate": `PROVIDER_FAILED`, `PROVIDER_DISABLED` (failed positive control), `USGS_BOX_TOO_LARGE`,
`USGS_TSMETA_UNAVAILABLE`, `CWMS_OFFICE_UNAVAILABLE`, `CWMS_LOCATIONS_TRUNCATED`, `CWMS_TS_UNAVAILABLE`, `CWMS_TS_TRUNCATED`,
`RISE_CATALOG_UNAVAILABLE` / `_PARTIAL` / `_TRUNCATED`, `RISE_DETAIL_UNAVAILABLE`, `RISE_ITEM_UNAVAILABLE`, `GEOMETRY_UNAVAILABLE`,
`USGS_OGC_TRUNCATED`, `USGS_SITE_ERROR` (a WaterServices 404 counts as empty only with its well-formed "No sites found" body),
`USGS_SITE_NO_COORDINATES`, `CWMS_LOCATION_NO_COORDINATES`, `RISE_LOCATION_NO_COORDINATES`. A failed or partial RISE
listing is never cached (retried, at most 3 failures). BINDING counts keep `noCandidate` (complete discovery, nothing found) apart
from `incomplete` and `notDiscovered` (budget). Writes only to `--out`.

## After the census

The census output is a shortlist, not a batch. The next binding batch is built after PR #243 has run, by the stage B rules in the
rules file (the same R1–R9 and checks (b)–(d) as batches 1 and 2), with level values read at that point. Any FAIL is held. The
≥ 311 target never changes a rule after values are seen.
