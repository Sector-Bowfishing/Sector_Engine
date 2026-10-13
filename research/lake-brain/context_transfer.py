#!/usr/bin/env python3
"""Track 6 / Track 10 evidence: how well do the 5 pilots cover the fleet, and which ~12 additional type slots close the gap?
Reads docs/research/lake-brain/data/lake_features.csv (context_features.py).  Writes docs/research/lake-brain/data/transfer_slots.json.
Distance between two lakes = RMS of standardised differences in [log10 area, log10 residence time, log10 mean depth, log10 SDI] (missing -> class median)
 + 0.5*[regime differs] + 0.4*[region differs] + 0.25*[operator family differs].   'Covered' = nearest chosen lake within 1.0.
Greedy k-medoid: from the pilots, repeatedly add the data-eligible lake that most reduces the sum of nearest-chosen distances (no thresholds involved)."""
import json
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/lake-brain/data"
PILOTS = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]


def prep():
    df = pd.read_csv(D / "lake_features.csv").set_index("id")
    df = df[~df.lake_class.isin(["X_mega", "Z_nodata"])].copy()
    X = pd.DataFrame({"a": np.log10(df.area_ref_km2.clip(lower=0.05)), "t": np.log10(df.res_time_d.clip(lower=1)), "d": np.log10(df.mean_depth_m.clip(lower=0.5)), "s": np.log10(df.sdi_ext.clip(lower=1))}, index=df.index)
    X = X.groupby(df.lake_class).transform(lambda c: c.fillna(c.median())).fillna(X.median())
    X = (X - X.mean()) / X.std()
    # natural lakes have no meaningful residence-time class difference with reservoirs?  keep: flushing time is a real regime difference
    return df, X


def dist_matrix(df, X):
    A = X.values
    num = np.sqrt(((A[:, None, :] - A[None, :, :]) ** 2).mean(axis=2))
    def mm(col, w):
        v = np.asarray(df[col].astype(str).tolist(), dtype=object)
        return (v[:, None] != v[None, :]).astype(float) * w
    reg, rg, op = mm("regime", 0.5), mm("region", 0.4), mm("operator_family", 0.25)
    return num + reg + rg + op


def eligible(df):
    """public-data-rich candidates: operator pool feed (TVA/CWMS) or USGS gauge, a polygon, and a HydroLAKES or NID name match"""
    ok = (df.cwms | (df.operator_family == "TVA") | (df.hl_match == "name") | (df.nid_match == "name")) & df.area_km2.notna()
    return ok


def cover(dm, idx_chosen):
    nn = dm[:, idx_chosen].min(axis=1)
    return nn


SLOTS = [  # id, label, filter(df) -> boolean mask, why
    ("S01", "Run-of-river hydropower pool, SE mainstem (TVA)", lambda d: (d.lake_class == "R1_run_of_river_pool") & (d.region == "SE") & (d.operator_family == "TVA"), "pilots Guntersville/Wheeler/Wilson/Pickwick: one regime, one operator, one chain"),
    ("S02", "Run-of-river / low-head pool, non-TVA operator (USACE or utility)", lambda d: (d.lake_class == "R1_run_of_river_pool") & (d.operator_family != "TVA"), "tests whether run-of-river transfer survives a change of operator and basin"),
    ("S03", "Deep dendritic Piedmont/Appalachian storage reservoir", lambda d: (d.lake_class == "R3_dendritic_storage") & (d.region == "SE"), "Hartwell is the only pilot; needs a second, different operator (TVA Norris/Cherokee-type or USACE SAM)"),
    ("S04", "Dendritic Ozark / interior-highland storage reservoir", lambda d: (d.lake_class == "R3_dendritic_storage") & d.region.isin(["MW", "GP"]), "deep clear storage lakes outside the Southeast (Missouri/Oklahoma/Arkansas)"),
    ("S05", "Shallow open-basin Great Plains flood-control reservoir", lambda d: (d.lake_class == "R4_open_basin_storage") & d.region.isin(["GP", "MW"]) & (d.mean_depth_m < 12), "turbid, large pool swings, flats; the biggest block of the fleet"),
    ("S06", "Western storage reservoir with large drawdown (USBR / irrigation)", lambda d: d.lake_class.isin(["R3_dendritic_storage", "R4_open_basin_storage"]) & (d.region == "W"), "steep shores, multi-metre annual drawdown, snowmelt regime"),
    ("S07", "Flow-through reservoir (30-180 d residence)", lambda d: (d.lake_class == "R2_flow_through_reservoir") & d.region.isin(["SE", "GP", "MW"]) & (d.operator_family != "USBR"), "intermediate flushing; Gulf-coastal and interior lakes"),
    ("S08", "Dam-raised natural lake, northeastern glacial", lambda d: (d.lake_class == "N2_regulated_natural_lake") & (d.region == "NE"), "outlet-dam lakes with small managed range; mostly state/no-operator data"),
    ("S09", "Headwaters regulated natural lake, Upper Midwest (USACE)", lambda d: (d.lake_class == "N2_regulated_natural_lake") & d.region.isin(["MW", "GP"]), "natural basins with managed outlets, shallow, vegetated"),
    ("S10", "Natural deep lake, no dam", lambda d: (d.lake_class == "N1a_natural_deep_or_unknown") & (d.mean_depth_m > 6), "negative control for pool-management features (no operator)"),
    ("S11", "Natural shallow vegetated lake", lambda d: d.lake_class == "N1b_natural_shallow", "Florida/Upper-Midwest shallow lakes; the vegetated-flat bowfishing archetype without a dam"),
    ("S12", "Small impoundment / pond (< 2 km2)", lambda d: d.lake_class.isin(["R5_small_impoundment", "N3_small_pond_or_outlet_dam"]), "state-managed ponds; high count, low data per lake"),
]


