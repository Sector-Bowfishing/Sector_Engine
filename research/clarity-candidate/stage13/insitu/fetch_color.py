"""Stage 13 section 1: same-site colour / CDOM / DOC results from WQP for the corpus stations only (development data;
2018-2025). Characteristics: True color, Color, Apparent color, Absorbance at 440 nm, Organic carbon. Writes color_raw.csv."""
import csv, io, json, sys, time, urllib.request, urllib.parse, concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
sites = sorted({x["site"] for x in rows if x.get("site")})
CH = ["True color", "Color", "Apparent color", "Absorbance at 440 nm", "Organic carbon"]
KEEP = ["MonitoringLocationIdentifier", "ActivityStartDate", "CharacteristicName", "ResultSampleFractionText", "ResultMeasureValue",
        "ResultMeasure/MeasureUnitCode", "ActivityDepthHeightMeasure/MeasureValue", "ActivityDepthHeightMeasure/MeasureUnitCode", "ResultDetectionConditionText"]
def q(batch):
    p = [("siteid", s) for s in batch] + [("characteristicName", c) for c in CH] + [("startDateLo", "01-01-2018"), ("startDateHi", "12-31-2025"),
         ("mimeType", "csv"), ("zip", "no"), ("dataProfile", "narrowResult")]
    url = "https://www.waterqualitydata.us/data/Result/search?" + urllib.parse.urlencode(p)
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=600) as r:
                txt = r.read().decode("utf-8", "replace")
            return [{k: d.get(k, "") for k in KEEP} for d in csv.DictReader(io.StringIO(txt))]
        except Exception as e:
            time.sleep(10 * (i + 1)); err = e
    print("FAILED batch", batch[0], err, flush=True); return []
out = []
with cf.ThreadPoolExecutor(4) as ex:
    for n, v in enumerate(ex.map(q, [sites[i:i + 50] for i in range(0, len(sites), 50)]), 1):
        out += v; print(n, len(out), flush=True)
with open("color_raw.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=KEEP); w.writeheader(); w.writerows(out)
print("sites", len(sites), "results", len(out))
