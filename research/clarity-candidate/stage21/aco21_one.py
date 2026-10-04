"""Stage 21: one crop through the FROZEN ACOLITE path (stage20/aco20_one.py, unchanged) with an ADDITIVE top-of-atmosphere
offset removed from S2C's L1R rhot (B08, B8A, B11, B12) before atmospheric correction (PREREGISTRATION_STAGE21.md 3a).
ACOLITE's own offsets_toa multiplies, so ac.sentinel2.l1_convert is wrapped. Overrides key "_toa_sub": {"B08": x, ...};
without it this is exactly aco20_one.py.
  python aco21_one.py INPUT LAT LON OUTDIR POINTS_JSON OVERRIDES_JSON"""
import json, sys, os
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage11/tools/acolite")
import run_acolite  # sets the ACOLITE source path (as aco12_one)
import acolite as ac
from netCDF4 import Dataset
ov = json.loads(sys.argv[6]); SUB = ov.pop("_toa_sub", None); sys.argv[6] = json.dumps(ov)
WAVE = {"B08": 833.0, "B8A": 865.0, "B11": 1612.0, "B12": 2190.0}
if SUB:
    _orig = ac.sentinel2.l1_convert
    def _wrapped(*a, **k):
        files, setu = _orig(*a, **k)
        for f in files:
            with Dataset(f, "a") as nc:
                rh = [n for n in nc.variables if n.startswith("rhot_")]
                for b, v in SUB.items():
                    names = [n for n in rh if abs(float(n.split("_")[1]) - WAVE[b]) <= 15]
                    assert len(names) == 1, (b, names, rh)
                    nc[names[0]][:] = nc[names[0]][:] - v
        return files, setu
    ac.sentinel2.l1_convert = _wrapped
exec(open(f"{S}/stage20/aco20_one.py").read())
