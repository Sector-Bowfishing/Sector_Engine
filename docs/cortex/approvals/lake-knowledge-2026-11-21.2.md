# Approval record: `lake-knowledge-2026-11-21.2` (PENDING)

Replaces the unshipped, never-approved draft id `lake-knowledge-2026-11-21.1` (releases are immutable, so the research fixes needed a new id).

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-21.2` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:d9fb97b7bd2b51bdc43e7550daacbfb1997c2a9076bc5c26e737d2e6c74b4b14` |
| Supersedes | `lake-knowledge-2026-11-20.1` (its bindings file changed: binding/history fixes from the 2026-11-21 dry-run research; 2 lakes held) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-20.1) |

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: `acceptedLakeIds` goes from 189 to **187**; Lake's reviewed set (with the 5 pilots) and the customer Lake-level list go from 194 to **192**.
  - The 2026-11-21 Mac mini dry-run gauge check flagged 17 lakes; research (`docs/brains/LAKE_BRAIN_DRYRUN_CHECK_2026-11-21.md`) returned 15: 8 with binding/history fixes, 7 confirmed as real operator drawdown.
  - **Live series fixed** (they were reading a rule/guide curve, not the lake): Sardis MS, Grenada MS, Arkabutla MS, Enid MS → `…Elev.Inst.1Hour.0.DCP-rev`; Smith (Lewis Smith) AL → `Smith.Elev.Inst.1Hour.0.Raw-APCO`.
  - **Datum fixes**: Jennings Randolph cwms fallback to project datum; Beltzville cwms fallback and history to NAVD88 `Rev-DCP-88`; Deep Creek history 62615 −1.82 ft and THYM2 fallback −1.82 ft; Havasu LKHC1 fallback −0.65 ft (inferred).
  - **History fixed** (rule curve → observed): Sutton, Bluestone, Burnsville, R.D. Bailey, Senecaville, Tappan → `<Lake>-Lake.Elev.Inst.15Minutes.0.OBS`.
  - El Vado: low level is real (USBR interim maximum operating elevation 6,820.5 ft, release 5329); no plan bound, because a plan zone needs both edges.
  - Still held: Badin NC, High Rock NC (no live source).
- Every other packaged file is unchanged.

## Until it is approved
- The Publisher (`PackagedReleaseResolver`) accepts only an `APPROVED` release, so a Publisher image built from this commit would refuse Lake artifacts. Approve before the next Publisher redeploy and LakeBrainJob rebuild; nothing is deployed by merging.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
