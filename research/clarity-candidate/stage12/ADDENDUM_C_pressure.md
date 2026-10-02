# Addendum C to PREREGISTRATION_STAGE12.md: surface pressure at the lake

Recorded after 59 of 1,631 corpus rows had been processed, and before any corpus reflectance or visibility metric was
computed. Those 59 rows were seen only as a count of valid disks and as the flags of one station.

**Found.** At a clear lake at 2,318 m (Wind River Range, WY), every pixel of the 60 m disk carried ACOLITE's
negative-reflectance flag. The red and green surface reflectance were −0.0014 and −0.0009. ACOLITE had used its
default sea-level pressure of 1013.25 hPa, where the standard atmosphere gives about 765 hPa. The Rayleigh term was
therefore over-subtracted. That is a physical input error, not a tuning choice, and it removes most high-elevation clear
water from any ACOLITE run with the default.

**Change.**
- Every corpus crop (and S2C harmonised run) sets ACOLITE `elevation` to the USGS 3DEP elevation (Elevation Point Query
  Service) of the crop's first station. ACOLITE converts it to pressure with its standard-atmosphere function.
- If the service returns no value, the crop keeps the default.
- The tandem validation keeps the default, because its A and C runs share a scene and so share any pressure error.

**Effect on Part 1.** All five AERONET-OC sites sit near sea level: Lake Erie 174 m, the others 0–44 m. Their pressure
changes by at most 2%, so the Part 1 ranking and BEST are not affected. As a check, K4 is rerun with the elevation on
the 10 Lake Erie matchups, and the change is reported. Part 1's selection is not revisited.

**Restart.** The 59 processed corpus rows are discarded, and the whole corpus is run with the corrected configuration.
