#!/usr/bin/env python3
"""Track 7 validation step 2: derive the real near-full-pool stage-area slope from CWMS daily Elev + Stor for each pair in hypso_pairs.json.
Method: align daily Z (ft) and S (ac-ft); keep days within the top 15 ft below the 95th-percentile pool (z_ref) ; fit S = a + b*(z-z_ref) + c*(z-z_ref)^2;
A_ref = b (ac, area at z_ref); dA/dz = 2c (ac per ft).  rel_per_ft = 2c / b.  Quality gates: >= 800 days, range >= 5 ft, b > 0.
Output <DATA>/context/hypso_truth.json"""
import json, time
from pathlib import Path
import numpy as np, requests
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
B = "https://cwms-data.usace.army.mil/cwms-data/timeseries"
H = {"Accept": "application/json;version=2"}


def series(office, name, begin="1990-01-01T00:00:00Z", end="2026-10-01T00:00:00Z"):
    out = {}
    page = None
    for _ in range(40):
        params = dict(office=office, name=name, begin=begin, end=end, unit="EN", **{"page-size": 20000})
        if page: params["page"] = page
        r = None
        for a in range(4):
            try:
                rr = requests.get(B, params=params, headers=H, timeout=240)
                if rr.status_code == 200: r = rr.json(); break
                if rr.status_code in (400, 404): return out
            except Exception: pass
            time.sleep(3 * (a + 1))
        if not r: return out
        for t, v, q in r.get("values", []):
            if v is not None: out[int(t // 86400000)] = v
        page = r.get("next-page")
        if not page: break
        time.sleep(0.3)
    return out


def fit(Z, S):
    zr = np.percentile(Z, 95)
    m = (Z >= zr - 15) & (Z <= zr + 3)
    if m.sum() < 300 or (Z[m].max() - Z[m].min()) < 5: return None
    x = Z[m] - zr; y = S[m]
    c, b, a = np.polyfit(x, y, 2)
    if b <= 0: return None
    # R2 of the fit
    res = y - (a + b * x + c * x * x); r2 = 1 - res.var() / y.var()
    return dict(z_ref=float(zr), A_ref_ac=float(b), dA_dz_ac_per_ft=float(2 * c), rel_per_ft=float(2 * c / b), n_days=int(m.sum()), r2=float(r2), zmin=float(Z[m].min()), zmax=float(Z[m].max()))


if __name__ == "__main__":
    pairs = json.load(open(DATA / "context/hypso_pairs.json"))
    outp = DATA / "context/hypso_truth.json"
    out = json.load(open(outp)) if outp.exists() else {}
    for p in pairs:
        key = p["lake"] + "#" + p["loc"]
        if key in out: continue
        z = series(p["office"], p["elev"][0]); time.sleep(0.5); s = series(p["office"], p["stor"][0]); time.sleep(0.5)
        d = sorted(set(z) & set(s)); rec = dict(p, n_overlap=len(d))
        if len(d) >= 800:
            Z = np.array([z[k] for k in d]); S = np.array([s[k] for k in d])
            rec["fit"] = fit(Z, S)
        out[key] = rec
        print(key, len(d), rec.get("fit") and {k: round(v, 3) for k, v in rec["fit"].items()}, flush=True)
        outp.write_text(json.dumps(out, indent=1))
