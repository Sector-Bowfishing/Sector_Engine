"""Stage 12 Part 2: write a harmonised copy of an S2C ACOLITE L1R that ACOLITE processes as S2A (acolite venv).
  python harm_l1r.py IN_L1R OUT_L1R COEF_JSON MODE
COEF_JSON: {"coef": {band: {g, o[, k]}}} at TOA; MODE: vfull (every fitted band) or vop (operational bands only).
rho_t(S2A-eq) = g*rho_t(S2C) + o (+ k*(rho_t B06 - rho_t B04) for B05, from the raw S2C values). Variables are
renamed to S2A's band names and the per-band wave/name/f0 attributes and the sensor are set to S2A's (template)."""
import json, sys, shutil, numpy as np, netCDF4 as nc
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
TEMPLATE = json.load(open(f"{S}/stage12/harm/s2a_l1r_template.json"))
IDS = ["1", "2", "3", "4", "5", "6", "7", "8", "8A", "9", "10", "11", "12"]
BID = {i: ("B8A" if i == "8A" else f"B{int(i):02d}") for i in IDS}
OPER = ["B05", "B08", "B8A", "B11", "B12"]


def main(inp, outp, coefp, mode):
    co = json.load(open(coefp))["coef"]
    shutil.copy(inp, outp)
    d = nc.Dataset(outp, "r+")
    name = {i: str(d.getncattr(f"{i}_name")) for i in IDS if f"{i}_name" in d.ncattrs()}
    raw = {BID[i]: np.array(d[f"rhot_{n}"][:], dtype="float64") for i, n in name.items() if f"rhot_{n}" in d.variables}
    bands = list(co) if mode == "vfull" else OPER
    for i, n in name.items():
        b = BID[i]; v = f"rhot_{n}"
        if v not in d.variables: continue
        if b in bands and b in co:
            c = co[b]; x = c["g"] * raw[b] + c["o"]
            if b == "B05": x = x + c["k"] * (raw["B06"] - raw["B04"])
            d[v][:] = x.astype(d[v].dtype)
        new = f"rhot_{TEMPLATE['bands'][i]['name']}"
        d[v].setncattr("wavelength", TEMPLATE["bands"][i]["wave"]); d[v].setncattr("parameter", new)
        if new != v: d.renameVariable(v, new)
        for a in ("wave", "name", "f0"):
            d.setncattr(f"{i}_{a}", TEMPLATE["bands"][i][a])
    d.setncattr("sensor", "S2A_MSI")
    d.setncattr("harmonised", f"S2C->S2A Stage 12 ({mode})")
    d.close()


if __name__ == "__main__":
    main(*sys.argv[1:5])
