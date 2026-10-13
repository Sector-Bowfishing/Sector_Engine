# ResOpsUS (Zenodo 5893641): licence check and finding

Status: 2026-10-13. **Not downloaded.** The brief allowed the ~299 MB download only if the licence and public access were confirmed open; the Zenodo record's own licence could not be read, so the rule "licence unclear, do not download" applies.

## What was checked

| Item | Result |
|---|---|
| Zenodo record page / API (`zenodo.org/records/5893641`, `/api/records/5893641`) | **Unreachable from this environment**: `curl` connection timed out after 20 and 40 s on `zenodo.org` (other hosts, including `doi.org` and `cwms-data.usace.army.mil`, answered in under 0.3 s); the WebFetch tool returned no output for the same URLs. The licence field of the record was therefore not read. |
| Web search result for the record | Version 2, published 2021-09-01, open access, one ZIP of about 298.6 MB; daily storage, inflow, outflow, elevation and evaporation for 679 reservoirs. A newer version of the record exists (not inspected). No licence text in the snippet. |
| Paper (Steyaert, Condon, Turner, Voisin 2022, Scientific Data, PMC8814038) | The **article** is CC BY 4.0 and its metadata files CC0; the page does not state a licence for the data files. |
| Mirror on CyVerse Data Commons (DOI 10.25739/5fnr-1v31, "Steyaert_ResOpsUS_April_2021") | Licensed **ODC PDDL** (public domain dedication). This is a different copy (April 2021 files, CyVerse user agreement), not the Zenodo record. |

Conclusion: the dataset is very probably open (CC BY or PDDL), but the Zenodo licence was not confirmed from the record itself, so no file was fetched and `MANIFEST.jsonl` has no ResOpsUS row.

## What the paper says about our needs (no data opened)

* 679 reservoirs, 1930 to 2020 (best 1980 to 2020; the USGS catalog entry says 1974 to 2020). Variables: storage (653 reservoirs), outflow (519), elevation (506), inflow (321), evaporation (46). Gaps are `NA`; where only elevation was supplied, storage is interpolated from storage-elevation curves and flagged in `agency_attributes.csv`.
* About half of the records come from agency portals (USACE, USBR, CDEC, Water Data for Texas, USGS), the rest from operators.
* **TVA: the paper states that for TVA reservoirs the dataset contains only a list of USGS gauges used for inflow, not inflow time series.** Whether TVA elevation, storage or release series exist was not confirmed. For our four mainstem pilots the deep composite already exists (NWS RVDHUN, HADS, CWMS LRD), and the nine TVA tributary lakes (Cherokee, Chickamauga, Douglas, Fontana, Fort Loudoun, Hiwassee, Norris, South Holston, Watts Bar) are the open question from `LAKE_BRAIN_PLAN_HISTORY_RESEARCH.md` (B-plan-002): ResOpsUS is unlikely to answer it.
* The USACE and USBR reservoirs in ResOpsUS overlap what CWMS and RISE already give the Lake Brain; the added value would be older elevation/storage/release history for reservoirs without a CWMS daily series, and release (outflow) series for the plan/flood work. Not measured against the 621-lake directory.

## To finish (Michael decision, 2 minutes)

Either open `https://zenodo.org/records/5893641` in a browser and confirm the licence field (CC BY 4.0 or CC0 would clear it), or approve the CyVerse PDDL copy. Then the download, SHA-256 check against the Zenodo/CyVerse metadata, the match against the 621 directory lakes (name, state and dam coordinates; count of TVA tributaries present; variables per matched dam) and the `MANIFEST.jsonl` rows (`retention: REBUILDABLE`, rebuild = the download URL) take about 20 minutes. Target directory: `~/Desktop/Development/Sector_Research_Data/lake-brain/plan/resopsus/` (outside Git).
