# TVA datum + bathymetry request - FINAL (Michael-ready; NOT SENT)

Combine with the bathymetry/records request (`DEPTH_SOURCE_REQUEST_QUEUE.md` row 1, `DEPTH_SOURCE_REQUEST_PACKAGE.md`). Evidence: `DEPTH_TVA_DATUM_CONFIRMATION.md`.

## What is established and what is not
* **Established (TVA's own REST payloads, fetched 2026-10-14):** for the 16 TVA lakes, the directory pool equals a figure in the `operating-guide` payload, and the operating guide's `MidNightElevation` matches the observed reservoir reading (identical for 7 lakes, within 0.05 ft for the rest). The Guntersville tailwater also matches NWS gage zero + stage exactly. So pool and reading behave as **one TVA system**. Depth therefore keeps `SAME_OPERATOR_SYSTEM` (sigma 0.1 ft) - **unchanged**, no confidence raised.
* **Not established:** the **datum name**. No TVA text or API field states it (`tva.com` returns 403 to automation; `lakeinfo.tva.gov` has no datum wording). NGVD29 rests on a Kentucky Transportation Cabinet record for the TVA-maintained Kentucky Dam gauge and an NWS tailwater gauge.

## Ask (to TVA River Management / Reservoir Operations)
1. Vertical datum of `ReservoirElevation` and `TailwaterElevation` (NGVD 1929, NAVD 1988, or a TVA datum) - the same for every reservoir listed?
2. Are the operating-guide fields (`TopOfGates`, `TopOpZone`, `BtmOpZone`, `GuideCurve`, `PrevYrElev`, `CurYrElev`) and `MidNightElevation` in the **same** vertical reference as the live reservoir reading? (This is the relationship Depth relies on.)
3. Any datum change or re-adjustment since 2000 (date, offset)?
4. Is `ReservoirElevation` the forebay elevation at the dam, and what is its precision?
5. A public document we can cite.

Reservoirs: Guntersville, Wheeler, Wilson, Pickwick, Chickamauga, Fort Loudoun, Nickajack, Watts Bar, Kentucky, Fontana, Hiwassee, Cherokee, Douglas, Norris, Tims Ford, South Holston (16 lakes; 17 directory rows).

## Email text
> Subject: Vertical datum of the TVA lake-level data (and survey data request)
> Hello - Sector is a bowfishing conditions app that reads TVA's public lake-level data (`observed-data-48-hours` and `operating-guide`). To state water-level changes correctly we need the vertical datum. For the reservoirs listed: (1) what vertical datum are reservoir and tailwater elevations referenced to? (2) are the operating-guide elevations (top of gates, operating zone, guide curve, midnight elevation) in the same reference as the live reading? (3) any datum change since 2000? (4) is it the forebay elevation at the dam? (5) is there a public document we can cite? We would also like to ask about processed bathymetric/hydrographic survey data and area-capacity tables for these reservoirs (details in the attached records request). We will credit TVA and publish only derived numbers unless TVA permits otherwise. Thank you - [YOUR NAME], [CONTACT]

## Channel
TVA FOIA portal (`foia.tva.gov`) was verified live; commercial requesters may be charged. A direct River Management contact may answer the datum questions faster; none is recorded here.

## What changes if TVA confirms (not before)
Single datum for reading and guide -> `datum_providers.json` tva `levelDatumBasis` moves to `verified_doc`, status may upgrade to SAME_SOURCE, sigma may drop; absolute-elevation statements and 3DEP/USGS/CWMS cross-comparison (and, with the official offset, NAVD88 conversion) become allowed. If TVA says the datum differs by reservoir, split the rule per reservoir. If any reservoir is NAVD88, remove the inferred-NGVD29 notes for it. Lake Brain can then stamp `datum` (`DEPTH_LAKE_DATUM_DEPENDENCY.md`).
