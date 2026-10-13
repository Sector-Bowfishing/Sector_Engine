"""Observers S / A / P on stored cell products -> per-lake belt scores -> lake-level metrics (prereg s4, s5 c/d).
Fixed before looking at results (implementation choices not in the prereg):
  * lake reference date = first NLA visit date of the lake's joined site(s); secondary mode: same calendar day in 2018 / 2019, window clipped to Jun1-Sep30
  * belt = lake cells with centre distance to polygon edge in (10, 90] m; SHORE_ADJACENT = <= 10 m (excluded); lake score UNKNOWN if < MIN_BELT seen belt cells
  * scene 'reads' coverage = (turbidity-read & not-plant clarity cells) / (not-plant clarity cells), clarity = lake eroded 40 m (lake if empty)
  * A: nearest scene with cov >= .5, else best cov >= .25, else UNKNOWN. S: nearest scene with >= 75 % of lake cells seen, else UNKNOWN.
  * P: accepted = cov >= .5; >= 3 accepted -> per-cell median of g' (plant fraction, read cells = 0) over accepted scenes where the cell is seen,
       cell needs to be seen in >= max(2, ceil(n/2)) accepted scenes else UNK_INSUFF; < 3 accepted -> evaluated as A, persistence=INSUFFICIENT
"""
import sys, json, glob, math, re, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import spearmanr
H = Path(__file__).resolve().parents[1]
MIN_BELT = 10; BELT = (10.0, 90.0)
cls = pd.read_csv(H/"out/nla_lake_classes.csv").set_index("lakeKey")
OBS = ["S", "A", "P"]
def load(key, tag):
    sc = {}
    for f in sorted(glob.glob(str(H/f"out/cells/{key}_{tag}_*.npz"))):
        d = re.search(r"_(\d{4}-\d\d-\d\d)\.npz$", f).group(1)
        z = np.load(f); sc[d] = dict(state=z["state"], fp=z["fplant"].astype("float32"), have=z["have"], dist=z["dist"].astype("float32"), lake=z["lake"], clarity=z["clarity"])
    return sc
def coverage(s):
    st = s["state"]; plant = st == 1
    cl = s["clarity"] if s["clarity"].any() else s["lake"]
    nonp = cl & ~plant
    return float((s["have"] & nonp).sum() / max(1, nonp.sum()))
def lake_seen_frac(s):
    st = s["state"]; return float(((st == 0) | (st == 1)).sum() / max(1, (st >= 0).sum()))
def observe(sc, ref):
    """-> dict obs -> (state array or None, info)"""
    dates = sorted(sc); out = {}
    if not dates: return {o: (None, {"why": "NO_SCENE"}) for o in OBS}
    cov = {d: coverage(sc[d]) for d in dates}; seenf = {d: lake_seen_frac(sc[d]) for d in dates}
    gap = lambda d: abs((pd.Timestamp(d) - pd.Timestamp(ref)).days)
    # S
    c = sorted([d for d in dates if seenf[d] >= 0.75 and gap(d) <= 21], key=gap)
    out["S"] = (sc[c[0]]["state"], {"dates": c[:1], "cov": [cov[c[0]]]}) if c else (None, {"why": "NO_CLEAR_SCENE_75"})
    # A
    acc = sorted([d for d in dates if cov[d] >= 0.5 and gap(d) <= 21], key=gap)
    if acc: Ast, Ai = sc[acc[0]]["state"], {"dates": acc[:1], "cov": [cov[acc[0]]]}
    else:
        fb = [d for d in dates if cov[d] >= 0.25 and gap(d) <= 21]
        if fb: b = max(fb, key=lambda d: cov[d]); Ast, Ai = sc[b]["state"], {"dates": [b], "cov": [cov[b]], "fallback": True}
        else: Ast, Ai = None, {"why": "NO_ACCEPTED_PASS"}
    out["A"] = (Ast, Ai)
    # P
    if len(acc) >= 3:
        fps = np.stack([np.where((sc[d]["state"] == 0) | (sc[d]["state"] == 1), sc[d]["fp"], np.nan) for d in acc])
        nseen = (~np.isnan(fps)).sum(0)
        with np.errstate(all="ignore"): med = np.nanmedian(fps, axis=0)
        lake = sc[acc[0]]["lake"]; need = max(2, math.ceil(len(acc) / 2))
        st = np.full(lake.shape, -1, "int8"); st[lake] = 4
        ok = lake & (nseen >= need)
        st[ok & (med < 0.5)] = 0; st[ok & (med >= 0.5)] = 1
        # carry cloud/dark causes for cells never seen: majority cause over accepted scenes
        for code in (2, 3):
            frac = np.mean([sc[d]["state"] == code for d in acc], axis=0); st[lake & ~ok & (frac >= 0.5)] = code
        out["P"] = (st, {"dates": acc, "cov": [cov[d] for d in acc], "persistence": "OK"})
    else:
        out["P"] = (Ast, dict(Ai, persistence="INSUFFICIENT", n_accepted=len(acc))) if Ast is not None else (None, {"why": "NO_ACCEPTED_PASS", "persistence": "INSUFFICIENT"})
    return out

