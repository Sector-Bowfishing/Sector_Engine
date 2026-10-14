# Strong-wind problem — do the shipped mechanisms work? (CAL+H1, descriptive)

Question: NBM under-forecasts stronger nights. Are *category-as-floor*, *P90 / ifItBlows*, *breezyRisk (P90 ≥ 10 mph)* and *confidence* enough to give a useful bowfishing warning — "Expected: LIGHT · Risk: COULD TURN BREEZY" — without a numeric correction? Rules evaluated exactly as shipped in `brain/tonight.py` (no tuning, no +N mph correction). Tonight rows with a percentile cycle: n = 4,716 station-hours. Code `research/provider_shadow.py`; numbers `data/strong_wind.json`. H2 not read.

## Answer in one paragraph
**Partly.** The risk flag is a genuinely useful *warning* — flagged nights reach 10 mph about **1 in 3** versus **1 in 30** unflagged (10× at night level, 19× at hour level) and it catches about **half** of breezy nights. But it is **not** a ceiling and **not** reassurance when absent: half of the ≥ 10 mph hours carry no flag and the product would read "calm/light", and the P90 value itself is below what happened on most windy hours. So the product must show the flag as a caution, never show "low risk" when the flag is absent, and never describe `ifItBlows` as a maximum.

## Results
| Measure | ≥ 10 mph observed hours (n 166) | ≥ 15 mph (n 20) |
|---|---|---|
| Flagged by P90 ≥ 10 | 81 (**48.8%** caught; 51.2% missed) | 6 (30% caught; **70% missed**) |
| "Silent" misses (no flag **and** category calm/light) | 85 (51.2%) | 14 (70%) |
| P90 ≥ observed ("ifItBlows covers it") | **31.9%** | 25% |
| Mean (P90 − observed) | −2.2 mph | **−7.4 mph** |
| Category floor below the observed category by ≥ 1 step | 86.1% | 100% |
Overall (all 4,716 hours) P90 covers the observation 77.8% (a calibrated P90 would be ≈ 90%): `ifItBlows` is optimistic, increasingly so as wind rises.

**Hour level:** flag share 4.8% of hours; of flagged hours 38.9% had observed wind below 8 mph (false alarm), POD 0.488, FAR 0.642 (reproduces the research V7).
**Night level (station-nights, window 00Z–06Z; n = 1,200; 75 breezy nights = 6.3%):** flagged nights 114; POD **0.507**, FAR 0.667; P(breezy | flagged night) **0.333** vs P(breezy | unflagged night) **0.034** (≈ 10×). Per station the hit counts are small (e.g. HSV 10 of 22 breezy nights flagged, DCU 10/17, 9A4 5/8, MSL 6/10, SNH 4/6, 4A6 1/4, 8A1 1/7, 15M 1/1): the flag works at the open-water-adjacent ASOS sites and poorly at 8A1 and 4A6 (the same stations with weak direction).
**Confidence label vs breezy frequency (hour level):** HIGH 7.2% (n 501), MEDIUM 8.2% (n 1,250), LOW 0.9% (n 2,965). The label reflects direction/forecast reliability; **it does not rank strong-wind risk**: a HIGH-confidence night is as likely to reach 10 mph as a flagged MEDIUM night. Customer copy must not read HIGH as "won't blow".

## Threshold sensitivity (information only — product threshold stays 10, frozen in the H2 pre-registration)
| P90 ≥ | flagged hours | POD | FAR |
|---|---|---|---|
| 8 mph | 13.8% | 0.70 | 0.82 |
| 9 | 8.2% | 0.59 | 0.75 |
| **10 (shipped)** | 4.8% | 0.49 | 0.64 |
| 12 | 1.6% | 0.24 | 0.47 |
A lower threshold buys detection at a steep false-alarm cost; it is not changed here.

## Is it enough?
- **As a caution:** yes. "Could turn breezy" is right often enough (33%) and discriminating enough (10×) to change a decision (choose the lee bank, bring more weight). False alarms are mostly mild nights (39% of flagged hours < 8 mph).
- **As a guarantee:** no. Half of breezy nights are unflagged and the point forecast reads light/calm on them. The product contract therefore needs: (1) absence of flag = no statement; (2) `ifItBlows` labelled "elevated case", not "worst case"; (3) strong-wind copy only from the flag, never from the mean; (4) for ≥ 15 mph nights, no claim at all (70% missed).
- **Better signal available without a new source:** the HRRR proxy's point value ≥ 10 mph caught 43% of breezy hours (FAR 0.68), similar to the flag. A "P90 flag OR HRRR ≥ 10" union could add recall, but it is a *new rule*: it must be pre-registered and tested on a fresh holdout and is **not** applied here (H2 criteria are frozen; no early look).
- **No numeric correction was added.** The bias is regime-dependent (+0.4 on calm nights, −5.7 on breezy ones); a constant would worsen the 77% of nights that are calm.

## Product consequences recorded in code/docs
`tonight.speed.note` and `breezyRisk.evidence` now state: P90 is not a ceiling; observed wind exceeded it on 22% of hours and on 68% of ≥ 10 mph hours; absence of a flag is not "low risk". (Wording only; the thresholds and the frozen H2 rules are unchanged.)
