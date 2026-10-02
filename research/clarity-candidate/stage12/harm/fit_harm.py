"""Stage 12 Part 2 (PREREGISTRATION_STAGE12.md section 2): S2C -> S2A-equivalent harmonisation from the Stage 11
tandem water pixels only. Per band A = g*C + o (+ k*(C_B06 - C_B04) for B05); least squares, every pair weighted
equally, pixels with |A-C| > 5 robust SD from the pair median dropped. TOA and BOA versions. Production fit on all
12 pairs; validation by leave-one-pair-out. Writes harm_prod.json, harm_lopo.json."""
import json, numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"]
OPERATIONAL_TOA = ["B05", "B08", "B8A", "B11", "B12"]
_NPZ = np.load(f"{S}/stage11/tandem/tandem_pixels.npz")
PAIRS = sorted(_NPZ.files)
NPZ = {p: _NPZ[p] for p in PAIRS}          # decompress once


def arrays(pair, level):
    a = NPZ[pair]; nb = len(BANDS)
    off = {"toa": (0, nb), "boa": (2 * nb, 3 * nb)}[level]
    A = {b: a[off[0] + i].astype("float64") for i, b in enumerate(BANDS)}
    C = {b: a[off[1] + i].astype("float64") for i, b in enumerate(BANDS)}
    return A, C


def design(C, b):
    cols = [C[b], np.ones_like(C[b])]
    if b == "B05": cols.append(C["B06"] - C["B04"])
    return np.stack(cols, axis=1)


def fit(pairs, level):
    coef = {}
    for b in BANDS:
        Xs, ys, ws = [], [], []
        for p in pairs:
            A, C = arrays(p, level)
            X = design(C, b); y = A[b]
            ok = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
            d = (y - C[b])[ok]
            if d.size < 50: continue
            med = np.median(d); rsd = 1.4826 * np.median(np.abs(d - med)) or 1e-6
            keep = np.zeros_like(ok); keep[np.flatnonzero(ok)] = np.abs(d - med) <= 5 * rsd
            Xs.append(X[keep]); ys.append(y[keep]); ws.append(np.full(keep.sum(), 1.0 / keep.sum()))
        X, y, w = np.vstack(Xs), np.concatenate(ys), np.concatenate(ws)
        sw = np.sqrt(w)
        beta = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
        coef[b] = {"g": float(beta[0]), "o": float(beta[1]), **({"k": float(beta[2])} if b == "B05" else {}), "pairs": len(Xs), "pixels": int(len(y))}
    return coef


def apply(C, coef, bands):
    """C: {band: array} of S2C values -> S2A-equivalent for the listed bands (others unchanged)."""
    out = dict(C)
    for b in bands:
        c = coef[b]; v = c["g"] * C[b] + c["o"]
        if b == "B05": v = v + c["k"] * (C["B06"] - C["B04"])
        out[b] = v
    return out


if __name__ == "__main__":
    prod = {lv: fit(PAIRS, lv) for lv in ("toa", "boa")}
    json.dump({"pairs": PAIRS, "operational_toa_bands": OPERATIONAL_TOA, "coef": prod}, open(f"{S}/stage12/harm/harm_prod.json", "w"), indent=1)
    lopo = {p: {lv: fit([q for q in PAIRS if q != p], lv) for lv in ("toa", "boa")} for p in PAIRS}
    json.dump(lopo, open(f"{S}/stage12/harm/harm_lopo.json", "w"), indent=1)
    for lv in ("toa", "boa"):
        print(lv, {b: (round(c["g"], 4), round(c["o"], 5), round(c.get("k", 0), 4)) for b, c in prod[lv].items()})