def belt_stats(st, dist, lake, lo=BELT[0], hi=BELT[1]):
    sa = lake & (dist <= lo); belt = lake & (dist > lo) & (dist <= hi)
    b = st[belt]
    r = dict(shore_adj=int(sa.sum()), belt_cells=int(belt.sum()), belt_plant=int((b == 1).sum()), belt_open=int((b == 0).sum()),
             unk_cloud=int((b == 2).sum()), unk_dark=int((b == 3).sum()), unk_insuff=int((b == 4).sum()))
    seen = r["belt_plant"] + r["belt_open"]
    r["belt_seen"] = seen; r["belt_share"] = r["belt_plant"] / seen if seen >= MIN_BELT else np.nan
    # distance-binned (for standardisation)
    for (a, c_), nm in (((10, 30), "b1"), ((30, 60), "b2"), ((60, 90), "b3")):
        m = lake & (dist > a) & (dist <= c_); s = st[m]
        r[nm+"_plant"] = int((s == 1).sum()); r[nm+"_seen"] = int(((s == 0) | (s == 1)).sum())
    # 40-90 (production erosion variant) and whole lake (exploratory)
    m4 = lake & (dist > 40) & (dist <= 90); s4 = st[m4]; r["b40_plant"] = int((s4 == 1).sum()); r["b40_seen"] = int(((s4 == 0) | (s4 == 1)).sum())
    ml = lake & (dist > lo); sl = st[ml]; r["lake_plant"] = int((sl == 1).sum()); r["lake_seen"] = int(((sl == 0) | (sl == 1)).sum())
    return r

def run():
    rows = []
    for key in cls.index[cls.n_stations > 0]:
        ref0 = pd.Timestamp(cls.loc[key, "visit_dates"].split(";")[0])
        for tag, mode, ref in (("p2017", "primary", ref0), ("s2018", "secondary", ref0.replace(year=2018)), ("s2019", "secondary", ref0.replace(year=2019))):
            sc = load(key, tag)
            if key == "Lake_Mead_NV": res = {o: (None, {"why": "SKIPPED_TOO_LARGE"}) for o in OBS}
            else: res = observe(sc, ref)
            for o in OBS:
                st, info = res[o]
                row = dict(lakeKey=key, mode=mode, tag=tag, observer=o, ref=ref.date().isoformat(), n_scenes=len(sc), info=json.dumps(info))
                if st is None:
                    row["why"] = info.get("why")
                else:
                    s0 = next(iter(sc.values()))
                    row.update(belt_stats(st, s0["dist"], s0["lake"])); row["why"] = None if not np.isnan(row["belt_share"]) else "BELT_TOO_SMALL"
                    row["persistence"] = info.get("persistence", ""); row["gap_d"] = (min(abs((pd.Timestamp(d) - ref).days) for d in info["dates"]) if info.get("dates") else None)
                rows.append(row)
    df = pd.DataFrame(rows)
    meta = cls[["name", "state", "epa_reg", "eco9", "areaKm2", "n_stations", "mean_emerg", "mean_float", "mean_ef", "frac_stations_ge2", "cls"]]
    df = df.merge(meta, left_on="lakeKey", right_index=True, how="left")
    df.to_csv(H/"out/nla_lake_scores.csv", index=False)
    return df

def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if len(pos) == 0 or len(neg) == 0: return np.nan
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))

