#!/usr/bin/env python3
"""Depth Brain / effective depth: which vertical datum do the bound level series (and pool figures) live in?
Evidence: USACE Access2Water location records (vertical_datum per project, cached by the Lake Brain binding thread), USGS parameter codes of bound gauges
(62614 = elevation above NGVD29, 62615 = elevation above NAVD88, 00062 = reservoir elevation, datum per site, 00065 = gage height above a local gage datum), providers.
Output docs/research/depth-brain/data/datum_inventory.json.  venv python."""
import collections, glob, json
from pathlib import Path
import pandas as pd
REPO = Path(__file__).resolve().parents[2]
LB = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data")
v1 = pd.read_csv(LB / "verified_bindings.csv"); v2 = pd.read_csv(LB / "verified_bindings_v2.csv")
vb = pd.concat([v2, v1[~v1.lake_id.isin(v2.lake_id)]]); vb = vb[vb.binding_status.str.startswith("VERIFIED")].drop_duplicates("lake_id")
loc = {}
for f in glob.glob("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding/raw/a2w/locations_*.json"):
    for it in json.load(open(f)): loc[(it["provider"], it["code"])] = it
norm = lambda d: {"ngvd29": "NGVD29", "ngvd1929": "NGVD29", "local datum 1": "LOCAL"}.get((d or "").strip().lower(), (d or "").strip() or "unrecorded")
out = {"n_bound_lakes": int(len(vb)), "bound_by_provider": vb.provider.value_counts().to_dict()}
out["a2w_all_projects_vertical_datum"] = dict(collections.Counter(norm(it.get("vertical_datum")) for it in loc.values() if it.get("kind") == "PROJECT"))
c = collections.Counter()
for _, r in vb[vb.provider == "a2w"].iterrows():
    o, l = r.station.split(":"); it = loc.get((o, l)); c[norm(it.get("vertical_datum")) if it else "no-record"] += 1
out["a2w_bound_lakes_vertical_datum"] = dict(c)
u = vb[vb.provider.str.startswith("usgs")]
out["usgs_bound_by_param"] = u.series_or_param.value_counts().to_dict()
out["interpretation"] = {"62614": "NGVD29", "62615": "NAVD88", "00062": "datum per site (unspecified in the parameter)", "00065+alt_va": "gage height + site datum (site-specific)"}
(REPO / "docs/research/depth-brain/data/datum_inventory.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
