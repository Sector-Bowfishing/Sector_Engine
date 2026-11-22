"""Weather Brain (`brainId: weather`): per-lake Sky, Barometric Pressure, Air Temperature and Humidity from NWS station observations and the
NWS forecast grid, plus the weather-change signal. Rules: brains/weather/BRAIN_OPERATING_CONTRACT.md; contract: contracts/weather-state-v1.md."""
from .contract import BRAIN_ID, BRAIN_VERSION  # noqa: F401
