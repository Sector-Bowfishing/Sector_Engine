#!/usr/bin/env python3
"""Track 7: empirical stage-area curve from a USACE CWMS project's own daily pool elevation + storage series:
area(z) = dStorage/dz (acre-ft per ft = acres). Test on Hartwell; works for any CWMS lake with Elev-Pool and Stor daily series.
Output: <DATA>/context/hypso_cwms_<lake>.json (rebuildable)."""
import json, sys, time
from pathlib import Path
import numpy as np, requests
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
B = "https://cwms-data.usace.army.mil/cwms-data/timeseries"


def series(office, name, begin, end):
    r = requests.get(B, params=dict(office=office, name=name, begin=begin, end=end, unit="EN", **{"page-size": 20000}),
                     headers={"Accept": "application/json;version=2"}, timeout=120).json()
    return {int(t // 86400000): v for t, v, q in r.get("values", []) if v is not None}


def run(office, proj, elev_name, stor_name, begin="1990-01-01T00:00:00Z", end="2026-03-01T00:00:00Z"):
    z = series(office, elev_name, begin, end); time.sleep(1); s = series(office, stor_name, begin, end)
    d = sorted(set(z) & set(s)); Z = np.array([z[k] for k in d]); S = np.array([s[k] for k in d])
    return d, Z, S


def curve(Z, S, width=1.0):
    """binned slope dS/dz using bins of `width` ft; returns [(z_mid, area_ac, n)]"""
    out = []
    lo, hi = np.floor(Z.min()), np.ceil(Z.max())
    for z0 in np.arange(lo, hi, width):
        m = (Z >= z0) & (Z < z0 + width)
        out.append((z0 + width / 2, float(S[m].mean()) if m.any() else None, int(m.sum())))
    # area between bin centres
    res = []
    for (z1, s1, n1), (z2, s2, n2) in zip(out[:-1], out[1:]):
        if s1 is not None and s2 is not None and n1 >= 20 and n2 >= 20:
            res.append(dict(z_ft=z2 - 0.5 * (z2 - z1), area_ac=(s2 - s1) / (z2 - z1), n=min(n1, n2)))
    return res


if __name__ == "__main__":
    d, Z, S = run("SAS", "Hartwell", "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS", "Hartwell.Stor.Inst.1Day.0.ARCHIVE-DAILY", "1990-01-01T00:00:00Z", "2026-03-01T00:00:00Z")
    c = curve(Z, S, 2.0)
    out = dict(lake="Lake Hartwell|SC", n_days=len(d), z_range=[float(Z.min()), float(Z.max())], stor_range=[float(S.min()), float(S.max())], curve=c)
    (DATA / "context/hypso_cwms_hartwell.json").write_text(json.dumps(out, indent=1))
    for r in c: print(round(r["z_ft"], 1), round(r["area_ac"]), r["n"])
