"""Stage 20 EXPLORATORY (not pre-registered; no verdict uses it): aco20_one.py with an ADDITIVE top-of-atmosphere offset
removed from chosen bands of the L1R before ACOLITE's atmospheric correction (ACOLITE's own offsets_toa multiplies, so it
cannot be used). The offsets come from the derivation tandem pairs only (S2C re-calibrated to nominal minus S2A, water
disks). Overrides key "_toa_sub": {"B8A": x, ...}.
  python aco20x_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON"""
import json, sys, os
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage11/tools/acolite")
import run_acolite  # sets the ACOLITE source path (as aco12_one)
import acolite as ac
from netCDF4 import Dataset
ov = json.loads(sys.argv[6]); SUB = ov.pop("_toa_sub"); sys.argv[6] = json.dumps(ov)
WAVE = {"B8A": "865", "B11": "1610", "B12": "2190"}
_orig = ac.sentinel2.l1_convert
def _wrapped(*a, **k):
    files, setu = _orig(*a, **k)
    for f in files:
        with Dataset(f, "a") as nc:
            for b, v in SUB.items():
                names = [n for n in nc.variables if n.startswith("rhot_") and abs(float(n.split("_")[1]) - float(WAVE[b])) <= 12]
                assert len(names) == 1, (b, names)
                x = nc[names[0]][:]; nc[names[0]][:] = x - v
    return files, setu
ac.sentinel2.l1_convert = _wrapped
exec(open(f"{S}/stage20/aco20_one.py").read())