def metrics(d, score="belt_share", rng=np.random.default_rng(20261013)):
    d = d.dropna(subset=[score]).copy()
    out = dict(n_scored=len(d), n_pos=int((d.cls == "POS").sum()), n_neg=int((d.cls == "NEG").sum()), n_amb=int((d.cls == "AMB").sum()),
               n_regions=int(d.epa_reg.nunique()), n_states=int(d.state.nunique()))
    if len(d) >= 4:
        rho = spearmanr(d[score], d.mean_ef); out["spearman"] = float(rho.statistic) if hasattr(rho, "statistic") else float(rho[0])
    else: out["spearman"] = np.nan
    pos, neg = d[d.cls == "POS"][score].values, d[d.cls == "NEG"][score].values
    out["auc"] = auc(pos, neg)
    # bootstrap over lakes (2000)
    B = []; R = []
    idx = np.arange(len(d)); v = d[score].values; m = d.mean_ef.values; c = d.cls.values
    for _ in range(2000):
        s = rng.choice(idx, len(idx));
        a = auc(v[s][c[s] == "POS"], v[s][c[s] == "NEG"])
        if not np.isnan(a): B.append(a)
        if len(set(v[s])) > 1 and len(set(m[s])) > 1: R.append(spearmanr(v[s], m[s])[0])
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) > 50 else [np.nan, np.nan]
    out["auc_ci95"] = q(B); out["spearman_ci95"] = q(R)
    negd = d[d.cls == "NEG"]
    out["neg_mean_belt_share"] = float(negd[score].mean()) if len(negd) else np.nan
    out["neg_max_belt_share"] = float(negd[score].max()) if len(negd) else np.nan
    out["neg_n_over_2pct"] = int((negd[score] > 0.02).sum()) if len(negd) else 0
    out["neg_pooled_cell_share"] = float(negd.belt_plant.sum() / max(1, negd.belt_seen.sum())) if len(negd) else np.nan
    out["neg_mean_whole_lake_share"] = float((negd.lake_plant / negd.lake_seen.replace(0, np.nan)).mean()) if len(negd) else np.nan
    out["median_share_pos"] = float(np.median(pos)) if len(pos) else np.nan; out["median_share_neg"] = float(np.median(neg)) if len(neg) else np.nan
    return out

def gates(m):
    ok_n = m["n_scored"] >= 15 and m["n_regions"] >= 3
    if not ok_n or np.isnan(m["auc"]) or np.isnan(m["spearman"]):
        c = "NOT_TESTABLE"
    else:
        c = "PASS" if (m["auc"] >= 0.80 and m["spearman"] >= 0.50) else "FAIL"
    if m["n_neg"] == 0 or np.isnan(m["neg_mean_belt_share"]): dgate = "NOT_TESTABLE"
    else: dgate = "PASS" if m["neg_mean_belt_share"] <= 0.02 else "FAIL"
    return c, dgate

if __name__ == "__main__":
    df = run(); res = {}; secs = {}
    def add_variants(sub):
        sub = sub.copy()
        sub["b40_share"] = np.where(sub.b40_seen >= MIN_BELT, sub.b40_plant / sub.b40_seen.replace(0, np.nan), np.nan)
        # distance-standardised belt score: bins 10-30/30-60/60-90 weighted by the pooled (all scored lakes) seen-cell share of each bin
        W = np.array([sub[f"b{i}_seen"].sum() for i in (1, 2, 3)], float); W = W / W.sum()
        def std(r):
            num = den = 0.0
            for w, i in zip(W, (1, 2, 3)):
                s_ = r[f"b{i}_seen"]
                if s_ >= 3: num += w * r[f"b{i}_plant"] / s_; den += w
            return num / den if den > 0 and r["belt_seen"] >= MIN_BELT else np.nan
        sub["std_share"] = sub.apply(std, axis=1)
        return sub
    for mode in ("primary", "secondary"):
        for o in OBS:
            sub = df[(df["mode"] == mode) & (df.observer == o)].copy()
            if mode == "secondary":   # pooled over the two years: mean of available year scores per lake
                agg = sub.groupby("lakeKey").agg(belt_share=("belt_share", "mean"), belt_plant=("belt_plant", "sum"), belt_seen=("belt_seen", "sum"), lake_plant=("lake_plant", "sum"), lake_seen=("lake_seen", "sum"),
                    **{f"b{i}_{k}": (f"b{i}_{k}", "sum") for i in (1, 2, 3) for k in ("plant", "seen")}, b40_plant=("b40_plant", "sum"), b40_seen=("b40_seen", "sum")).reset_index()
                sub = agg.merge(cls[["name", "state", "epa_reg", "mean_ef", "cls"]], left_on="lakeKey", right_index=True)
            sub = add_variants(sub)
            m = metrics(sub); m["gate_c"], m["gate_d"] = gates(m); res[f"{mode}/{o}"] = m
            for sc_ in ("b40_share", "std_share"):
                mm = metrics(sub, score=sc_); mm["gate_c"], mm["gate_d"] = gates(mm); res[f"{mode}/{o}/{sc_}"] = mm
            sub.to_csv(H/f"out/nla_lakelevel_{mode}_{o}.csv", index=False)
    json.dump(res, open(H/"out/nla_metrics.json", "w"), indent=1, default=float)
    for k, v in res.items(): print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()})