def score(df):
    pairs = set()
    p = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/context/hypso_pairs.json")
    if p.exists(): pairs = {x["lake"] for x in json.load(open(p))}
    s = (df.cwms.astype(int) * 2 + (df.operator_family == "TVA").astype(int) * 2 + (df.usgsGage == "yes").astype(int) + (df.apiLevel == "dedicated").astype(int)
         + (df.hl_match == "name").astype(int) + (df.nid_match == "name").astype(int) + ((df.area_km2 / df.area_ref_km2) >= 0.7).astype(int) + df.index.isin(pairs).astype(int) * 2)
    return s


def main():
    df, X = prep(); dm = dist_matrix(df, X)
    ids = list(df.index); pos = {k: i for i, k in enumerate(ids)}
    chosen = [pos[p] for p in PILOTS if p in pos]
    base = cover(dm, chosen)
    el = [i for i, k in enumerate(ids) if eligible(df).iloc[i] and i not in chosen]
    rows = []
    cur = list(chosen)
    for step in range(14):
        best = None
        for c in el:
            if c in cur: continue
            nn = np.minimum(cover(dm, cur), dm[:, c]).sum()
            if best is None or nn < best[0]: best = (nn, c)
        cur.append(best[1])
        nn = cover(dm, cur)
        rows.append(dict(step=step + 1, lake=ids[best[1]], lake_class=df.lake_class.iloc[best[1]], region=df.region.iloc[best[1]], operator_family=df.operator_family.iloc[best[1]],
                         mean_nn=float(nn.mean()), cov_1_0=float((nn <= 1.0).mean()), cov_0_75=float((nn <= 0.75).mean())))
    def summ(nn):
        return dict(mean=float(nn.mean()), median=float(np.median(nn)), p90=float(np.percentile(nn, 90)), cov_0_75=float((nn <= .75).mean()), cov_1_0=float((nn <= 1.0).mean()), cov_1_25=float((nn <= 1.25).mean()))
    out = dict(n_lakes_in_metric=len(ids), pilots_only=summ(base), greedy_steps=rows,
               pilots_covered_by_class=df.loc[[p for p in PILOTS if p in df.index], "lake_class"].value_counts().to_dict(),
               class_counts=df.lake_class.value_counts().to_dict(),
               class_covered_by_pilots_share=float(df.lake_class.isin(df.loc[[p for p in PILOTS if p in df.index], "lake_class"]).mean()),
               region_covered_by_pilots_share=float(df.region.isin(df.loc[[p for p in PILOTS if p in df.index], "region"]).mean()))
    # --- rule-based type slots with data-rich candidates
    sc = score(df); slots = []; picks = []
    for sid, label, f, why in SLOTS:
        m = f(df).fillna(False)
        sub = df[m]
        if not len(sub): slots.append(dict(slot=sid, label=label, n_fleet=0)); continue
        minscore = 5 if sid in ("S01","S02","S03","S04","S05","S06","S07") else (3 if sid in ("S08","S09","S10","S11") else 3)
        ok = [k for k in sub.index if sc[k] >= minscore and k not in PILOTS] or [k for k in sub.index if k not in PILOTS]
        ii = [pos[k] for k in sub.index]; sub_dm = dm[np.ix_([pos[k] for k in ok], ii)]
        medoid_cost = sub_dm.mean(axis=1)
        ordc = pd.DataFrame({"cost": medoid_cost, "score": [sc[k] for k in ok]}, index=ok).sort_values(["cost"])
        cand = list(ordc.index[:2])
        pilot_in = [k for k in sub.index if k in PILOTS]
        slots.append(dict(slot=sid, label=label, why=why, n_fleet=int(len(sub)), pilots_in_slot=pilot_in, candidates=[dict(lake=k, score=int(sc[k]), area_km2=round(float(df.area_ref_km2[k]), 1), res_time_d=None if pd.isna(df.res_time_d[k]) else round(float(df.res_time_d[k]), 0),
                          operator=df.operator_family[k], cwms=bool(df.cwms[k]), region=df.region[k]) for k in cand]))
        if not pilot_in or sid in ("S01",): picks += cand[:1] if not pilot_in else []
        elif sid == "S01": pass
    pick_idx = [pos[k] for k in picks if k in pos]
    nn_all = cover(dm, chosen + pick_idx)
    out["slots"] = slots; out["slot_picks_first_candidate"] = picks
    out["pilots_plus_slot_picks"] = summ(nn_all)
    # also: second candidates (a spare per slot) and pilots alone vs random-12 baseline
    rng = np.random.default_rng(7); rr = []; rc = []
    for _ in range(200):
        r = rng.choice([i for i in range(len(ids)) if i not in chosen], size=len(pick_idx), replace=False)
        nn_r = cover(dm, chosen + list(r)); rr.append(nn_r.mean()); rc.append((nn_r <= 1.0).mean())
    out["random_same_k_mean_nn"] = dict(mean=float(np.mean(rr)), p5=float(np.percentile(rr, 5)), p95=float(np.percentile(rr, 95)), cov_1_0_mean=float(np.mean(rc)), cov_1_0_p95=float(np.percentile(rc, 95)))
    (D / "transfer_slots.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("pilots_only", "pilots_plus_slot_picks", "random_same_k_mean_nn", "slot_picks_first_candidate")}, indent=1))
    for s_ in slots: print(s_["slot"], s_["n_fleet"], s_["label"], [(c["lake"], c["score"]) for c in s_.get("candidates", [])])


if __name__ == "__main__":
    main()
