#!/usr/bin/env python3
"""Rebuild vegetation_brain/data/agency_sfwmd_okeechobee.json from the open SFWMD ArcGIS layer (two small group-by requests). Read-only.
Area comes from the 1-ha cell COUNT; the layer's Shape__Area is web-mercator inflated, so it is used only as a cross-check at the lake's latitude."""
import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from vegetation_brain import agency as A  # noqa: E402

LAYER = A.SOURCE_SFWMD_OKEE["layer"]
LAT = 26.95        # Lake Okeechobee marsh, for the mercator cross-check


def q(stats):
    url = LAYER + "/query?" + urllib.parse.urlencode({"where": "1=1", "groupByFieldsForStatistics": "VEGLABEL1_CODE,VEGLABEL1_DESC",
                                                      "outStatistics": json.dumps(stats), "f": "json"})
    return json.load(urllib.request.urlopen(url, timeout=90))["features"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "vegetation_brain", "data", "agency_sfwmd_okeechobee.json"))
    a = ap.parse_args()
    n = q([{"statisticType": "count", "onStatisticField": "OBJECTID", "outStatisticFieldName": "n"}])
    ar = q([{"statisticType": "sum", "onStatisticField": "Shape__Area", "outStatisticFieldName": "a"}])
    counts = [{"code": f["attributes"]["VEGLABEL1_CODE"], "desc": f["attributes"]["VEGLABEL1_DESC"] or "", "n": f["attributes"]["n"]} for f in n if f["attributes"]["VEGLABEL1_CODE"]]
    merc = {f["attributes"]["VEGLABEL1_CODE"]: (f["attributes"]["a"] or 0) / 1e6 * math.cos(math.radians(LAT)) ** 2 for f in ar}
    rec = A.build_sfwmd_record("Okeechobee|FL", counts, datetime.now(timezone.utc).date().isoformat(), merc)
    cell_total = sum(c["n"] for c in counts) * 0.01
    geom_total = sum(merc.values())
    rec["mercatorAreaCheck"] = {"cellCountKm2": round(cell_total, 1), "geometryKm2AtLatitude": round(geom_total, 1), "ratio": round(geom_total / cell_total, 3)}
    bad = A.validate_sfwmd(rec)
    json.dump({"schema": "sector-vegetation-agency-v1", "source": A.SOURCE_SFWMD_OKEE["id"], "problems": bad, "records": {"Okeechobee|FL": rec}},
              open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps({"problems": bad, "mappedKm2": rec["mappedKm2"], "check": rec["mercatorAreaCheck"], "top": [(c["label"], c["areaKm2"]) for c in rec["classes"][:4]]}))


if __name__ == "__main__":
    main()
