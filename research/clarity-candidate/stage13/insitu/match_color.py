"""Stage 13 section 1: same-day colour / DOC per corpus row. true colour = 'True color' in PCU/CU; DOC = 'Organic carbon'
dissolved/filtered mg/L; TOC = total/unfiltered mg/L (lakes: mostly dissolved; used where DOC is absent, flagged).
Depth <= 2 m or blank; below-detection results dropped; median of duplicates. Writes color_matched.json."""
import csv, json, collections, statistics
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
vals = collections.defaultdict(lambda: collections.defaultdict(list))
for r in csv.DictReader(open("color_raw.csv")):
    try: v = float(r["ResultMeasureValue"])
    except ValueError: continue
    if r["ResultDetectionConditionText"]: continue
    d = r["ActivityDepthHeightMeasure/MeasureValue"]; du = r["ActivityDepthHeightMeasure/MeasureUnitCode"].lower()
    if d:
        try: dm = float(d) * (0.3048 if du in ("ft", "feet") else 1.0)
        except ValueError: dm = 0
        if dm > 2: continue
    c, u, fr = r["CharacteristicName"], r["ResultMeasure/MeasureUnitCode"].upper(), r["ResultSampleFractionText"].lower()
    k = None
    if c == "True color" and u in ("PCU", "CU"): k = "true_color"
    elif c == "Apparent color" and u in ("PCU", "CU"): k = "apparent_color"
    elif c == "Organic carbon" and u == "MG/L": k = "doc" if ("dissolved" in fr or "filtered" in fr) else "toc"
    if k and v >= 0: vals[(r["MonitoringLocationIdentifier"], r["ActivityStartDate"])][k].append(v)
rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if x["date"] <= "2025-12-31"]
out = {}
for x in rows:
    v = vals.get((x.get("site"), x["date"]))
    if v: out[x["id"]] = {k: statistics.median(a) for k, a in v.items()}
json.dump(out, open("color_matched.json", "w"), indent=1)
print("rows with any", len(out), {k: sum(1 for v in out.values() if k in v) for k in ("true_color", "apparent_color", "doc", "toc")})
