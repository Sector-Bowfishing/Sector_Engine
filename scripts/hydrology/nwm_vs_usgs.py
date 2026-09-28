"""The National Water Model against the two measured arms, every day both
exist (Clarity Fusion Stage 2, item 7: never assume the model's skill from
one snapshot).

Each day at 16Z: the NWM analysis for the arm's reach (nwm_history.py) and
the USGS 15-min discharge nearest 16Z (within 1 h). Reported per gauge:
bias and spread of log10(NWM/USGS), share within ±30% and within 2x, by flow
regime (USGS terciles), rank correlation, and events -- does the model rise
when the gauge does (day-over-day >= 2x), and does the gauge rise when the
model does.

usage: python3 nwm_vs_usgs.py <usgs_iv.json> <nwm_daily.json> <out.json>
"""
import sys, json, math, bisect, datetime as dt, statistics as st

usgs = json.load(open(sys.argv[1])); nwm = json.load(open(sys.argv[2])); out = sys.argv[3]
PAIRS = {"town-creek-marshall": ("03572900", "19649040"), "south-sauty-creek": ("03572690", "19648816")}


def parse_t(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def rank(xs):
    o = sorted(range(len(xs)), key=lambda i: xs[i]); r = [0] * len(xs)
    for k, i in enumerate(o): r[i] = k
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b); n = len(a)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def q(xs, p):
    xs = sorted(xs); return xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]


res = {"source": {"usgs": "USGS IV 00060, value nearest 16Z within 1 h", "nwm": nwm.get("source")}, "arms": {}}
for arm, (site, reach) in PAIRS.items():
    pts = usgs[site]; ts = [parse_t(t) for t, _ in pts]; vs = [v for _, v in pts]
    rows = []
    for day, vals in sorted(nwm["days"].items()):
        if not vals or reach not in vals:
            continue
        t = dt.datetime.fromisoformat(day + "T16:00:00+00:00")
        i = bisect.bisect_left(ts, t); best = None
        for j in (i - 1, i):
            if 0 <= j < len(ts) and abs((ts[j] - t).total_seconds()) <= 3600:
                if best is None or abs((ts[j] - t).total_seconds()) < abs((ts[best] - t).total_seconds()):
                    best = j
        if best is None:
            continue
        rows.append({"day": day, "usgs": vs[best], "nwm": vals[reach]})
    lr = [math.log10(max(r["nwm"], 0.01) / max(r["usgs"], 0.01)) for r in rows]
    u = [r["usgs"] for r in rows]; m = [r["nwm"] for r in rows]
    t1, t2 = q(u, 1 / 3), q(u, 2 / 3)
    def block(sel):
        x = [l for l, r in zip(lr, rows) if sel(r)]
        if not x: return None
        return {"days": len(x), "medianRatio": round(10 ** st.median(x), 2),
                "ratio10to90": [round(10 ** q(x, .1), 2), round(10 ** q(x, .9), 2)],
                "within30pct": round(sum(abs(10 ** v - 1) <= 0.3 for v in x) / len(x), 3),
                "within2x": round(sum(abs(v) <= math.log10(2) for v in x) / len(x), 3)}
    # events: day-over-day >= 2x rises
    ev_u = ev_m = hit_u = hit_m = 0
    for a, b in zip(rows, rows[1:]):
        if (dt.date.fromisoformat(b["day"]) - dt.date.fromisoformat(a["day"])).days != 1:
            continue
        ur = b["usgs"] / max(a["usgs"], 0.01) >= 2; mr = b["nwm"] / max(a["nwm"], 0.01) >= 2
        if ur:
            ev_u += 1; hit_u += mr
        if mr:
            ev_m += 1; hit_m += ur
    res["arms"][arm] = {
        "usgsSite": site, "nwmReach": reach, "daysBoth": len(rows),
        "from": rows[0]["day"] if rows else None, "to": rows[-1]["day"] if rows else None,
        "all": block(lambda r: True),
        "lowFlow (USGS lowest third)": block(lambda r: r["usgs"] <= t1),
        "midFlow": block(lambda r: t1 < r["usgs"] <= t2),
        "highFlow (USGS highest third)": block(lambda r: r["usgs"] > t2),
        "usgsTercilesCfs": [round(t1, 2), round(t2, 2)],
        "spearman": round(spearman(u, m), 3) if len(rows) > 3 else None,
        "gaugeRises2xDayOverDay": ev_u, "modelAlsoRose2x": hit_u,
        "modelRises2xDayOverDay": ev_m, "gaugeAlsoRose2x": hit_m,
        "rows": rows}
    a = res["arms"][arm]
    print(arm, a["daysBoth"], "days", a["from"], "->", a["to"], "| all", a["all"], "| rho", a["spearman"])
    for k in ("lowFlow (USGS lowest third)", "midFlow", "highFlow (USGS highest third)"): print("   ", k, a[k])
    print("    gauge 2x rises", ev_u, "model also", hit_u, "| model 2x rises", ev_m, "gauge also", hit_m)
json.dump(res, open(out, "w"), indent=1)
