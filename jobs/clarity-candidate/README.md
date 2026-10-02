# Current Clarity candidate — shadow job (UNCERTIFIED)

Runs the frozen Current Clarity candidate (`research/clarity-candidate`) on every new Sentinel-2 pass over 17 pilot
lakes. It records the candidate beside what production shows, so later agency data and scoring-only field reports can
score both without guesswork.

**It never touches production:**
- It writes only to the private bucket `gs://sector-clarity-candidate` (public access prevention enforced).
- It reads no field report.
- No score, map or bowfisher-facing surface reads its output.

| | |
|---|---|
| **Stage 16 (baseline)** | Frozen ACOLITE path (K4, lake-elevation pressure, M0/M3, 60 m disk) → frozen C-gbm → posterior gate 0.70 / 0.70, tier-2 boundary-only, S2C lower authority, algal modifier (`engine16.answer16`, unchanged) |
| **Stage 17 (challenger)** | Frozen inverse-uncertainty consensus over ±10 days (`challenger17.py`, a port checked against the frozen `dev17` outputs on all 1,582 development events), computed when neighbouring scenes exist |
| **Production** | The published Water Clarity layer at the point for that pass (`gs://sector-lake-surface`, `secchi-power-v1` feet: what the app shows), and the same model on the production-gated Sen2Cor disk at the point (`stage6/extract.py`) |

## Every run checks itself first

Each task compares the environment and engine against the frozen outputs. Any difference means that task writes
nothing but its failure record (`runs/<execution>/selfcheck-task<k>.json`). The checks:
- the package set, the ACOLITE commit and tree, and the 269 LUT hashes;
- 134 research-file hashes;
- engine14 on 1,574 certification rows and engine16 on 108 fresh rows (0 differences);
- the challenger port on 1,582 frozen fixtures;
- ACOLITE golden scenes: all six on task 0, one on every other task. Each runs on the machine that then processes new
  scenes, max |difference| 0.

## What it writes (`gs://sector-clarity-candidate/shadow/v1/`)

| Path | Contents |
|---|---|
| `scenes/<lake>/<item>.json` | One per Earth Search L2A item. Per point: production (layer + disk), the Stage 16 output (tier, state, display, feet shown, posterior, authority, evidence, algal flag and NDCI, S2C flag, interval), the raw inputs (M0/M3 samples, Sen2Cor read-out, sun elevation, platform), the L1C name, and the version hashes |
| `log/<lake>.json` | The shadow log: one row per point and item, with production, Stage 16 and Stage 17 side by side |
| `latest/<lake>.json` | Each point's latest pass and latest usable pass, plus a lake summary. The engine's `/clarity/candidate` serves this |
| `runs/<execution>/` | Self-check results and each task's summary |

**Version hashes in every record:**
- the frozen files (`FREEZE_STAGE18.json`);
- the ACOLITE path files;
- the Sen2Cor read-out;
- the ACOLITE commit and LUT lock;
- the production model;
- this job's commit and files.

## The challenger and duplicate acquisitions

**What frozen means here.** The frozen Stage 17 rule picks neighbours by unique Earth Search item. One satellite pass
can appear as several items:
- **overlapping tiles:** different L1C files, the same pixels;
- **datastrip twins:** one L1C split into two items.

In the frozen research, 399 of 1,215 development events (33%) had a neighbour that was the anchor's own pass seen
through another item. So part of Stage 17's apparent consensus was one observation counted twice.

**`stage17`** is the challenger exactly as frozen, duplicates included.

**`stage17_one_per_pass`** is a diagnostic, not a frozen rule. It is the same challenger with one scene per satellite
pass (satellite + day), keeping the best-read item.

**Before any adoption decision,** compare the two on live data.

**Live windows are one-sided.** A pass sees itself and the 10 days before it; same-day items see each other. Every
scene is stored, so the research's two-sided window can be rebuilt for scoring.

**ACOLITE runs once per L1C and crop.** A datastrip twin reuses the samples, which are identical by construction.

## Pilot lakes

`pilot_lakes.json` is built by `build_pilot.py` from the lake outlines only, and the selection is by environment. No
model output, Secchi value or field report enters it.

| Lake | Why |
|---|---|
| Guntersville AL | The 42 Stage 10 survey targets, so the scoring-only acceptance survey has candidate answers at its exact points |
| Okeechobee FL, Pontchartrain LA, Toledo Bend TX, Marion SC | Subtropical, estuarine, tannic and blackwater |
| Texoma TX, Ouachita AR, Ozarks MO, Lanier GA | Red clay, clear oligotrophic, Ozark and Piedmont |
| Winnebago WI, Mille Lacs MN, Champlain VT | Eutrophic natural lake, glacial, deep and clear |
| Sakakawea ND, Utah Lake UT, Elephant Butte NM, Mead NV, Clear Lake CA | Plains sediment, alkaline turbid, desert reservoirs, hypereutrophic |

Every lake except Guntersville has five points: the open water farthest from shore, then up to four more at least 300 m
from shore and 1.5 km apart, all inside one ACOLITE crop.

## Cost

Over the last 30 days the pilot lakes had about 13.7 Sentinel-2 L1C acquisitions a day.

- **Downloads:** about 0.48 GB each without the TCI preview. With the golden checks, that is roughly 6–7 GB of new scenes
  plus about 9 GB of checks a day.
- **Download cost:** the public L1C bucket is EU multi-region and not requester-pays. The Sen2Cor COGs are AWS Open
  Data. So downloads cost Sector about $0.
- **Compute:** about 1 hour of 2 vCPU / 8 GiB task time a day, roughly **$0.20 a day** (about $6 a month) at Cloud
  Run's list price. Guntersville is about 60% of it (4 tiles, 10 crops).
- **Storage:** under $0.10 a month.

## Where it runs (decision pending)

**On Linux x86-64 the frozen candidate is not bit-exact.** The Cloud Run image passes every environment check, and every
decision is identical. But the numeric fields differ in the last bits:
- engine `p`/`feet`: at most 1.6e-15 relative;
- ACOLITE: one float32 ulp on Intel AVX-512 hosts.

See `research/clarity-candidate/provenance/CROSS_PLATFORM_REPRODUCTION.md`.

**So the cloud job fails closed:** it writes nothing, and its schedule is paused. Two ways forward, Michael's call:
1. **A declared tolerance** for the cloud: decisions identical, numeric within 1e-12 relative, ACOLITE within 1e-8.
2. **The exact host:** `run-on-mac.sh` runs the same job on macOS arm64, where every check is exact.

## Deploy, run, stop

```bash
./jobs/clarity-candidate/deploy-job.sh                                  # image, job, schedule (07:00 CT daily)
gcloud run jobs execute clarity-candidate-shadow --region us-central1 --update-env-vars LOOKBACK_DAYS=20   # backfill
gcloud scheduler jobs pause clarity-candidate-shadow --location us-central1                               # stop
```

Local run (no bucket): `CLARITY_RESEARCH_ROOT=<bootstrapped research dir> <root>/geo/bin/python shadow.py --local DIR --lakes ouachita`.

## Not in scope

- **Promotion.** Before any data arrive, pre-register the promotion gate:
  - the Stage 16 bars on at least 200 new agency rows;
  - plus the Guntersville survey as the acceptance test.
- **Fitting on field observations.** Never: they are scoring-only.
