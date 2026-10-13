"""Lake-level NLA cover codes and class (prereg s4)."""
import numpy as np, pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parents[4]; H = Path(__file__).resolve().parents[1]
phab = pd.read_csv(R/"sources/nla_2017_phab/nla_2017_phab-data.csv", low_memory=False)
j = pd.read_csv(H/"out/nla_fleet_join.csv")
# a site mapped to 2 lakes: keep both rows (flagged); a lake with 2 sites: keep the visit-1 site rows of each
rows=[]
for (k), g in j.groupby("lakeKey"):
    sids = list(g.SITE_ID)
    p = phab[phab.SITE_ID.isin(sids) & (phab.VISIT_NO==1)]
    p = p.dropna(subset=["AM_EMERGENT","AM_FLOATING"], how="all")
    n = len(p)
    ef = p[["AM_EMERGENT","AM_FLOATING"]].fillna(0).sum(axis=1) if n else pd.Series(dtype=float)
    # "mean(emergent, floating) station cover code" = mean over stations of the mean of the two codes
    mean_ef = float(((p.AM_EMERGENT.fillna(0)+p.AM_FLOATING.fillna(0))/2).mean()) if n else np.nan
    mean_sum = float(ef.mean()) if n else np.nan   # emergent+floating (alt. reading: lake-mean of sum)
    ge2 = float((((p.AM_EMERGENT.fillna(0)>=2)|(p.AM_FLOATING.fillna(0)>=2))).mean()) if n else np.nan   # station at code>=2 in emergent OR floating
    ge2_mean = float((((p.AM_EMERGENT.fillna(0)+p.AM_FLOATING.fillna(0))/2)>=2).mean()) if n else np.nan
    allzero = bool(n and ((p.AM_EMERGENT.fillna(-1)==0)&(p.AM_FLOATING.fillna(-1)==0)&(p.AM_TOTALCOVER.fillna(-1)==0)).all())
    pos = bool(n and (mean_ef>=1.0 or ge2>=0.2))
    cls = "POS" if pos else ("NEG" if allzero else "AMB") if n else "NO_COVER_ROWS"
    r0 = g.iloc[0]
    rows.append(dict(lakeKey=k,name=r0["name"],state=r0.state,epa_reg=r0.epa_reg,eco9=r0.eco9,areaKm2=r0.areaKm2,SITE_IDs=";".join(sids),visit_dates=";".join(g.date),
        n_stations=n,n_stat_emerg=int(p.AM_EMERGENT.notna().sum()) if n else 0,mean_emerg=float(p.AM_EMERGENT.mean()) if n else np.nan,mean_float=float(p.AM_FLOATING.mean()) if n else np.nan,
        mean_total=float(p.AM_TOTALCOVER.mean()) if n else np.nan,mean_ef=mean_ef,mean_ef_sum=mean_sum,frac_stations_ge2=ge2,cls=cls))
d = pd.DataFrame(rows); d.to_csv(H/"out/nla_lake_classes.csv", index=False)
print(d.cls.value_counts()); print(d.groupby(["epa_reg","cls"]).size().unstack(fill_value=0)); print(d.groupby(["state","cls"]).size().unstack(fill_value=0))
print(d[["n_stations"]].describe().T)
# sensitivity: pos by the alternative reading (cover in either lifeform / sum)
print("pos if mean(sum)>=1:", int((d.mean_ef_sum>=1).sum()))
