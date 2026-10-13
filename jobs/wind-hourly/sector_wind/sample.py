"""Canonical wind sample (Python mirror of the Swift `WindSample`).

Rules (pre-registration §2.1):
- `kind` is required and carries the provenance that matters for it: an observation has a
  station, an analysis has an analysis time, a forecast has a model, an init time and a lead.
- Speed is m/s at 10 m unless `sensorHeightM` says otherwise. Direction is meteorological
  FROM, degrees true, [0, 360); nil when calm or unknown. u/v are earth-relative motion TOWARD.
- A missing gust is None, never 0. Unknown speed is None, never 0."""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal, Optional, Union

CALM_MS = 0.5


@dataclass(frozen=True)
class Observed:
    station: str
    network: str
    sensorHeightM: float
    averaging: str            # e.g. "2-min"
    kind: Literal["observed"] = "observed"


@dataclass(frozen=True)
class Analysis:
    product: str              # "RTMA-RU" | "RTMA" | "URMA"
    analysisTime: datetime
    kind: Literal["analysis"] = "analysis"


@dataclass(frozen=True)
class Forecast:
    model: str                # "NBM" | "HRRR"
    modelVersion: str
    initTime: datetime
    leadHours: float
    kind: Literal["forecast"] = "forecast"


WindKind = Union[Observed, Analysis, Forecast]


@dataclass(frozen=True)
class Uncertainty:
    speedP10: Optional[float] = None
    speedP50: Optional[float] = None
    speedP90: Optional[float] = None
    gustP90: Optional[float] = None


@dataclass(frozen=True)
class WindSample:
    kind: WindKind                         # required, no default
    validTime: datetime
    retrievedAt: datetime
    lat: float
    lon: float
    speedMS: Optional[float]
    dirFromDeg: Optional[float]
    gustMS: Optional[float]
    source: str                            # bucket/object key or URL
    decoderVersion: str
    gridCell: Optional[tuple[int, int]] = None
    gridSpacingKm: Optional[float] = None
    uncertainty: Optional[Uncertainty] = None

    def __post_init__(self):
        if not isinstance(self.kind, (Observed, Analysis, Forecast)):
            raise TypeError("WindSample.kind must be Observed, Analysis or Forecast")
        if self.speedMS is not None and (self.speedMS < 0 or math.isnan(self.speedMS)):
            raise ValueError("speed must be >= 0 or None")
        if self.dirFromDeg is not None and not (0.0 <= self.dirFromDeg < 360.0):
            raise ValueError("dirFromDeg must be in [0, 360) or None")
        if self.isCalm and self.dirFromDeg is not None:
            raise ValueError("a calm sample carries no direction")

    @property
    def isCalm(self) -> bool:
        return self.speedMS is not None and self.speedMS < CALM_MS

    @property
    def u(self) -> Optional[float]:
        if self.speedMS is None or self.dirFromDeg is None:
            return 0.0 if self.isCalm else None
        return -self.speedMS * math.sin(math.radians(self.dirFromDeg))

    @property
    def v(self) -> Optional[float]:
        if self.speedMS is None or self.dirFromDeg is None:
            return 0.0 if self.isCalm else None
        return -self.speedMS * math.cos(math.radians(self.dirFromDeg))

    def referenceTime(self) -> datetime:
        k = self.kind
        if isinstance(k, Forecast):
            return k.initTime
        if isinstance(k, Analysis):
            return k.analysisTime
        return self.validTime

    def ageHours(self, now: datetime) -> float:
        return (now - self.referenceTime()).total_seconds() / 3600.0


def make_sample(kind: WindKind, valid: datetime, retrieved: datetime, lat: float, lon: float,
                speed: Optional[float], dir_from: Optional[float], gust: Optional[float], source: str,
                decoder: str, **kw) -> WindSample:
    """Normalises calm (direction -> None) and NaN (-> None) on the way in."""
    nn = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
    speed, dir_from, gust = nn(speed), nn(dir_from), nn(gust)
    if speed is not None and speed < CALM_MS:
        dir_from = None
    if dir_from is not None:
        dir_from = dir_from % 360.0
    return WindSample(kind, valid, retrieved, lat, lon, speed, dir_from, gust, source, decoder, **kw)


def circular_error(a: float, b: float) -> float:
    """|smallest angle| between two FROM directions, degrees. 359 vs 1 -> 2."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
