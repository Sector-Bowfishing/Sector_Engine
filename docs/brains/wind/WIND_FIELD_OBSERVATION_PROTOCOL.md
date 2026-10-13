# Field observation protocol — about one minute per bank

Goal: let a trusted tester, a local bowfisher or a beta user give Sector physical truth without being a meteorologist. Schema and validator: `jobs/wind-hourly/sector_wind/brain/field_schema.py` (`sector-wind-field-v2`, tested). It extends the existing Stage 3 packet system (blinded sheets, write-once intake, sealed keys) and drops its four-lake limit.

## The record (what the tester taps/types)
| Field | Values | Notes |
|---|---|---|
| lake, bank/zone | picked from the map (canonical bank/zone id) | auto: time (UTC), GPS, device |
| **Water surface** | CALM · LIGHT · CHOPPY · ROUGH | calm = glass/no ripple · light = small ripples · choppy = whitecap-free chop that slaps the hull · rough = whitecaps/waves |
| **Bank exposure** (the tester's judgement) | **EXPOSED · PROTECTED · UNSURE** (everyone) · optional richer **DIRECT · CROSS** for AUDITED-lake validation | "is the wind reaching this bank, or is the bank in the lee?" ESTIMATED lakes only claim EXPOSED/PROTECTED, so that is all a tester needs to say |
| **Boat-control difficulty** | EASY · NOTICEABLE · DIFFICULT | holding position/steering while hunting |
| Wind direction FROM | 16-point compass, or degrees | from a compass/flag/handheld; optional |
| Wind speed | mph from a handheld anemometer, **or** "visual estimate" | optional; measured reading needs device, height above water, averaging (60 s) |
| Confidence | 1 guess · 2 · 3 sure | |
| Photo/video | optional: one photo looking upwind from the boat | |
| Saw the model's prediction? | yes/no (automatic) | the app must not show the prediction before submission |
| Pair | optional pairId + A/B | for planned paired sessions |
**Never recorded in the observation:** the model's prediction or label (sealed separately, joined by id).

## Rules enforced by the validator (not repaired, only reported)
Measured wind must name the device, a sensor height > 0 and an averaging period; gusts only from a measuring device; direction is the meteorological FROM bearing; future timestamps rejected; a pair needs both banks usable, same lake, same pairId with roles A/B, within 60 minutes, and not the same bank twice; an observation may not contain a prediction.

## Who can collect what
| Collector | Can provide | Counts toward |
|---|---|---|
| Michael / trained tester | paired sessions with handheld wind, photos | bank-pair concordance (certification dims 6/7), over-water ratio |
| Trusted beta tester | single-bank records, visual wind | tester-vs-model agreement matrix; surface class agreement |
| Any bowfisher (future in-app) | one tap "wind is hitting this bank / protected" + roughness | volume signal only; not scored unless blinded and device-wind present |
Quality control: tester calibration on a few pairs against the trained tester; photos for disputes; observer confidence ≥ 2 for scored pairs.

## Scoring (not done here)
`field_schema.pair_concordance` converts paired records and sealed predictions to concordance (ties 0.5, model ties and UNKNOWN/UNSURE excluded and counted). Certification credit is the canonical scorer's job under Evidence Addendum v1; this protocol only produces records that can qualify.

## Practicalities
Safety first (no sessions in lightning or when wind makes boating unsafe). Avoid anchoring: record before opening any Sector wind screen. Time-sync: phone clock is fine (UTC stored). One session = one lake, one evening, ≥ 2 banks.
