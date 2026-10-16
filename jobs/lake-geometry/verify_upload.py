#!/usr/bin/env python3
"""Verify the published Lake Registry bucket from the outside (anonymous HTTPS, like a browser):
status, CORS (Access-Control-Allow-Origin for an allowed and a disallowed Origin), content-type / encoding / cache-control,
sha256 of the stored bytes vs registry/lakes.v1.json, and a re-read of the geometry (area vs the index and vs NID).

  python verify_upload.py [--lakes "Guntersville|AL,Wheeler|AL,..."] [--origin https://sector-bowfishing-ops.web.app]
"""
import argparse
import gzip
import hashlib
import json
import sys
import urllib.error
import urllib.request

from shapely.geometry import shape

import lake_geometry as lg

BASE = "https://storage.googleapis.com/sector-lake-registry"
PILOTS = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"]


def get(url, origin=None, accept_gzip=True):
    h = {"User-Agent": "lake-registry-verify/1.0"}
    if origin:
        h["Origin"] = origin
    if accept_gzip:
        h["Accept-Encoding"] = "gzip"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, b""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lakes", default=",".join(PILOTS))
    ap.add_argument("--origin", default="https://sector-bowfishing-ops.web.app")
    a = ap.parse_args()
    ok = True
    st, h, body = get(f"{BASE}/registry/lakes.v1.json", a.origin)
    idx = json.loads(gzip.decompress(body) if h.get("content-encoding") == "gzip" else body)
    by = {e["lakeId"]: e for e in idx["lakes"]}
    print(f"index: status {st} content-type {h.get('content-type')} encoding {h.get('content-encoding')} cache {h.get('cache-control')} "
          f"acao {h.get('access-control-allow-origin')} lakes {idx['count']} stored {len(body)} B")
    rows = []
    for lid in a.lakes.split(","):
        e = by[lid]
        g = e["geometry"]
        for v in ("display", "analysis"):
            url = g[v + "Url"]
            st, h, body = get(url, a.origin)
            sha = hashlib.sha256(body).hexdigest()
            f = json.loads(gzip.decompress(body))
            geom = shape(f["geometry"])
            center = lg.center_of(geom)
            area = lg.area_km2(geom, center)
            nid = next((p["areaKm2"] for p in e["poolExtents"] if p["kind"] == "normalPool"), None)
            usace = next((p["areaKm2"] for p in e["poolExtents"] if p["source"] == "usace-rez"), None)
            # negative CORS: an origin that is not allowed must not get Access-Control-Allow-Origin
            _s, hn, _b = get(url, "https://evil.example")
            # decompressive transcoding: a client that does not accept gzip still gets valid JSON
            _s2, h2, b2 = get(url, a.origin, accept_gzip=False)
            plain_ok = h2.get("content-encoding") is None and json.loads(b2)["type"] == "Feature"
            row = {"lake": lid, "variant": v, "status": st, "acao": h.get("access-control-allow-origin"), "acao_evil": hn.get("access-control-allow-origin"),
                   "content_type": h.get("content-type"), "encoding": h.get("content-encoding"), "cache": h.get("cache-control"),
                   "bytes": len(body), "sha_ok": sha == g["sha256"][v], "valid": geom.is_valid, "area_km2": round(area, 3),
                   "index_area_km2": g["areaKm2"] if v == "analysis" else g["areaDisplayKm2"], "nid_km2": nid, "usace_km2": usace,
                   "ratio_nid": round(area / nid, 3) if nid else None, "plain_fetch_ok": plain_ok, "confidence": e["geometryConfidence"]["level"]}
            good = (st == 200 and row["acao"] == a.origin and not row["acao_evil"] and row["content_type"] == "application/geo+json"
                    and row["encoding"] == "gzip" and "immutable" in (row["cache"] or "") and row["sha_ok"] and row["valid"] and plain_ok
                    and abs(area - row["index_area_km2"]) < 0.01 * max(1, row["index_area_km2"]))
            row["pass"] = good
            ok &= good
            rows.append(row)
            print(json.dumps(row))
    print("ALL PASS" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
