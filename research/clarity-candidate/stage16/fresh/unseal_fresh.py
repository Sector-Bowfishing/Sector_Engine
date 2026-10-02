"""Stage 16 unsealing (protocol section 4). Run ONCE, after rule16 and the fresh sample are frozen and hashed. Reads the
fresh Secchi and turbidity for the sample rows only; fetches same-day chlorophyll a for the sample sites (Stage 11
characteristics and unit rules). Writes truth16.json; records its sha256 and the unsealing time. Prints counts only."""
import csv, json, collections, urllib.request, time, hashlib, datetime, io
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage16/fresh"; W = f"{D}/wqp"; FT = 3.28084
F = json.load(open(f"{S}/stage16/FREEZE_STAGE16.json"))
assert "rule_frozen_utc" in F and "stage16/fresh/fresh_sample.csv" in F["files"] and "unsealed_utc" not in F, "freeze order violated or already unsealed"
smp = list(csv.DictReader(open(f"{D}/fresh_sample.csv"))); keys = {(r["site"], r["date"]): r["id"] for r in smp}
num = lambda v: (float(v) if v not in (None, "") else None) if not isinstance(v, float) else v
sec = collections.defaultdict(list)
for r in csv.DictReader(open(f"{W}/secchi.csv")):
    k = (r["site_id"], r["date"])
    if k in keys: sec[k].append(float(r["secchi_m"]))
tb = collections.defaultdict(list)
for r in csv.DictReader(open(f"{W}/turbidity.csv")):
    k = (r["site_id"], r["date"])
    if k not in keys or r["unit"] not in ("NTU", "FNU", "FTU", "NTRU"): continue
    try: v = float(r["value"])
    except ValueError: continue
    if 0 <= v < 5000:
        dep = num(r.get("depth_m")); tb[k].append((dep if dep is not None else 0.0, v))
chl = collections.defaultdict(list); sites = sorted({r["site"] for r in smp})
chars = ["Chlorophyll a", "Chlorophyll a, corrected for pheophytin", "Chlorophyll a, uncorrected for pheophytin", "Chlorophyll a (probe)"]
for i in range(0, len(sites), 60):
    body = {"siteid": sites[i:i + 60], "characteristicName": chars, "startDateLo": "01-01-2026", "startDateHi": "09-30-2026"}; txt = None
    for t in range(6):
        try:
            req = urllib.request.Request("https://www.waterqualitydata.us/data/Result/search?mimeType=csv&zip=no", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "Accept": "text/csv"})
            txt = urllib.request.urlopen(req, timeout=600).read().decode("utf-8", "replace"); break
        except Exception: time.sleep(30 * (t + 1))
    time.sleep(5)
    if txt is None: print("chl batch failed", i, flush=True); continue
    for r in csv.DictReader(io.StringIO(txt)):
        k = (r["MonitoringLocationIdentifier"], r["ActivityStartDate"])
        if k not in keys: continue
        u = (r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower()
        try: v = float(r.get("ResultMeasureValue"))
        except (TypeError, ValueError): v = 0.0 if r.get("ResultDetectionConditionText") else None
        if v is None: continue
        if u in ("ug/l", "mg/m3", "ppb", "µg/l"): pass
        elif u == "mg/l": v *= 1000
        else: continue
        if 0 <= v < 5000: chl[k].append(v)
def itype(c, t):
    if c is None or t is None: return None
    return "mixed" if c >= 15 and t >= 8 else "algal" if c >= 15 else "sediment" if t >= 8 else "clear"
T = {}
for k, rid in keys.items():
    vs = sec.get(k, []); m = float(np.median(vs)) if vs else None
    c = float(np.median(chl[k])) if chl.get(k) else None
    t = None
    if tb.get(k):
        top = min(v[0] for v in tb[k]); t = float(np.median([v[1] for v in tb[k] if v[0] <= top + 0.5]))
    T[rid] = {"secchi_ft": m * FT if m is not None and 0.05 <= m <= 25 else None, "chl": c, "turb": t, "insitu_type": itype(c, t)}
json.dump(T, open(f"{D}/truth16.json", "w"))
print("fresh rows", len(keys), "with Secchi", sum(1 for v in T.values() if v["secchi_ft"]), "with chl", sum(1 for v in T.values() if v["chl"] is not None),
      "with turb", sum(1 for v in T.values() if v["turb"] is not None))
F = json.load(open(f"{S}/stage16/FREEZE_STAGE16.json"))
F["unsealed_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for p in ("stage16/fresh/truth16.json", "stage16/fresh/unseal_fresh.py"): F["files"][p] = hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest()
json.dump(F, open(f"{S}/stage16/FREEZE_STAGE16.json", "w"), indent=1); print("unsealed", F["unsealed_utc"])
