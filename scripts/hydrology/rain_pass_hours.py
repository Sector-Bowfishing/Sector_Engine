"""Hourly MRMS Pass 2 basin rain for the day before each pass (Clarity
Fusion Stage 3A, item 4).

The Stage 2 replay read rain as 24 h totals valid 17Z, so a pass at ~16:30Z
could see nothing after 17Z the day before. For every pass day D this reads
the 01H Pass 2 products valid 18Z D-1 ... 16Z D (rain 17Z D-1 -> 16Z D), per
arm drainage and over the lake surface, so a replay as of the pass knows the
rain up to 16Z (30 min before the scene) without reading after it.

usage: geo/bin/python rain_pass_hours.py <weights.json> <lake geojson> <passes.json> <out.json> [--threads 8]
"""
import os, sys, json, tempfile, argparse, datetime as dt, concurrent.futures as cf
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catchment_rain as C
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

ap = argparse.ArgumentParser()
ap.add_argument("weights"); ap.add_argument("lake"); ap.add_argument("passes"); ap.add_argument("out")
ap.add_argument("--threads", type=int, default=8)
a = ap.parse_args()
W = json.load(open(a.weights))
arms = {k: v for k, v in W["arms"].items() if v["cells"]}
if "_lakeSurface" not in arms:
    lake = unary_union([shape(f["geometry"]) for f in json.load(open(a.lake))["features"]])
    arms["_lakeSurface"] = {"basis": "lakeSurface", "cells": C.cell_weights(mapping(lake))}
days = sorted({p["date"] for p in json.load(open(a.passes))})
res = json.load(open(a.out)) if os.path.exists(a.out) else {
    "source": "MRMS MultiSensor_QPE_01H_Pass2; key = hour the product is valid (rain in the hour before)", "hours": {}}
hours = []
for d in days:
    D = dt.datetime.fromisoformat(d)
    for h in range(18, 24):
        hours.append(D - dt.timedelta(days=1) + dt.timedelta(hours=h))
    for h in range(0, 17):
        hours.append(D + dt.timedelta(hours=h))
hours = [t for t in sorted(set(hours)) if f"{t:%Y-%m-%dT%H}" not in res["hours"]]
tmp = tempfile.mkdtemp()


def one(t):
    p = C.fetch(C.PRODUCTS[1], t, tmp)
    if p is None:
        return t, None
    try:
        return t, {k: (None if v is None else round(v, 4)) for k, v in C.basin_means(p, arms).items()}
    except Exception:
        return t, None
    finally:
        os.remove(p)


print(len(hours), "hours to read", flush=True)
with cf.ThreadPoolExecutor(a.threads) as ex:
    for n, (t, v) in enumerate(ex.map(one, hours), 1):
        res["hours"][f"{t:%Y-%m-%dT%H}"] = v
        if n % 200 == 0:
            json.dump(res, open(a.out, "w")); print(n, flush=True)
json.dump(res, open(a.out, "w"))
print("done", len(res["hours"]), "hours;", sum(v is None for v in res["hours"].values()), "missing")
