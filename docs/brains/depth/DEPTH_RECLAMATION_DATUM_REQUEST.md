# Reclamation datum confirmation request - NARROWED (Michael-ready; NOT SENT)

**Update 2026-10-14 (long-run campaign).** The original request (19 RISE rows) is superseded. Public Reclamation data settled **17 RISE lakes** (16 of them from this work, Cheney through an independent USGS gauge) without waiting for Reclamation (storage consistency against the TSC survey tables, allocation-diagram frame check; `DEPTH_RECLAMATION_DATUM_CHAIN.md`). What remains is below, with the specific reason each stayed open. Sending is still Michael's call; this version is shorter and every question is specific.

## Reservoirs still open (RISE series, pool Depth uses, why open)
| Reservoir | Series | Pool (ft) | Why public data did not settle it |
|---|---|---|---|
| Blue Mesa Reservoir (CO) | RISE item 78 | 7519.4 | RISE daily storage is not total storage (fit off by a third), the 2019 tables cannot be used for a frame check |
| Box Butte Reservoir (NE) | RISE item 142 | 4007 | no printed capacity reached since the diagram was revised (reservoir low) |
| Caballo Lake (NM) | RISE item 212 | 4172.44 | no table or diagram capacity available publicly |
| Flaming Gorge Reservoir (UT) | RISE item 341 | 6040 | RISE storage matches a table 1.2 ft away from the 2019 table; which table does RISE use? |
| Flaming Gorge Reservoir (WY) | RISE item 341 | 6040 | same series as UT |
| Fontenelle Reservoir (WY) | RISE item 349 | 6506 | no table available publicly |
| Jamestown Reservoir (ND) | RISE item 451 | 1431 | within 0.04 ft of the 2009 table but 0.145 ft off the 2015 diagram at 1431 ft; which is current? |
| Alcova Reservoir (WY) | RISE item 114 | 5498 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Buffalo Bill Reservoir (WY) | RISE item 152 | 5393.5 | no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills) |
| Deer Creek Reservoir (UT) | RISE item 293 | 5417 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Glendo Reservoir (WY) | RISE item 374 | 4635 | no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills) |
| Havasu (AZ) | RISE item 6128 | 450 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Horsetooth Reservoir (CO) | RISE item 87 | 5430 | no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills) |
| Jordanelle Reservoir (UT) | RISE item 471 | 6166.4 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Lake Granby (CO) | RISE item 384 | 8280 | no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills) |
| Lake Mead (NV) | RISE item 6123 | 1219.6 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Lake Mohave (NV) | RISE item 6133 | 647 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Lake Powell (UT) | RISE item 508 | 3700 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Pineview Reservoir (UT) | RISE item 656 | 4900 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Ruedi Reservoir (CO) | RISE item 712 | 7766 | no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills) |
| Seminoe Reservoir (WY) | RISE item 733 | 6357 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Shadow Mountain Reservoir (CO) | RISE item 738 | 8367 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Shasta (CA) | RISE item 10863 | 1067 | no Reclamation allocation diagram or public capacity table for this pool figure |
| Starvation Reservoir (UT) | RISE item 767 | 5712 | no Reclamation allocation diagram or public capacity table for this pool figure |

## Email text (placeholders [YOUR NAME] [CONTACT])

> Subject: Vertical frame of RISE daily reservoir elevation series for a short list of reservoirs
> Hello - Sector is a bowfishing conditions app. We compare each reservoir's current RISE "Lake/Reservoir Elevation" (parameter 2, daily) with its normal pool to tell anglers how far the water has moved. For most Reclamation reservoirs we could confirm from RISE storage and the Technical Service Center tables that RISE elevation and the allocation pages share one vertical frame. For the reservoirs in the attached table we could not (reasons listed). For each:
> 1. Is the RISE daily elevation the dam water-surface gage record in the reservoir's current TSC survey / area-capacity report, in the same project datum as the allocation elevations?
> 2. Which capacity table does RISE storage use today (survey year), and has the gage or datum been re-adjusted (dates, offsets)?
> 3. Where we list a mismatch (Flaming Gorge, Jamestown), which source is current?
> We will not convert between datums without an official offset, we will credit Reclamation, and we use only derived numbers. A one-line reply per reservoir is enough. Thank you - [YOUR NAME], [CONTACT]

## If confirmation arrives
Add the confirmed reservoirs as lake-scoped `operator-doc` proposals (`SAME_SOURCE`, project frame, sigma 0.1), `promote-proposals --apply`, `refresh`, `report --log`, regenerate docs, tests. Nothing is promoted before that.
