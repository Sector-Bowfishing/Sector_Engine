# WSW-2026-11-23, R2, R3, R4 and R5 are superseded (never run)

`WSW-2026-11-23.protocol.json` (sha256 `b9a55721f7a6d2853462c1080bbec384c3a30e3429fce70b10c2872c77449346`) is kept unchanged as a record. It was never run: nothing was fetched, fitted or scored under it, and the runner refuses it.

Its past window (NBM inits 2025-11..2026-04) had already been read: W1 and W1b graded NBM night wind against the same airports for 2025-11-01..2026-09-30, including >= 15 mph POD/FAR (`docs/brains/wind/APP_WIND_SOURCE_REVIEW_V1.md`), and the golden decoder fixture decodes NBM init 2026-03-08 at the frozen stations.

`WSW-2026-11-23-R2.protocol.json` (sha256 `ba05492be82102fdba170b8dd5181ec557505622246e6a780c52a6ffc129633b`) is also kept byte-identical and was never run. Independent review found that its CAL+H1 observation range reached H2 days (2026-10-08), that rows it could not build or forecast were dropped silently instead of counted against the method, and that the fit's sha256 was not required to be posted before the past-window fetch.

`WSW-2026-11-23-R3.protocol.json` (sha256 `82f96596197d6af32e43b9e01ce152e922f3a0c0a42993641993a2da0fda68a2`) is also kept byte-identical and was never run. Independent review found that every one-shot guard in it was bound to the --out folder, so a second folder could re-run a step and keep the better result.

`WSW-2026-11-23-R4.protocol.json` (sha256 `c0e86f6afa9de57d33c71d4eb049d4b1c95e403ad4a9c966edd16c7e9aaf77ca`) is also kept byte-identical and was never run. Its run ledger was local only, so a deleted or rewritten ledger folder could not be detected.

`WSW-2026-11-23-R5.protocol.json` (sha256 `a3578415c6b9f8d6a678e567234e1775512a3db9ea53ede1451f476128d0b565`) is also kept byte-identical and was never run: nothing was fetched, fitted or scored under it, and no R5 anchor was posted. The Mac mini never-read check of 2026-11-25 (Sector_Ops #51 comment 7153314652) found that its past window at the 8 frozen stations had been read before (W-NOW-1 fitted the pW15 recalibration on the 2024-25 cool season at those stations), and that no never-read past window exists at the 8 frozen stations at all.

The governing protocol is `WSW-2026-11-25-R6.protocol.json` (sidecar `.sha256`, sha256 `cd309fb947076ff87ad924d1e52e107dae2179a4138205ea5c9f782754fd8262`): R5's windows, methods, scoring and decision, with the past window scored at 8 fresh stations chosen from IEM station metadata by a fixed rule before any value is read, and a site-transfer caveat. It was drafted on 2026-11-25 (draft sha256 `1149d9d9dcfdc7e29ae28c493b5ab483824e0d4367ee3a1a4adedcabd3e09bf7`, under Owner decisions 2026-11-24, #51 comment 7154041302 decision 5), accepted by the owner (Owner decisions 2026-11-25, #51 comment 7183456058 item 5) and registered alone before any runner change and before any data was fetched; its `registration.changesFromDraft` lists what registration added. The runner pins it and refuses all five superseded files.
