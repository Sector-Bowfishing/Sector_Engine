# Session record: WT-NOW-4, Water Temp range (latitude band and Landsat correction)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine, pin ecaef70. Date: 2026-11-14. Branch: `cortex/wt-now-4-2026-11-14` (off main d216e3c). Mac mini, research home `/Volumes/DevSSD/Research/SectorResearch`. Records only; no production code changed.

## Scope
Owner approval (Michael, 2026-11-14 ~18:52Z), Sector_Ops #51 comment 6882544498, item 2: pre-register and hash three arms (latitude band, Landsat 8/9 per-lake correction, both) and a new fresh-lake pool before reading any held-out row; score once against the same bar; no cloud spend. Item 3: a passing arm opens a PR with the range OFF by default; otherwise "Estimate" stays. Using Landsat in any score is not covered and was not done.
Michael's follow-ups in this session: the repo's `.claude/settings.json` deny rule blocks `curl`, so downloads ran through Python for planetarycomputer.microsoft.com, waterqualitydata.us, archive-api.open-meteo.com and PyPI (`pip install --user pystac-client planetary-computer rasterio`; `pandas` was also installed from PyPI because the existing scorers need it); a new pull, not a lower lake-day bar, if the fresh pool was short.

## Done
- New WQP pull (cool seasons 2013-14…2015-16, 48 states) added to the 2016-26 files; 46 fresh lakes with ≥ 10 lake-days in 2013-11…2020-04; every WT-NOW-2 and WT-NOW-3 lake excluded. Prereg, pool lists, scorer hashed and posted on #51 (comment 6883334285) before the weather and Landsat pulls.
- Scored once: all three arms FAIL (coverage 0.712 (a), 0.737 (b), 0.765 (a)+(b); Mar–Apr bias 1.97 °C breaks the bar for (b) and (a)+(b)).
- Closeout `water-temperature/closeouts/2026-11-14-wt-now-4-latitude-band-and-landsat.md`; manifest item `wt-now-4-2026-11-14` and task DONE; `research-check` on the closeout: 0 findings; home check: no finding names this item (the existing findings are older manifests/duplicates, unchanged).

## Decisions (reversible, in the prereg)
- Training window for Landsat is 2020-11…2026-04 and the test lake-days are 2013-11…2020-04, because a forward split gave 5 lakes.
- Training lakes for the bands are the 300 WT-NOW-3 lakes (allowed by Michael).
- Corrections fitted on training lakes: γ (solar) and ω (wind) with per-lake offsets shrunk by n/(n+5); 90 m shore buffer.

## Verification
- `research-check sector/engine --closeout …`: Findings 0. `research-check sector/engine --repo .`: 8 `MAC_LOCAL_RUNTIME_PATH` findings in files this session did not touch (unchanged by this change).
- Declared limits: ~2% of Landsat scene reads failed and were not re-pulled; the Landsat reader's window/component rule was set after a debug run on three training lakes (disclosed); no multiple-comparison correction across three arms.

## Open for Michael
- Keep "Estimate" (approval item 1), or commission another pre-registered attempt (new pool needed; the 46 + 300 + WT-NOW-2 lakes cannot be reused).
