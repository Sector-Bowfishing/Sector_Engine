"""Level-1 check (provider truth): is the level Lake Brain published for each Depth pilot what the OPERATOR's own feed says right now?
One-off audit, GET-only; the product never does this (Depth consumes Lake). Output: docs/brains/depth/data/pilot_input_verification.json"""
import json, subprocess, urllib.request, datetime as dt
H = {"Accept": "application/json;version=2"}
def get(u, h=None, t=40):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=h or {"User-Agent": "sector-depth-audit"}), timeout=t).read())
T = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()
def rtdb(p): return get(f"https://sector-brain.firebaseio.com/{p}.json?access_token={T}")
out = {"checkedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "lakes": {}}
TVA = {"Guntersville_AL": "GVDA1", "Wheeler_AL": "WHLA1", "Wilson_AL": "WLSA1", "Pickwick_Lake_TN": "PICT1"}      # location codes from LakeSourceBindings.swift
for k, loc in TVA.items():
    ls, ds = rtdb(f"lakes/{k}/states/lake"), rtdb(f"lakes/{k}/states/depth")
    try:
        rows = get(f"https://www.tva.com/RestApi/observed-data-48-hours/{loc}", {"Accept": "application/json", "User-Agent": "sector-depth-audit"})
        vals = [(r.get("Day"), r.get("Time"), float(r["ReservoirElevation"])) for r in rows if r.get("ReservoirElevation") not in (None, "")]
        match = [v for v in vals if abs(v[2] - ls["currentElevationFt"]) < 0.005]
        prov = {"source": f"TVA RestApi observed-data-48-hours/{loc}", "rowsLast48h": len(vals), "latest": {"day": vals[-1][0], "time": vals[-1][1], "elevationFt": vals[-1][2]},
                "lakeValuePresentInProviderFeed": bool(match), "matchedRow": ({"day": match[-1][0], "time": match[-1][1], "elevationFt": match[-1][2]} if match else None)}
        prov["elevationFt"] = match[-1][2] if match else vals[-1][2]
    except Exception as e:
        prov = {"source": f"TVA RestApi observed-data-48-hours/{loc}", "error": repr(e)[:120]}
    out["lakes"][k] = {"lake": {"elevationFt": ls["currentElevationFt"], "observationTime": ls["observationTime"], "unit": ls["unit"], "datum": ls.get("datum")}, "provider": prov,
                       "depth": {"shiftFt": ds["effectiveDepth"]["shiftFt"], "levelDeltaFromReferenceFt": ds["level"]["levelDeltaFromReferenceFt"], "referencePoolFt": ds["reference"]["referencePoolFt"]}}
ls, ds = rtdb("lakes/Lake_Hartwell_SC/states/lake"), rtdb("lakes/Lake_Hartwell_SC/states/depth")
try:
    d = get("https://waterservices.usgs.gov/nwis/iv/?format=json&sites=02187010&parameterCd=00062&period=PT48H")
    pts = d["value"]["timeSeries"][0]["values"][0]["value"]
    t0 = dt.datetime.fromisoformat(ls["observationTime"].replace("Z", "+00:00"))
    near = min(pts, key=lambda p: abs(dt.datetime.fromisoformat(p["dateTime"]).astimezone(dt.timezone.utc) - t0))
    prov = {"source": "USGS 02187010 parameter 00062 (instantaneous), nearest to the Lake observation time", "elevationFt": float(near["value"]), "at": near["dateTime"], "lakeObservationTime": ls["observationTime"]}
except Exception as e:
    prov = {"source": "USGS 02187010 00062", "error": repr(e)[:120]}
out["lakes"]["Lake_Hartwell_SC"] = {"lake": {"elevationFt": ls["currentElevationFt"], "observationTime": ls["observationTime"], "unit": ls["unit"], "datum": ls.get("datum")}, "provider": prov,
                                     "depth": {"shiftFt": ds["effectiveDepth"]["shiftFt"], "levelDeltaFromReferenceFt": ds["level"]["levelDeltaFromReferenceFt"], "referencePoolFt": ds["reference"]["referencePoolFt"]}}
for k, v in out["lakes"].items():
    if "elevationFt" in v["provider"]:
        v["diffLakeMinusProviderFt"] = round(v["lake"]["elevationFt"] - v["provider"]["elevationFt"], 3)
    v["depthShiftEqualsLevelMinusPoolFt"] = round(v["lake"]["elevationFt"] - v["depth"]["referencePoolFt"], 2)
    v["shiftArithmeticOk"] = abs(v["depth"]["levelDeltaFromReferenceFt"] - (v["lake"]["elevationFt"] - v["depth"]["referencePoolFt"])) < 0.006
json.dump(out, open("docs/brains/depth/data/pilot_input_verification.json", "w"), indent=1)
for k, v in out["lakes"].items(): print(k, "lake", v["lake"]["elevationFt"], "| provider", v["provider"].get("elevationFt", v["provider"].get("error")), "| diff", v.get("diffLakeMinusProviderFt"), "| shift", v["depth"]["shiftFt"], "| arithmetic", v["shiftArithmeticOk"])
