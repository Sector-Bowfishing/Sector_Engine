#!/usr/bin/env python3
"""Rebuild vegetation_brain/data/agency_fwc_pacpvi.json from the open FWC layer (one request, ~60 KB). Read-only.
   python tools/build_agency_fwc.py [--out PATH]"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "runtime"))                # brains/vegetation/runtime (vegetation_brain)
sys.path.insert(0, os.path.join(HERE, ".."))                                          # research/tools (vegetation_research)
from vegetation_brain import agency as A  # noqa: E402

URL = A.SOURCE_FWC["layer"] + "/query?where=1%3D1&outFields=*&returnGeometry=false&resultRecordCount=2000&f=json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "..", "..", "runtime", "knowledge", "agency_fwc_pacpvi.json"))
    a = ap.parse_args()
    rows = [f["attributes"] for f in json.load(urllib.request.urlopen(URL, timeout=90))["features"]]
    by = {}
    for r in rows:
        by.setdefault((r.get("LakeName") or "").strip(), []).append(r)
    today = datetime.now(timezone.utc).date().isoformat()
    recs = {lid: A.build_record(lid, by.get(name, []), today) for lid, name in A.FWC_NAME_MAP.items()}
    missing = [lid for lid, r in recs.items() if not r["rows"]]
    json.dump({"schema": "sector-vegetation-agency-v1", "source": A.SOURCE_FWC["id"], "retrievedOn": today, "totalLayerRows": len(rows),
               "records": recs, "missing": missing}, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps({"records": len(recs) - len(missing), "missing": missing, "layerRows": len(rows)}))


if __name__ == "__main__":
    main()
