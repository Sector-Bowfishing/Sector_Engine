"""Supplementary (non-gate): station-level local plant fraction (3x3 cells around the station, seen cells only) for stations inside polygon, 10 < d <= 90 m.
Uses observer states re-derived through n5_score.observe for the primary / secondary modes."""
import sys, json, numpy as np, pandas as pd, pyproj
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nlalib as L, n5_score as N
H = L.H
stn = pd.read_csv(H/"out/nla_station_geometry.csv"); stn = stn[stn.has_xy & stn.inside & (stn.d_edge_m > 10) & (stn.d_edge_m <= 90)]
cls = N.cls
out = []
for key, g in stn.groupby("lakeKey"):
    if key == "Lake_Mead_NV": continue
    poly = L.load_poly(key); fr = L.C.Frame(poly)
    tx = pyproj.Transformer.from_crs("EPSG:4326", L.C.WEB_MERCATOR, always_xy=True)
    ref0 = pd.Timestamp(cls.loc[key, "visit_dates"].split(";")[0])
    for tag, mode, ref in (("p2017", "primary", ref0), ("s2018", "secondary", ref0.replace(year=2018)), ("s2019", "secondary", ref0.replace(year=2019))):
        sc = N.load(key, tag)
        if not sc: continue
        res = N.observe(sc, ref)
        for o in N.OBS:
            st = res[o][0]
            if st is None: continue
            for _, s in g.iterrows():
                x, y = tx.transform(s.lon, s.lat); c = int((x - fr.left) // fr.cell); r = int((fr.top - y) // fr.cell)
                w = st[max(0, r-1):r+2, max(0, c-1):c+2]; seen = ((w == 0) | (w == 1)).sum()
                out.append(dict(lakeKey=key, mode=mode, tag=tag, observer=o, station=s.station, emerg=s.emerg, floating=s.floating, d_edge_m=s.d_edge_m,
                                local_plant=(w == 1).sum() / seen if seen >= 3 else np.nan, n_seen=int(seen)))
d = pd.DataFrame(out); d.to_csv(H/"out/nla_station_level.csv", index=False)
d["ef"] = d.emerg.fillna(0) + d.floating.fillna(0); d["pos"] = (d.emerg.fillna(0) >= 2) | (d.floating.fillna(0) >= 2); d["neg"] = (d.emerg.fillna(-1) == 0) & (d.floating.fillna(-1) == 0)
res = {}
for (mode, o), g in d.dropna(subset=["local_plant"]).groupby(["mode", "observer"]):
    gg = g.groupby(["lakeKey", "station"]).agg(lp=("local_plant", "mean"), pos=("pos", "first"), neg=("neg", "first"), ef=("ef", "first")).reset_index()
    a = N.auc(gg[gg.pos].lp, gg[gg.neg].lp)
    from scipy.stats import spearmanr
    res[f"{mode}/{o}"] = dict(n_stations=len(gg), n_pos=int(gg.pos.sum()), n_neg=int(gg.neg.sum()), auc_code2_vs_zero=a, spearman_ef=float(spearmanr(gg.lp, gg.ef)[0]) if len(gg) > 5 else None)
json.dump(res, open(H/"out/nla_station_level_metrics.json", "w"), indent=1, default=float); print(json.dumps(res, indent=1, default=float))
