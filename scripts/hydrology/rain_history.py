"""Daily basin-mean rain per arm, from NOAA MRMS Pass 2, for a date range
(Clarity Fusion Stage 2, the pass-pair calibration and replay input).

Each day D: the MultiSensor QPE 24H Pass 2 product valid at 17Z on D (rain
from 17Z D-1 to 17Z D -- aligned with the ~16:30Z Sentinel-2 passes), as
basin means over each arm's drainage (guntersville.mrms_weights.json), plus
the lake's own surface (the main stem has no cove catchments). Files are
deleted once read.

usage: geo/bin/python rain_history.py <weights.json> <lake geojson> <start YYYY-MM-DD> <end> <out.json>
"""
import os, sys, json, gzip, tempfile, datetime as dt, urllib.request, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catchment_rain as C

weights, lake_path, start, end, out = sys.argv[1:6]
W = json.load(open(weights))
arms = {k: v for k, v in W["arms"].items() if v["cells"]}
# the lake surface as one more "catchment"
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
lake = unary_union([shape(f["geometry"]) for f in json.load(open(lake_path))["features"]])
arms["_lakeSurface"] = {"basis": "lakeSurface", "cells": C.cell_weights(mapping(lake))}
res = json.load(open(out)) if os.path.exists(out) else {"source": "MRMS MultiSensor_QPE_24H_Pass2 valid 17Z", "days": {}}
d = dt.date.fromisoformat(start); e = dt.date.fromisoformat(end)
tmpdir = tempfile.mkdtemp()
while d <= e:
    k = d.isoformat()
    if k not in res["days"]:
        t = dt.datetime(d.year, d.month, d.day, 17)
        p = C.fetch(C.PRODUCTS[24], t, tmpdir)
        if p is None:
            res["days"][k] = None
        else:
            try:
                m = C.basin_means(p, arms)
                res["days"][k] = {a: (None if v is None else round(v, 3)) for a, v in m.items()}
            except Exception as ex:
                res["days"][k] = None
            os.remove(p)
        if len(res["days"]) % 20 == 0:
            json.dump(res, open(out, "w")); print(k, flush=True)
    d += dt.timedelta(days=1)
json.dump(res, open(out, "w"))
print("done", len(res["days"]), "days")
