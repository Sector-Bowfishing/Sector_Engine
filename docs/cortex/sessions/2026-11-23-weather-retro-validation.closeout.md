# Research Closeout — weather — weather-retro-validation

```text
Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine
Task: WX-001 / WX-002 retrospective validation (pre-registration + runner) · Folder: weather-brain (research home absent in this cloud session, CG-3.1-22; `research-path` does not know `weather`, CG-3.1-26) · Date: 2026-11-23 · Manifest task status: OPEN (blocked: the run happens on the Mac mini)
```

## Preserved results
No local data was created and nothing was fetched. Committed on branch `research/weather-retro-validation-2026-11-23`: protocol WX-RETRO-2026-11-23.5 (sha256 2133b04e9c65d3a10a9a878a92ea206fa1c0745b0023613cf0a74f2ed6f66386, committed alone in faafe95c; uses the shared run ledger #251), which supersedes WX-RETRO-2026-11-23.4 (sha256 55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d, 9cce990c), WX-RETRO-2026-11-23.3 (sha256 492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7, 90876982), WX-RETRO-2026-11-23.2 (sha256 01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c, b8e284f3) and WX-RETRO-2026-11-23 (sha256 6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8, c8d2e526), both kept byte-identical and refused by the runner; all five committed before any data, the runner `tools/research/weather_retro_validation.py`, its 43 offline tests, the plan amendment (WEATHER_BRAIN_PLAN.md §5.4) and the draft Mini request. These are rules and code, not research data.

## Manifests updated
none (no research folder exists for Weather yet; the Mini creates `weather-brain/README.md` and `manifest.json` and registers its outputs there)

## Candidate knowledge
none

## Backups verified
none required (nothing retained locally)

## Deleted
none. The Cortex tree extracted read-only into the session scratchpad and a throwaway performance fixture (synthetic, removed right after timing) are DISPOSABLE and are discarded with the session.

## Worktrees
`/home/claude/sector_engine_wxretro` (this task): kept until the PR is reviewed; worktree-check class before the final commit was KEEP_DIRTY (this task's uncommitted work), after push it is KEEP_ACTIVE (unmerged branch). `se_wt_validation` and `sector_engine_wt_wtpt` (REMOVABLE_MERGED, other sessions) were removed by the coordinator (merged and clean); not removed by this session. Other KEEP_* worktrees belong to other sessions: not touched.

## Blockers
The run ledger cannot open until Cortex `research-path sector/engine weather` resolves (CG-3.1-26; needs a Cortex release and an Engine pin bump). The data fetch and grading run on the Mac mini (draft request in `docs/brains/weather-retro-validation/MINI_REQUEST_DRAFT.md`, not posted). This session fetched nothing by design (pre-registration first; the run is the Mini's).
