"""Shared config for the seasonal back-test. Research only."""
from pathlib import Path
import sys, json
H = Path(__file__).resolve().parents[1]                       # .../adoption/seasonal
R = Path(__file__).resolve().parents[4]                       # vegetation-brain
EXP = R / "experiments"
sys.path.insert(0, str(EXP / "scripts"))
# (lakeKey, lake class, short label)
LAKES = [
 ("Guntersville_AL",            "SE reservoir",         "Guntersville AL"),
 ("Lake_Hartwell_SC",           "SE reservoir",         "Hartwell SC/GA"),
 ("Istokpoga_FL",               "Florida",              "Istokpoga FL"),
 ("Orange_Lake_FL",             "Florida",              "Orange Lake FL"),
 ("Fern_Ridge_Reservoir_OR",    "Pacific NW",           "Fern Ridge OR"),
 ("Lake_Sammamish_WA",          "Pacific NW",           "Sammamish WA"),
 ("Sam_Rayburn_Reservoir_TX",   "Texas reservoir",      "Sam Rayburn TX"),
 ("Lake_Pepin_MN",              "Upper Midwest/river pool", "Lake Pepin MN/WI"),
 ("Chippewa_Flowage_WI",        "Northern ice-affected", "Chippewa Flowage WI"),
 ("Leech_Lake_MN",              "Northern ice-affected", "Leech Lake MN"),
 ("Milford_Lake_KS",            "Plains reservoir",     "Milford KS"),
 ("Clear_Lake_CA",              "Southwest/California", "Clear Lake CA"),
]
NOT_RUN = ["Sam_Rayburn_Reservoir_TX", "Chippewa_Flowage_WI", "Milford_Lake_KS", "Clear_Lake_CA"]   # fetch stopped: download budget already exceeded (see note 08 s2)
ALL_PLANNED = list(LAKES)
LAKES = [x for x in LAKES if x[0] not in NOT_RUN]
CLASS = {k: c for k, c, _ in LAKES}; LABEL = {k: l for k, _, l in LAKES}
WIN_KM = 5.0   # analysis-window side cap (km)
