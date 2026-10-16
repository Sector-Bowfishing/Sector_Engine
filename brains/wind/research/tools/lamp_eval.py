"""Score Acceleration §6–8: station GFS-LAMP vs NBM (pre-registered: score-acceleration/WIND_LAMP_PREREG.md, sha 9f7efd98…).

  python research/lamp_eval.py parse            # raw monthly bulletins -> lamp/parsed.pkl  {(station, run, valid): (spdMS, dirDeg, gustMS|None, ng)}
  python research/lamp_eval.py eval OUT.json    # same rows vs NBM (CAL + H1 only); untuned

LAMP run HH:30 is paired with NBM init HH; lead = valid − HH. Nothing is fitted."""
import gzip, glob, json, os, pickle, re, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "runtime"))  # brains/wind/runtime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

L = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50/lamp")
ROWS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/stage3d/rows.pkl")
KT = 0.514444
STATIONS = {"K4A6": "4A6", "KDCU": "DCU", "KHSV": "HSV", "KMSL": "MSL", "KSNH": "SNH", "K8A1": "8A1", "K9A4": "9A4", "K15M": "15M"}
HDR = re.compile(r"^ (K\w{3})\s+GFS LAMP GUIDANCE\s+(\d+)/(\d+)/(\d{4})\s+(\d{2})(\d{2}) UTC")


def parse():
    out = {}
    for p in sorted(glob.glob(os.path.join(L, "raw", "lmp_lavtxt.*.gz"))):
        lines = gzip.open(p, "rt", errors="replace").read().split("\n")
        i = 0
        while i < len(lines):
            m = HDR.match(lines[i])
            if not m or m.group(1) not in STATIONS:
                i += 1; continue
            sid = STATIONS[m.group(1)]
            run = datetime(int(m.group(4)), int(m.group(2)), int(m.group(3)), int(m.group(5)), int(m.group(6)), tzinfo=timezone.utc)
            blk = {}
            j = i + 1
            while j < len(lines) and lines[j].strip():
                key = lines[j][1:4]; blk[key] = lines[j][5:]
                j += 1
            if "UTC" in blk and "WSP" in blk:
                cols = [blk["UTC"][k:k + 3] for k in range(0, len(blk["UTC"]), 3)]
                t = run.replace(minute=0)
                for c, hh in enumerate(cols):
                    if not hh.strip():
                        continue
                    t = t + timedelta(hours=1)
                    while t.hour != int(hh):
                        t += timedelta(hours=1)
                    get = lambda k: blk.get(k, "")[c * 3:c * 3 + 3].strip()
                    ws, wd, wg = get("WSP"), get("WDR"), get("WGS")
                    if not ws.isdigit():
                        continue
                    s = int(ws) * KT
                    d = int(wd) * 10 if wd.isdigit() and not (int(wd) == 0 and int(ws) == 0) else None
                    g = int(wg) * KT if wg.isdigit() else None
                    out[(sid, run, t)] = (s, d, g, wg == "NG")
            i = j
    pickle.dump(out, open(os.path.join(L, "parsed.pkl"), "wb"))
    runs = {k[1] for k in out}
    print(len(out), "station-valid rows;", len(runs), "runs;", sorted({k[0] for k in out}))


def evaluate(outp):
    import stage3d2_eval as E
    LP = pickle.load(open(os.path.join(L, "parsed.pkl"), "rb"))
    R = pickle.load(open(ROWS, "rb"))
    P = []
    for r in R:
        if r["set"] not in ("CAL", "H1"):
            continue
        x = LP.get((r["station"], r["init"] + timedelta(minutes=30), r["valid"]))
        if x is None:
            continue
        s, d, g, ng = x
        P.append((r, (s, d, g if g is not None else (s if ng else None))))
    T6 = E.cem_table("6.0")
    res = {"rows": len(P), "stations": sorted({p[0]["station"] for p in P}),
           "all": E.block(P, T6), "CAL": E.block([p for p in P if p[0]["set"] == "CAL"], T6), "H1": E.block([p for p in P if p[0]["set"] == "H1"], T6)}
    # pre-registered gust event uses NG = no event; conditional bias only where a gust is forecast or NG (sustained)
    json.dump(res, open(outp, "w"), indent=1, default=str); print("wrote", outp, len(P))


if __name__ == "__main__":
    {"parse": parse, "eval": lambda: evaluate(sys.argv[2])}[sys.argv[1]]()
