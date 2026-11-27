# Approval record: `lake-knowledge-2026-11-26.1` (APPROVED)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-26.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:4f2d6154fa1d46c00a86a296bd9abf6e8fc9c972d3484a398ecfb54ba69dfa47` |
| Replaces | `lake-knowledge-2026-11-25.1` (never approved or merged; cut again after review) and supersedes `lake-knowledge-2026-11-24.1` (APPROVED 2026-11-25, Sector_Ops #51 comment 7154041302) |
| Status | **APPROVED** by Michael in chat, 2026-11-26 20:57 CT (Claude Code session): "approve", in reply to "Approve the Lake release digest sha256:4f2d6154…fa47 (#259)". Recorded by Claude from the chat; no Sector_Ops comment yet. |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-24.1) |

## What changed
- `LakeBrain/LakeSourceBindingsGenerated.swift` only (sha256 `c26df536...`, 621,215 bytes). `LakeSourceBindings.swift` and `LakeGeneratedBindings.swift` are unchanged.
- Moses Lake WA: live moves from USACE CWMS `NWDP` `MLAW.Elev-Forebay` (RFC-RAW) to USGS `12471000` series `62614`, `DIRECT_LAKE_GAUGE`. CWMS has read +0.34 ft above USGS since 2026-11-13; USGS is the same gauge the history already uses.
- Flannagan Reservoir VA: history moves from the CWMS rule curve `JWFlannagan-Lake.Elev.Inst.1Day.0.RUL` to the observed `JWFlannagan-Lake.Elev.Inst.15Minutes.0.OBS` (the same location the live side already reads through NWPS `FLAV2`). Live binding unchanged. History stats follow the new series, which starts 2020-08-12: 5 complete years (2021-2025), first year 2020, class SUFFICIENT (was 13 years from 2013 on the rule curve). Counted from the series start; a Mac mini read should confirm.
- `brains/lake/contracts/reviewed-lake-bindings-v1.json`: Moses Lake capability and live id updated to match.
- Basis: Owner decisions (Michael, 2026-11-25 23:22 CT), item 6 of the Morning summary, Sector_Ops #51 chat approval of all recommendations.

## What approval allows
- Recording these bindings as the owner-approved Lake knowledge for INTERNAL, CALIBRATION and CUSTOMER scope.

## What it does not allow
- A LakeBrainJob rebuild, a Pulse binary switch, a deploy, a schedule change, or turning on any customer flag or Engine reader: each is a separate owner decision.

## To approve (historical)
Approved in chat as recorded above; `approval.status` is `APPROVED` here and in `brains/lake/runtime/knowledge-release.json` (the digest does not change).
