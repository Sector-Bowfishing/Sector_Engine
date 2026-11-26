# Approval record: `lake-knowledge-2026-11-25.1` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-25.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:5fc7d3e81afcc805528a6df66e75c7bfaed9b3e4f0267554ae37448895bc5e9b` |
| Supersedes | `lake-knowledge-2026-11-24.1` (APPROVED 2026-11-25, Sector_Ops #51 comment 7154041302) |
| Status | **NOT_RECORDED: the rebind is requested by the owner; the release digest awaits Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-24.1) |

## What changed
- `LakeBrain/LakeSourceBindingsGenerated.swift` only (sha256 `19dc1336...`, 621,216 bytes). `LakeSourceBindings.swift` and `LakeGeneratedBindings.swift` are unchanged.
- Moses Lake WA: live moves from USACE CWMS `NWDP` `MLAW.Elev-Forebay` (RFC-RAW) to USGS `12471000` series `62614`, `DIRECT_LAKE_GAUGE`. CWMS has read +0.34 ft above USGS since 2026-11-13; USGS is the same gauge the history already uses.
- Flannagan Reservoir VA: history moves from the CWMS rule curve `JWFlannagan-Lake.Elev.Inst.1Day.0.RUL` to the observed `JWFlannagan-Lake.Elev.Inst.15Minutes.0.OBS` (the same location the live side already reads through NWPS `FLAV2`). Live binding unchanged.
- `brains/lake/contracts/reviewed-lake-bindings-v1.json`: Moses Lake capability and live id updated to match.
- Basis: Owner decisions (Michael, 2026-11-25 23:22 CT), item 6 of the Morning summary, Sector_Ops #51 chat approval of all recommendations.

## What approval allows
- Recording these bindings as the owner-approved Lake knowledge for INTERNAL, CALIBRATION and CUSTOMER scope.

## What it does not allow
- A LakeBrainJob rebuild, a Pulse binary switch, a deploy, a schedule change, or turning on any customer flag or Engine reader: each is a separate owner decision.

## To approve
Michael confirms the digest above in chat or in an "Owner approval (Michael, ...)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
