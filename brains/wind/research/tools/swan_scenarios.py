"""Stage 3E §28: SWAN 41.51 offline reference scenarios (reference physics, NOT truth; never used for selection or scoring).

  python research/swan_scenarios.py run OUT.json

Idealised square basins (1 km and 5 km side), flat 10 m depth, closed boundaries, output at the centre.
Wind phase A for 12 h (spin-up) then phase B for 12 h; hourly uniform wind via INPGRID WIND NONSTATIONARY.
SWAN: GEN3 (default Komen), nonstationary, dt 2 min, BSBT propagation, 36 directions, 0.1-2.0 Hz. Compared with the Stage 3E Python
mirror of the frozen CEM (M0) and the CAL-chosen memory models (M2, M3) driven by the same hourly wind."""
import json, math, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import wave_memory as W

WORK = os.path.expanduser("~/Library/Caches/sector-wind/swan/runs")
FITS = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/derived/score-acceleration/wave_memory_fits.json")
SCEN = {   # name: (phase A (speed, from-dir), phase B list of 12 hourly (speed, from-dir))
    "steady8": ((8, 270), [(8, 270)] * 12),
    "steady5": ((5, 270), [(5, 270)] * 12),
    "increase4to10": ((4, 270), [(10, 270)] * 12),
    "decrease10to4": ((10, 270), [(4, 270)] * 12),
    "drop10toCalm": ((10, 270), [(0.5, 270)] * 12),
    "rampDown10to2": ((10, 270), [(10 - 8 * min(1, k / 6), 270) for k in range(1, 13)]),
    "shift15": ((8, 270), [(8, 255)] * 12),
    "shift30": ((8, 270), [(8, 240)] * 12),
    "shift60": ((8, 270), [(8, 210)] * 12),
    "reverse": ((8, 270), [(8, 90)] * 12),
    "pulse2h": ((1, 270), [(10, 270)] * 2 + [(1, 270)] * 10),
    "gustyAlt": ((8, 270), [((10 if k % 2 else 6), 270) for k in range(12)]),
}
BASINS = {"1km": 1000.0, "5km": 5000.0}


def fetch_table(L):
    """Distance from the centre to the square's edge upwind, 120 bearings (3°), as the frozen 9-ray mean expects."""
    t = []
    for b in range(120):
        th = math.radians(b * 3.0)            # FROM bearing; upwind ray points toward the bearing
        dx, dy = math.sin(th), math.cos(th)
        t.append(min((L / 2) / abs(dx) if abs(dx) > 1e-9 else 1e18, (L / 2) / abs(dy) if abs(dy) > 1e-9 else 1e18))
    return t


def swan(name, L, hours):
    d = os.path.join(WORK, f"{name}_{int(L)}"); os.makedirs(d, exist_ok=True)
    n = 20                                     # 50 m cells (1 km), 250 m cells (5 km)
    files = []
    for i, (s, fr) in enumerate(hours):
        u, v = -s * math.sin(math.radians(fr)), -s * math.cos(math.radians(fr))      # toward-components
        fn = f"w{i:03d}.txt"; open(os.path.join(d, fn), "w").write(f"{u} {u}\n{u} {u}\n{v} {v}\n{v} {v}\n"); files.append(fn)
    open(os.path.join(d, "series.txt"), "w").write("\n".join(files) + "\n")
    open(os.path.join(d, "bot.txt"), "w").write("10 10\n10 10\n")
    T0 = "20260101.000000"; tend = f"20260102.{(len(hours) - 1 - 24) if len(hours) > 24 else 0:02d}0000"
    end_h = len(hours) - 1
    tend = f"202601{1 + end_h // 24:02d}.{end_h % 24:02d}0000"
    cmd = f"""PROJECT 'sector' '3e'
SET LEVEL 0 NAUTICAL
MODE NONSTATIONARY TWODIMENSIONAL
COORDINATES CARTESIAN
CGRID REGULAR 0 0 0 {L} {L} {n} {n} CIRCLE 36 0.1 2.0 40
INPGRID BOTTOM REGULAR 0 0 0 1 1 {L} {L}
READINP BOTTOM 1 'bot.txt' 1 0 FREE
INPGRID WIND REGULAR 0 0 0 1 1 {L} {L} NONSTATIONARY {T0} 1 HR {tend}
READINP WIND 1 SERIES 'series.txt' 1 0 FREE
GEN3
PROP BSBT
OFF QUAD
QUADRUPL
NUM ACCUR 0.02 0.02 0.02 98 NONSTAT 3
POINTS 'P' {L / 2} {L / 2}
TABLE 'P' NOHEAD 'out.tab' TIME HS OUTPUT {T0} 1 HR
COMPUTE NONSTAT {T0} 2 MIN {tend}
STOP
"""
    cmd = cmd.replace("OFF QUAD\nQUADRUPL\n", "")
    open(os.path.join(d, "INPUT"), "w").write(cmd)
    done_ = os.path.join(d, "out.tab")
    if os.path.exists(done_) and sum(1 for l in open(done_) if l.strip() and l.split()[0][0].isdigit()) == len(hours):
        pass
    else:
      subprocess.run(["docker", "run", "--rm", "-v", f"{d}:/data", "sector-swan:41.51", "bash", "-c", "cd /data && swan.exe > swan.log 2>&1 || true"], check=True)
    out = []
    p = os.path.join(d, "out.tab")
    if os.path.exists(p):
        for l in open(p):
            q = l.split()
            if len(q) >= 2 and q[0][0].isdigit():
                out.append(float(q[1]))
    return out


def run(outp):
    fits = json.load(open(FITS))["chosen"]
    m3 = {"cont": (fits["M3"]["cont"][0], tuple(fits["M3"]["cont"][1])), "tau": fits["M3"]["tau"]}; m2 = {"tau": fits["M2"]["tau"]}
    res = {}
    for bname, L in BASINS.items():
        tab = fetch_table(L)
        for name, (A, B) in SCEN.items():
            hours = [A] * 13 + B          # hour 0..12 phase A, 13..24 phase B
            hs = swan(name, L, hours)
            rows = []
            for t in range(12, len(hours)):
                ser = [{"speedMS": s, "dirFromDeg": fr} for s, fr in hours[max(0, t - 12):t + 1]]
                s, fr = hours[t]
                r = {"windMS": s, "dirFromDeg": fr, "fetchM": W.nine_ray(tab, fr), "series": ser}
                rows.append({"hour": t, "wind": s, "dir": fr, "swan": hs[t] if t < len(hs) else None,
                             "M0": W.predict(r, tab, "M0", {}), "M2": W.predict(r, tab, "M2", m2), "M3": W.predict(r, tab, "M3", m3)})
            res[f"{bname}|{name}"] = rows
            ok = [x for x in rows if x["swan"] is not None]
            print(bname, name, "swan n", len(hs), " ".join(f"{m}:{np.mean([abs(x[m] - x['swan']) for x in ok]):.3f}" for m in ("M0", "M2", "M3")) if ok else "NO SWAN OUTPUT", flush=True)
    json.dump(res, open(outp, "w"), indent=1)


if __name__ == "__main__":
    run(sys.argv[2])
