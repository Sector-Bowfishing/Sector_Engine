# Approval record: `lake-knowledge-2026-11-21.2`

Replaces the unshipped, never-approved draft id `lake-knowledge-2026-11-21.1` (releases are immutable, so the research fixes needed a new id).

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-21.2` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:d9fb97b7bd2b51bdc43e7550daacbfb1997c2a9076bc5c26e737d2e6c74b4b14` |
| Supersedes | `lake-knowledge-2026-11-20.1` (its bindings file changed: binding/history fixes from the 2026-11-21 dry-run research; 2 lakes held) |
| Approved by | Michael Cather (owner), in chat, 2026-11-21 04:15Z ("yes to both"); recorded on Sector_Ops #51 comment 7057138140 |
| Scope | **INTERNAL**, **CALIBRATION** and **CUSTOMER** |
| Customer eligible | **Yes** |

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: `acceptedLakeIds` goes from 189 to **187**; Lake's reviewed set (with the 5 pilots) and the customer Lake-level list go from 194 to **192**.
  - The 2026-11-21 Mac mini dry-run gauge check flagged 17 lakes; research (`docs/brains/LAKE_BRAIN_DRYRUN_CHECK_2026-11-21.md`) returned 15: 8 with binding/history fixes, 7 confirmed as real operator drawdown.
  - **Live series fixed** (they were reading a rule/guide curve, not the lake): Sardis MS, Grenada MS, Arkabutla MS, Enid MS → `…Elev.Inst.1Hour.0.DCP-rev`; Smith (Lewis Smith) AL → `Smith.Elev.Inst.1Hour.0.Raw-APCO`.
  - **Datum fixes**: Jennings Randolph cwms fallback to project datum; Beltzville cwms fallback and history to NAVD88 `Rev-DCP-88`; Deep Creek history 62615 −1.82 ft and THYM2 fallback −1.82 ft; Havasu LKHC1 fallback −0.65 ft (inferred).
  - **History fixed** (rule curve → observed): Sutton, Bluestone, Burnsville, R.D. Bailey, Senecaville, Tappan → `<Lake>-Lake.Elev.Inst.15Minutes.0.OBS`.
  - El Vado: low level is real (USBR interim maximum operating elevation 6,820.5 ft, release 5329); no plan bound, because a plan zone needs both edges.
  - Still held: Badin NC, High Rock NC (no live source).
- Every other packaged file is unchanged.

## What this approval allows
- The central Publisher may accept Lake Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`).
- Customer use of the release.

## What it does not allow
- Turning on any customer copy: `PUBLISHER_CUSTOMER_LAKE_LEVEL` stays Michael's switch.
- Any further change to the bindings: changing a file in the release means a new `releaseId` and a new approval.
