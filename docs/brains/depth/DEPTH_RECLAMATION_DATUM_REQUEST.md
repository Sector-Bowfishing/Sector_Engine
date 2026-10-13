# Reclamation datum confirmation request - FINAL (Michael-ready; NOT SENT)

Purpose: unlock **19 RISE reservoir rows (18 distinct series; Flaming Gorge is bound as both UT and WY)** that Depth holds (`accepted_provider_rules.json` -> `heldWithReason`). Nothing is promoted until Reclamation confirms. Evidence: `DEPTH_RISE_DATUM_RULES.md`. Held because: each reservoir's TSC survey / area-capacity report states the dam gage record and the pool in one **project datum** (RPVD / "project datum"), but nothing documents that the **RISE daily "Lake/Reservoir Elevation" value (parameter 2)** *is* that gage record, and RISE itself declares no series datum (null on all 45 catalog items; location tags are mixed, 15 are EGM96, which is not a gage datum).

## Who / where
Bureau of Reclamation, the regional offices that own the data (Great Plains: Billings/Montana, Nebraska-Kansas, Dakotas; Upper Colorado; Technical Service Center for the surveys). Use Reclamation's public data-request/contact route (RISE help/contact on `https://data.usbr.gov`, or the regional hydromet contact printed on each project page). **Re-verify the channel before sending** (the scouting host could not reach `data.usbr.gov` in prior cycles). No individual's name is recorded here.

## The reservoirs (what Depth reads and what the survey says)
| Reservoir | RISE item (parameter 2) | Pool Depth uses (ft) | Survey statement Depth found |
|---|---|---|---|
| Angostura (SD) | 106 | 3187.2 | project datum reported as NGVD29; about 2 ft below NAVD88 (2004) |
| Bighorn (WY) | 164 | 3640 (top of joint use) | RPVD assumed equal to NGVD29; NAVD88 - NGVD29 = 2.63 ft at Yellowtail (2017). Pool basis is joint use, not conservation (3614) |
| Blue Mesa (CO) | 78 | 7519.4 | RPVD is 4.71 ft below NAVD88 (2019) |
| Box Butte (NE) | 142 | 4007 | gage datum tied to NGVD29; 2.0 ft below NAVD88 (2003) |
| Caballo (NM) | 212 | 4172.44 | project datum 43.3 ft below NGVD29 / 45.5 below NAVD88 (2007) |
| Cheney (KS) | 133978 | 1421.6 | project datum coincides with NGVD29; 0.479 ft below NAVD88 (2015) |
| El Vado (NM) | 336 | 6902 | project datum about 7.8 ft below NGVD29 / 12.0 below NAVD88 (2007) |
| Elephant Butte (NM) | 332 | 4407 | RPVD 43.3 (2007) vs 45.0 ft below NAVD88 (2017/2019): two reports differ by 0.5 ft |
| Flaming Gorge (UT and WY) | 341 | 6040 | RPVD defined; 2019 survey says CorpsCon was inconclusive on RPVD = NGVD29 |
| Fontenelle (WY) | 349 | 6506 | RPVD; offsets not extracted (2019) |
| Fresno (MT) | 355 | 2575 | project datum 4.7 ft above NGVD29 (2010) - NOT the RISE location NGVD29 tag |
| Heron (NM) | 421 | 7186.1 | tied to NGVD29; 4.278 ft below NAVD88 (2010) |
| Jamestown (ND) | 451 | 1431 | tied to NGVD29; 1.25 ft below NAVD88 (2009) |
| Keyhole (WY) | 478 | 4099.3 | NGVD29; 2.1 ft below NAVD88 (2003) |
| Navajo (NM) | 612 | 6085 | RPVD 2.97 ft below NAVD88 (2019) |
| Lake Tschida (ND) | 550 | 2064.5 | 0.2 ft below NGVD29; 1.7 below NAVD88 (2013) |
| Merritt (NE) | 599 | 2946 | tied to NGVD29; about 1.0 ft below NAVD88 (2003) |
| Patterson (ND) | 305 | 2420 | 0.1 ft below NGVD29; 1.9 below NAVD88 (2013); a contour labelled NAVD88 at 2,420 is ambiguous |

## Email text (placeholders [YOUR NAME] [CONTACT]; edit the list if Reclamation asks for fewer)

> Subject: Vertical datum of RISE daily reservoir elevation series - confirmation request
> Hello - Sector is a bowfishing conditions app. We compare each reservoir's current RISE "Lake/Reservoir Elevation" (parameter 2, daily) with its normal pool to tell anglers how far the water has moved, and we need to state the vertical reference correctly. For the 18 reservoirs in the attached table (RISE item ids included):
> 1. Is the RISE daily value the **dam water-surface gage record** described in the reservoir's current TSC survey / area-capacity report?
> 2. Is it expressed in the **project datum (RPVD / "project datum")** stated in that report, for the full period of record, or has the gage or datum been re-adjusted (dates and offsets)?
> 3. Are the **Top of Active Conservation / joint-use elevations** on the project allocation pages in that same datum?
> 4. For the cases where the RISE location tag or asset record disagrees with the survey (Fresno, Bighorn, Shasta, Trinity, Mohave), which field is authoritative?
> 5. Is there a public document we can cite?
> We will not convert between datums without an official offset, we will credit Reclamation, and we use only derived numbers. A one-line reply per question is enough. Thank you - [YOUR NAME], [CONTACT]

## If confirmation arrives (what Depth will do - not before)
1. Add a provider rule to `proposals/accepted_provider_rules.json` (scope: the confirmed reservoirs) with the reply as evidence; add validator support for a **project datum** as a SAME_SOURCE-type relationship (never SAME_DATUM with NGVD29/NAVD88; never converted).
2. `python -m depth_brain promote-proposals --apply`, rebuild the manifest, `python -m depth_brain report --log --cycle <n>`, regenerate docs, re-run tests, push.
3. Expected: up to +19 defensible rows (MEDIUM rollout until history length and pool-basis issues are cleared: Bighorn is joint-use, not conservation pool).
