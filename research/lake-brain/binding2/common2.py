"""binding2 (wave 2, thread 'gaps') shared paths + imports. Wave-1 modules are imported from ../binding (not copied)."""
import sys, os
sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import *            # noqa: F401,F403  (DATA, BIND, RAW, http_get, get_json, haversine_m, name_sim, load_directory ...)
B2 = os.path.join(DATA, "binding2")
for d in ("cand", "history", "raw", "notes", "probe"):
    os.makedirs(os.path.join(B2, d), exist_ok=True)
DOCS = "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain"
FEAT = f"{DOCS}/data/lake_features.csv"
