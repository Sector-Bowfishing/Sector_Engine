"""H2 holdout runner (criteria frozen in docs/brains/wind/WIND_H2_PREREG.md; SHA-256 in WIND_H2_PREREG.freeze.json).

  python -m sector_wind.h2 --store local:<mirror> --ledger <path>/h2_ledger.json

* Refuses before 2027-01-01 00:00 UTC (H2_SEALED_UNTIL) and refuses a second run (one-shot ledger). A refusal reads NO H2 row.
* Categories, confidence and the breezy-risk flag come from brain/tonight.py: the product and its test cannot drift.
* The pure scoring (`score_rows`) takes plain rows so it is unit-tested on synthetic data without touching any archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

from .brain import contract as C
from .brain import tonight as TN
from .sample import circular_error

MPH = 0.44704
PREREG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "docs", "brains", "wind")
H2_START = datetime(2026, 10, 7, tzinfo=timezone.utc)
H2_END_INIT = datetime(2026, 12, 31, 23, tzinfo=timezone.utc)


class Sealed(Exception):
    pass


def prereg_ok(prereg_dir: str = PREREG) -> bool:
    fz = json.load(open(os.path.join(prereg_dir, "WIND_H2_PREREG.freeze.json")))
    return hashlib.sha256(open(os.path.join(prereg_dir, fz["file"]), "rb").read()).hexdigest() == fz["sha256"]


def gate(now: datetime, ledger_path: str | None, prereg_dir: str = PREREG) -> None:
    if not prereg_ok(prereg_dir):
        raise Sealed("pre-registration file does not match its freeze hash; refusing")
    if now < C.H2_SEALED_UNTIL:
        raise Sealed(f"H2 is sealed until {C.iso(C.H2_SEALED_UNTIL)}; no H2 row was read")
    if ledger_path and os.path.exists(ledger_path):
        raise Sealed("H2 already run (one-shot ledger exists); no H2 row was read")


def _verdict(n, minimum, ok):
    return "INSUFFICIENT" if n < minimum else ("PASS" if ok else "FAIL")


def score_rows(rows: list[dict], pairs: list[dict]) -> dict:
    """rows: tonight rows {fcMph, p90Mph|None, obsMph, fcDir, obsDir, night:bool, lead:int}; pairs: {fc00, fc06, obs00, obs06} mph.
    Every threshold below is copied from the frozen table; do not edit without a v2 pre-registration."""
    out = {}
    # D1 / D2: direction (night, lead <= 12 h, observed >= 2.6 m/s)
    dr = [r for r in rows if r["night"] and r["lead"] <= 12 and r.get("fcDir") is not None and r.get("obsDir") is not None and r["obsMph"] * MPH >= 2.6]
    def within(sel):
        e = [circular_error(r["fcDir"], r["obsDir"]) for r in sel]
        return (len(e), (sum(x <= 22.5 for x in e) / len(e)) if e else None)
    n1, v1 = within([r for r in dr if 5 <= r["fcMph"] < 10])
    n2, v2 = within([r for r in dr if r["fcMph"] >= 10])
    out["H2-D1"] = {"n": n1, "within22_5": v1, "rule": ">= 0.75", "verdict": _verdict(n1, 500, v1 is not None and v1 >= 0.75)}
    out["H2-D2"] = {"n": n2, "within22_5": v2, "rule": ">= 0.85", "verdict": _verdict(n2, 100, v2 is not None and v2 >= 0.85)}
    # S1: category
    n = len(rows)
    if n:
        oc = [TN.CATEGORIES.index(TN.category(r["obsMph"])) for r in rows]; fcc = [TN.CATEGORIES.index(TN.category(r["fcMph"])) for r in rows]
        exact = sum(a == b for a, b in zip(oc, fcc)) / n; w1 = sum(abs(a - b) <= 1 for a, b in zip(oc, fcc)) / n
        modal = max(set(oc), key=oc.count); base = sum(a == modal for a in oc) / n
    else:
        exact = w1 = base = None
    out["H2-S1"] = {"n": n, "exact": exact, "within1": w1, "modalBaseline": base, "rule": "exact >= 0.65 and within1 >= 0.95 and exact > baseline",
                    "verdict": _verdict(n, 1000, n > 0 and exact >= 0.65 and w1 >= 0.95 and exact > base)}
    # S2: descriptive strong-wind bias
    st = [r for r in rows if r["obsMph"] >= 10]
    out["H2-S2"] = {"events": len(st), "meanBiasMph": round(sum(r["fcMph"] - r["obsMph"] for r in st) / len(st), 2) if st else None,
                    "rule": "descriptive (expect negative)", "verdict": "INSUFFICIENT" if len(st) < 30 else "REPORTED"}
    # T1 / T2 / T3 from pairs
    cls = lambda d: 0 if d <= -2 else 2 if d >= 2 else 1
    po = [cls(p["obs06"] - p["obs00"]) for p in pairs]; pf = [cls(p["fc06"] - p["fc00"]) for p in pairs]
    m = len(pairs)
    if m:
        acc = sum(a == b for a, b in zip(po, pf)) / m; base_t = sum(a == 1 for a in po) / m
        fe = [(a, b) for a, b in zip(po, pf) if b == 0]; prec = (sum(a == 0 for a, _ in fe) / len(fe)) if fe else None
    else:
        acc = base_t = prec = None; fe = []
    out["H2-T1"] = {"pairs": m, "accuracy": acc, "alwaysSteady": base_t, "easingForecasts": len(fe), "easingPrecision": prec,
                    "rule": "accuracy >= steady + 0.05 and easing precision >= 0.55",
                    "verdict": "INSUFFICIENT" if (m < 1000 or len(fe) < 100) else ("PASS" if acc >= base_t + 0.05 and prec >= 0.55 else "FAIL")}
    ld_o = [p["obs00"] >= 8 and p["obs06"] <= 5 for p in pairs]; ld_f = [p["fc00"] >= 8 and p["fc06"] <= 5 for p in pairs]
    ev = sum(ld_o); hit = sum(a and b for a, b in zip(ld_o, ld_f)); fc = sum(ld_f)
    pod = hit / ev if ev else None; far = (fc - hit) / fc if fc else None
    out["H2-T2"] = {"events": ev, "POD": pod, "FAR": far, "rule": "claim allowed only if POD >= 0.40 and FAR <= 0.50",
                    "verdict": "INSUFFICIENT" if ev < 50 else ("PASS" if (pod is not None and pod >= 0.40 and far is not None and far <= 0.50) else "FAIL")}
    ri_o = [b == 2 for b in po]; ri_f = [b == 2 for b in pf]; rev = sum(ri_o); rh = sum(a and b for a, b in zip(ri_o, ri_f)); rf = sum(ri_f)
    rrec = rh / rev if rev else None; rprec = rh / rf if rf else None
    out["H2-T3"] = {"observedRises": rev, "recall": rrec, "precision": rprec, "rule": "claim allowed only if recall >= 0.40 and precision >= 0.55",
                    "verdict": "INSUFFICIENT" if rev < 50 else ("PASS" if (rrec or 0) >= 0.40 and (rprec or 0) >= 0.55 else "FAIL")}
    # B1: breezy risk flag
    pr = [r for r in rows if r.get("p90Mph") is not None]
    fl = [TN.breezy_flag(r["p90Mph"]) for r in pr]; ob = [r["obsMph"] >= 10 for r in pr]
    nf, nev = sum(fl), sum(ob)
    p_on = (sum(a and b for a, b in zip(fl, ob)) / nf) if nf else None
    off = [b for a, b in zip(fl, ob) if not a]; p_off = (sum(off) / len(off)) if off else None
    pod_b = (sum(a and b for a, b in zip(fl, ob)) / nev) if nev else None
    lift = (p_on / p_off) if (p_on is not None and p_off) else (float("inf") if p_on and p_off == 0 else None)
    out["H2-B1"] = {"rows": len(pr), "flagged": nf, "events": nev, "P_event_given_flag": p_on, "P_event_given_noflag": p_off, "lift": lift, "POD": pod_b,
                    "rule": "lift >= 3 and POD >= 0.40",
                    "verdict": "INSUFFICIENT" if (nev < 30 or nf < 50) else ("PASS" if (lift is not None and lift >= 3 and pod_b >= 0.40) else "FAIL")}
    # C1 / C2: confidence label by the product rule
    lab = []
    for r in pr:
        lab.append(TN.confidence(r["fcMph"], TN.breezy_flag(r["p90Mph"]), False)[0])
    hi = [r for r, l in zip(pr, lab) if l == "HIGH" and r.get("fcDir") is not None and r.get("obsDir") is not None and r["obsMph"] * MPH >= 2.6]
    nh, vh = within(hi)
    out["H2-C1"] = {"n": nh, "within22_5": vh, "rule": ">= 0.75", "verdict": _verdict(nh, 300, vh is not None and vh >= 0.75)}
    def err_rate(sel):
        sel = [r for r in sel if r.get("fcDir") is not None and r.get("obsDir") is not None and r["obsMph"] >= 3]
        return len(sel), (sum(circular_error(r["fcDir"], r["obsDir"]) > 45 for r in sel) / len(sel)) if sel else None
    nH, eH = err_rate([r for r, l in zip(pr, lab) if l == "HIGH"]); nN, eN = err_rate([r for r, l in zip(pr, lab) if l != "HIGH"])
    ok = eH is not None and eN is not None and eH <= 0.5 * eN
    out["H2-C2"] = {"nHigh": nH, "nNotHigh": nN, "errRateHigh": eH, "errRateNotHigh": eN, "rule": "HIGH error rate <= 0.5 x not-HIGH",
                    "verdict": "INSUFFICIENT" if (nH < 200 or nN < 200) else ("PASS" if ok else "FAIL")}
    return out


def collect_rows(store, cfg, start: datetime, end: datetime):
    """H2 rows from the archive (same collection as the research: validate.collect + the percentile cycles). Only called after gate()."""
    from datetime import timedelta
    from .interp import CutoutIndex, blend
    from .validate import collect, load_obs
    from .sample import parse_iso
    obs = load_obs(store, start - timedelta(days=1), end + timedelta(days=2))
    by_key = {}
    for m in collect(store, cfg, start, end, (6, 12, 18), obs):
        i, l = m["init"], m["lead"]
        if (i.hour == 12 and l in (12, 18)) or (i.hour == 18 and l in (6, 12)):
            by_key[(m["lake"], m["station"], i, m["validTime"])] = m
    idx, rows, pairs_src = {}, [], {}
    stations = {}
    for sid, s in cfg["stations"].items():
        stations.setdefault(s["lake"], []).append(sid)
    for (lake, sid, init, vt), m in sorted(by_key.items()):
        cyc = store.get_json(f"nbm/{lake}/{init:%Y%m%d%H}.json.gz")
        p90 = None
        if cyc and cyc.get("hasPercentiles"):
            if lake not in idx:
                g = store.get_json(cyc["grid"]); ci = CutoutIndex(g["cells"], g["lat"], g["lon"], g["nx"])
                idx[lake] = {s: ci.weights(cfg["stations"][s]["lat"], cfg["stations"][s]["lon"]) for s in stations[lake]}
            st = next((s for s in cyc["steps"] if s["leadHours"] == m["lead"]), None)
            if st and st.get("speedP90"):
                p90 = blend(st["speedP90"], idx[lake][sid])
        fs, fd, _fg, os_, od, _og = m["rec"]
        rows.append({"fcMph": fs / MPH, "p90Mph": None if p90 is None else p90 / MPH, "obsMph": os_ / MPH, "fcDir": fd, "obsDir": od,
                     "night": 1 <= vt.hour <= 8, "lead": m["lead"], "_k": (lake, sid, init), "_h": vt.hour})
    byk = {}
    for r in rows:
        byk.setdefault(r["_k"], {})[r["_h"]] = r
    pairs = [{"fc00": d[0]["fcMph"], "fc06": d[6]["fcMph"], "obs00": d[0]["obsMph"], "obs06": d[6]["obsMph"]} for d in byk.values() if 0 in d and 6 in d]
    return rows, pairs


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        gate(now, a.ledger)
    except Sealed as e:
        print(f"H2 NOT RUN: {e}")
        return 2
    from .store import LocalStore
    from .ingest import load_config
    store = LocalStore(a.store.split(":", 1)[1]); cfg = load_config()
    json.dump({"startedAt": C.iso(now), "preregSha256": json.load(open(os.path.join(PREREG, "WIND_H2_PREREG.freeze.json")))["sha256"]}, open(a.ledger, "w"))
    rows, pairs = collect_rows(store, cfg, H2_START, H2_END_INIT)
    res = score_rows(rows, pairs)
    json.dump({"ranAt": C.iso(now), "rows": len(rows), "pairs": len(pairs), "results": res}, open(a.out, "w"), indent=1, default=str)
    print(json.dumps({k: v["verdict"] for k, v in res.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
