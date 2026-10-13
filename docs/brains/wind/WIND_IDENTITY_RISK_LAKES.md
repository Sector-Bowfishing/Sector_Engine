# Audited lakes with a lake-identity risk (Lake Brain owns identity; Wind blocks until it is resolved)

Lake Brain's geometry flags (`lake_geometry_flags.csv`, sha256 prefix a6986e005ad3, 621 lakes) mark 43 lakes `identity_risk` (all confidence LOW). Six of them nevertheless have an **AUDITED** Wind fetch table. Wind does **not** fix identity: those six are `BLOCKED` in the geometry manifest (`exposure_allowed` = false), so no bank statement is produced for them. The other 37 identity-risk lakes were already LOW/POINT_ONLY (no bank labels). Machine-readable evidence: `data/identity_risk_audited_lakes.json`.

| Lake ID | Lake Brain evidence | What the audited table was actually built on | Severity |
|---|---|---|---|
| **Andrews Lake\|DE** | directory point **12.7 km** from the polygon (allowed 3.0 km); engine polygon "Andrews Lake" 0.084 km²; 25% of polygon water ≥ 50% of the time (GSW) | NHD feature **"McColley Pond"** (0.232 km²), seed 6.7 km from the directory point, `nameMatchesDirectory: false` | **Wrong water body.** Table must not be used. |
| **Griffith Lake\|DE** | point **6.3 km** from polygon; polygon "Griffith Lake" 0.159 km² | NHD **"Killen Pond"** (0.319 km²), seed 6.1 km, name mismatch | **Wrong water body.** |
| **Hiwassee Lake\|NC** | point **8.9 km** from polygon; source osm; NHD name differs from directory name; NHD area ratio 0.88 | NHD **"Persimmon Lake"** (23.9 km²), seed 8.9 km, name mismatch | **Wrong water body (or a differently named reach).** |
| **Eagle Lake\|MS** | point **4.1 km** from polygon (allowed 3.0) | NHD "Eagle Lake" (19.5 km²), name matches, seed 4.1 km | Name matches; the **directory coordinate is off by 4 km** (also shifts the forecast sampling point by ≥ 1 cell) |
| **Long Lake\|ME** | point **4.8 km** from polygon | NHD "Long Lake" (24.4 km²), name matches | same |
| **Sherman Reservoir\|NE** | point **4.6 km** from polygon | NHD "Sherman Reservoir" (9.9 km²), name matches | same |

## What Lake Brain needs to decide (per lake)
1. Is the directory name/state the lake in the engine polygon, or the pond/lake the audited table used? (The three mismatches look like the directory name belonging to a small pond that NHD names differently; Hiwassee's reservoir may be a different feature entirely.)
2. If the polygon is right: correct the directory coordinate (this also fixes the forecast sampling point).
3. If the audited table's feature is right: replace the engine polygon.
Evidence Wind can hand over: table SHA-256 prefixes (8fa2941c3b04 Andrews, bc347a2db835 Griffith, 416877cb8380 Hiwassee, 9c1d73c7bf99 Eagle, 476d44f1951a Long, 7582a8d6403d Sherman), seed distances above, the NHD features used.

## Wind policy until resolved
`blockers: ["lakeIdentityRisk"]` ⇒ no bank labels and no exposure shares; wind direction/tonight for these lakes should carry a "representative point may be off" caveat (their directory coordinate is 4–13 km from the water). When Lake Brain publishes a corrected identity, rebuild the manifest (`python -m sector_wind.brain.fleet build …`); Wind re-audits the table only if the underlying feature changed.
