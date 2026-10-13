"""Lake -> dam linkage via the National Inventory of Dams (NID). Output: binding/nid_links.csv + summary."""
import csv, json, math, re, collections
from shapely.geometry import Point, box
from shapely.ops import transform
from shapely.strtree import STRtree
from common import *
from match import load_polys, proj, lake_name_alts, to_planar

DAM_WORDS = re.compile(r"\b(dam|lake|reservoir|res|pond|pool|lock|and|no|number|n|upper|lower)\b", re.I)


def nid_sim(l, d):
    names = [d.get("NAME") or ""] + [x for x in re.split(r"[;|]", d.get("OTHER_NAMES") or "") if x] + [x for x in re.split(r"[;|]", d.get("FORMER_NAMES") or "") if x]
    return max(name_sim(a, n) for a in lake_name_alts(l) for n in names) if names else 0.0


def run():
    lakes = load_directory(); polys = load_polys()
    dams = [json.loads(x) for x in open(f"{RAW}/nid/nid.jsonl")]
    dams = [d for d in dams if d.get("LATITUDE") and d.get("LONGITUDE")]
    tree = STRtree([Point(d["LONGITUDE"], d["LATITUDE"]) for d in dams])
    rows = []
    for l in lakes:
        if not l["hasDam"]:
            continue
        poly = polys.get(l["id"]); pj = proj(l["lat"])
        if poly is not None:
            minx, miny, maxx, maxy = poly.bounds; pad = 0.06
            idx = tree.query(box(minx - pad, miny - pad, maxx + pad, maxy + pad)); pp = to_planar(poly, l['lat'])
        else:
            idx = tree.query(box(l["lon"] - .1, l["lat"] - .1, l["lon"] + .1, l["lat"] + .1)); pp = Point(*pj(l["lon"], l["lat"]))
        c = []
        states = set(l.get("states") or [l["state"]])
        for i in idx:
            d = dams[i]
            dist = pp.distance(Point(*pj(d["LONGITUDE"], d["LATITUDE"])))
            if dist > (4000 if poly is not None else 8000):
                continue
            sim = nid_sim(l, d)
            if d["NIDID"][:2] not in states and not (dist < 3000 and sim >= 0.6):
                continue
            s = (40 if dist < 300 else 30 if dist < 1000 else 18 if dist < 2500 else 8) + 35 * min(1, sim * 1.3)
            h = d.get("DAM_HEIGHT") or 0
            stor = d.get("NID_STORAGE") or 0
            s += min(15, math.log10(stor + 1) * 2.5) + (5 if h >= 25 else 0)
            if d.get("IS_ASSOCIATED_STRUCTURE") == "Yes":
                s -= 15
            op = (l["operatorName"] or "").lower(); own = " ".join(str(d.get(k) or "") for k in ("FED_AGENCY_OWNERS", "FED_AGENCY_OPERATIONS", "STATE_FED_AGENCY", "OWNER_TYPES")).lower()
            if ("usace" in op and ("usace" in own or "corps" in own or "army" in own)) or ("usbr" in op and ("bureau" in own or "usbr" in own)) or ("tva" in op and ("tennessee valley" in own or "tva" in own)):
                s += 5
            c.append((round(s, 1), round(dist), sim, d))
        c.sort(key=lambda x: -x[0])
        top = c[0] if c else None
        rows.append(dict(lakeId=l["id"], lakeName=l["name"], state=l["state"], operator=l["operatorName"], nCand=len(c),
                         nidId=top[3]["NIDID"] if top else "", nidName=top[3]["NAME"] if top else "", nidScore=top[0] if top else 0, nidDistM=top[1] if top else "",
                         nidSim=round(top[2], 2) if top else "", river=top[3]["RIVER_OR_STREAM"] if top else "", owner=(top[3]["PRIMARY_OWNER_TYPE"] if top else ""),
                         fedOp=(top[3].get("FED_AGENCY_OPERATIONS") or top[3].get("FED_AGENCY_OWNERS")) if top else "", purposes=(top[3]["PURPOSES"] if top else ""),
                         height=top[3]["DAM_HEIGHT"] if top else "", storage=top[3]["NID_STORAGE"] if top else "",
                         second=c[1][0] if len(c) > 1 else 0, secondName=c[1][3]["NAME"] if len(c) > 1 else ""))
    return rows


if __name__ == "__main__":
    rows = run()
    with open(f"{BIND}/nid_links.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    n = len(rows)
    strong = [r for r in rows if r["nidScore"] >= 70 and r["nidSim"] and r["nidSim"] >= 0.4]
    unamb = [r for r in strong if r["nidScore"] - r["second"] >= 10]
    print("hasDam lakes", n, "any candidate", sum(1 for r in rows if r["nCand"]), "strong(score>=70&sim>=.4)", len(strong), "unambiguous(margin>=10)", len(unamb))
