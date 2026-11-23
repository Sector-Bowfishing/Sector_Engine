"""Source readers. Each returns a `Reading`: what one operator or agency published for one dam, exactly as published (units converted to
cfs / ft / MW only). No reader derives a value the source did not state: SWPA's megawatts are never turned into units or discharge, and a
missing value stays missing. Pool elevation is Lake Brain's domain and is never read here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..contract import iso

FT3_PER_M3 = 35.3146667
FT_PER_M = 3.28084


@dataclass
class Reading:
    provider: str
    agency: str
    ok: bool
    error: str | None = None
    observations: list = field(default_factory=list)   # [{"at": iso, "dischargeCfs"?, "turbineCfs"?, "spillCfs"?, "generationMw"?, "tailwaterFt"?}]
    schedule: list = field(default_factory=list)       # [{"start": iso, "end": iso, "unitsOn"?, "unitsOnIsMinimum"?, "generationMw"?}]
    series: list = field(default_factory=list)         # identifiers read ("tva:GVDA1:observed-data-48-hours", "cwms:SWL:Bull_Shoals...")
    cadence_min: int = 60                               # how often the source publishes a new value
    lag_min: int = 60                                   # how late a value usually appears
    series_timing: dict = field(default_factory=dict)  # per field: {"turbineCfs": (cadence_min, lag_min)} when series differ (CWMS)
    meta: dict = field(default_factory=dict)           # source facts the state names (USGS: site, distanceMiles)

    def timing(self, key: str) -> tuple[int, int]:
        return self.series_timing.get(key, (self.cadence_min, self.lag_min))

    def ceiling_min(self, key: str) -> int:
        """A value counts as current until its series is overdue: lag + 3 x cadence (the Lake Brain stale rule), per series."""
        cadence, lag = self.timing(key)
        return lag + 3 * cadence

    def summary(self, retrieved_at: datetime) -> dict:
        return {"provider": self.provider, "agency": self.agency, "ok": self.ok, "error": self.error, "series": list(self.series),
                "retrievedAt": iso(retrieved_at), "observationCount": len(self.observations), "scheduleWindows": len(self.schedule)}


def failed(provider: str, agency: str, error: str, series=()) -> Reading:
    return Reading(provider, agency, False, error, series=list(series))


def merge_observations(obs: list[dict]) -> list[dict]:
    """One row per timestamp (later keys fill earlier gaps for the same time), oldest first."""
    by: dict[str, dict] = {}
    for o in obs:
        row = by.setdefault(o["at"], {"at": o["at"]})
        for k, v in o.items():
            if v is not None:
                row[k] = v
    return [by[k] for k in sorted(by)]
