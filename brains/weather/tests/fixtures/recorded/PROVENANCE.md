# Recorded NWS fixtures (RECORDED, not hand-built)

Byte-identical copies of the Engine's recorded api.weather.gov responses (`Tests/SectorEngineTests/Fixtures/NWS/`, recorded 2026-11-06 at about
20:51Z for the NWS weather adapter, commit 943751e7; see `docs/architecture/conditions/NWS_WEATHER_ADAPTER_V1.md`). The Engine recording kept only
the fields the adapter reads, so `presentWeather` and `probabilityOfPrecipitation` are absent. Champlain: only the nearest station (KBTV) is copied;
KPBG and KFSO are not, so a Champlain run here sees one station.

| file | sha256 |
|---|---|
| champlain-grid.json | ad308504fb588edd7eecf65c17d5b5f3897bce74098a9e58d61267cc2492cff4 |
| champlain-obs-KBTV.json | ea4d5d84372b73901bf1167ef30f704746ebdbace6584d9d2c136d28f891565f |
| champlain-points.json | c1b59dcb6536696a737fa4e01d0e7c154bd531fcdda1424b8f8a2232019c3153 |
| champlain-stations.json | afbd26fd74604c36366827f8eee5cd0b92cdb3abe03c4b301545779905c0f620 |
| guntersville-grid.json | f73df4d6bddf6277e915efa1c4ff52cf897dfede930f387436aeaa3cf978e5a0 |
| guntersville-obs-K4A6.json | 9f89c554a9de86d0afb61edb6c6853a4b7c161e7398f6cec27fbf71d31fc1aaf |
| guntersville-obs-K8A1.json | ed778c73ea51338d6576fb5992b189f2b94d9f3d5e199f46c1af520d6b0b3e6c |
| guntersville-obs-KBFZ.json | f9fe3129bd8c59650efad8c34e96ead1a0adcbfe8922195a9ad0b2ab5aa90e11 |
| guntersville-points.json | 79100f0faeba27e7c55c36d64b3d5b499f965fa8e16f909bfdb38d688e6dd4fe |
| guntersville-stations.json | bfa48612396c5e043b82b82c20b65732c924fb548ca6e6c5bd027ed3f569942a |
