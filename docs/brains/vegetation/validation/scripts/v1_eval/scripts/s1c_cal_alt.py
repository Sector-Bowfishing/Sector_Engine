"""POST-HOC, NOT USED: alternative calibration cuts on the two calibration lakes only (never an evaluation lake), to inform a future amendment."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import warnings; warnings.filterwarnings("ignore")
from multiprocessing import Pool
import s1_calibrate as S
def w(a):
    lk, f = a
    r = S.work(a)[2]
    if r is None or not r["acc"]: return None
    return lk, int(f.stem[5:7]), r["h"], r["h_seen"]
if __name__ == "__main__":
    jobs = [(lk, f) for lk in S.LAKES for f in sorted((S.SEAS / "cache" / lk).glob("2*.npz"))]
    with Pool(6) as p: r = [x for x in p.map(w, jobs, chunksize=8) if x]
    def pct(h, q): c = np.cumsum(h); k = int(np.searchsorted(c, q * c[-1])); return round((k - 1000) * 1e-4, 4)
    out = {}
    for name, sel in (("all months, both lakes (the A3 rule)", lambda lk, m: True), ("Jun-Sep, both lakes", lambda lk, m: 6 <= m <= 9), ("Jun-Sep, Leech only", lambda lk, m: lk == "Leech_Lake_MN" and 6 <= m <= 9),
                      ("Jun-Sep, Hartwell only", lambda lk, m: lk == "Lake_Hartwell_SC" and 6 <= m <= 9), ("Apr-Oct excluding Mar-Apr ice shoulder, both", lambda lk, m: 5 <= m <= 10)):
        h = sum((x[2] for x in r if sel(x[0], x[1])), np.zeros(S.NB, np.int64)); hs = sum((x[3] for x in r if sel(x[0], x[1])), np.zeros(S.NB, np.int64))
        out[name] = dict(P99=pct(h, .99), P995=pct(h, .995), P995_seen_only=pct(hs, .995), n_px=int(h.sum()))
        print(name, out[name])
    json.dump(out, open(OUT / "calibration_alt_cuts_NOT_USED.json", "w"), indent=1)
