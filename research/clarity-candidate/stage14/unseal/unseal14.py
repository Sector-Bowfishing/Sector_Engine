"""Stage 14 unsealing (protocol section 6). Run ONCE, after the engine manifest and the WQP sample are frozen and hashed.
Reads/fetches Secchi, chlorophyll a and turbidity for the certification rows only. Writes truth14.json; records its
sha256 and the unsealing time in FREEZE_STAGE14.json. Prints counts only."""
import csv, json, math, collections, urllib.request, urllib.parse, time, hashlib, datetime, os, io, sys
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
U = f"{S}/stage14/unseal"; FT = 3.28084
F = json.load(open(f"{S}/stage14/FREEZE_STAGE14.json"))
assert "engine_frozen_utc" in F and "stage14/cert/wqp_sample.csv" in F["files"] and "unsealed_utc" not in F, "freeze order violated or already unsealed"
b13 = list(csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv"))); wqp = list(csv.DictReader(open(f"{S}/stage14/cert/wqp_sample.csv")))
T = {}
def itype(chl, turb):
    if chl is None or turb is None: return None
    return "mixed" if chl >= 15 and turb >= 8 else "algal" if chl >= 15 else "sediment" if turb >= 8 else "clear"
def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None
def fetch(url, path):
    if not os.path.exists(path):
        for i in range(5):
            try: urllib.request.urlretrieve(url, path); break
            except Exception: time.sleep(5 * (i + 1))
    return path
# ---------------- WQP (part B)
keys = {(r["site"], r["date"]): r["id"] for r in wqp}
sec = collections.defaultdict(list)
for r in csv.DictReader(open(f"{S}/q9/wqp/secchi.csv")):
    k = (r["site_id"], r["date"])
    if k in keys: sec[k].append(float(r["secchi_m"]))
tb = collections.defaultdict(list)
for r in csv.DictReader(open(f"{S}/q9/wqp/turbidity.csv")):
    k = (r["site_id"], r["date"])
    if k not in keys or r["unit"] not in ("NTU", "FNU", "FTU", "NTRU"): continue
    v = num(r["value"])
    if v is None or not (0 <= v < 5000): continue
    dep = num(r.get("depth_m")); tb[k].append((dep if dep is not None else 0.0, v))
def turb_of(vs):
    top = min(v[0] for v in vs); return float(np.median([v[1] for v in vs if v[0] <= top + 0.5]))
sites = sorted({r["site"] for r in wqp}); chl = collections.defaultdict(list)
chars = ["Chlorophyll a", "Chlorophyll a, corrected for pheophytin", "Chlorophyll a, uncorrected for pheophytin", "Chlorophyll a (probe)"]
for i in range(0, len(sites), 80):
    body = {"siteid": sites[i:i + 80], "characteristicName": chars, "startDateLo": "01-01-2018", "startDateHi": "12-31-2025"}
    txt = None
    for t in range(5):
        try:
            req = urllib.request.Request("https://www.waterqualitydata.us/data/Result/search?mimeType=csv&zip=no", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "Accept": "text/csv"})
            txt = urllib.request.urlopen(req, timeout=600).read().decode("utf-8", "replace"); break
        except Exception as e:
            time.sleep(10 * (t + 1))
    if txt is None: print("chl batch failed", i, flush=True); continue
    with open(f"{U}/wqp_cert_chl.csv", "a") as fh: fh.write(txt if i == 0 else txt.split("\n", 1)[1] if "\n" in txt else "")
    for r in csv.DictReader(io.StringIO(txt)):
        k = (r["MonitoringLocationIdentifier"], r["ActivityStartDate"])
        if k not in keys: continue
        u = (r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower(); v = num(r.get("ResultMeasureValue"))
        if v is None: v = 0.0 if r.get("ResultDetectionConditionText") else None
        if v is None: continue
        if u in ("ug/l", "mg/m3", "ppb", "µg/l"): pass
        elif u == "mg/l": v *= 1000
        else: continue
        if 0 <= v < 5000: chl[k].append(v)
for k, rid in keys.items():
    vs = sec.get(k, []); m = float(np.median(vs)) if vs else None
    c = float(np.median(chl[k])) if chl.get(k) else None; t = turb_of(tb[k]) if tb.get(k) else None
    T[rid] = {"secchi_ft": m * FT if m is not None and 0.05 <= m <= 25 else None, "drop": None if (m is not None and 0.05 <= m <= 25) else "no reading / out of 0.05-25 m",
              "chl": c, "turb": t, "insitu_type": itype(c, t), "n_readings": len(vs)}
print("WQP", len(keys), "with Secchi", sum(1 for r in wqp if T[r["id"]]["secchi_ft"]), "with chl", sum(1 for r in wqp if T[r["id"]]["chl"] is not None),
      "with turb", sum(1 for r in wqp if T[r["id"]]["turb"] is not None), flush=True)
# ---------------- NLA
NL = {"22s": "https://www.epa.gov/system/files/other-files/2024-08/nla22_secchi.csv", "22c": "https://www.epa.gov/system/files/other-files/2024-08/nla22_waterchem_wide.csv",
      "17s": "https://www.epa.gov/sites/default/files/2021-04/nla_2017_secchi-data.csv", "17c": "https://www.epa.gov/sites/default/files/2021-04/nla_2017_water_chemistry_chla-data.csv"}
P = {k: fetch(u, f"{U}/{os.path.basename(u)}") for k, u in NL.items()}
def rows(p): return list(csv.DictReader(open(p, encoding="utf-8-sig", errors="replace")))
sec22 = {(r["SITE_ID"], str(r.get("VISIT_NO", "1"))): r for r in rows(P["22s"])}
sec17 = {(r["SITE_ID"], str(r.get("VISIT_NO", "1"))): r for r in rows(P["17s"])}
ch22 = {(r["SITE_ID"], str(r.get("VISIT_NO", "1"))): r for r in rows(P["22c"])}
ch17 = collections.defaultdict(dict)
for r in rows(P["17c"]):
    a = (r.get("ANALYTE") or "").upper()
    if a in ("CHLA", "TURB"): ch17[(r["SITE_ID"], str(r.get("VISIT_NO", "1")))][a] = num(r.get("RESULT"))
for r in b13:
    if not r["src"].startswith("NLA"): continue
    src, site, visit = r["id"].split(":")
    s = (sec22 if src == "NLA22" else sec17).get((site, visit)); m = None; why = None
    if not s: why = "no Secchi record"
    elif (s.get("CLEAR_TO_BOTTOM") or "").upper() in ("Y", "YES"): why = "clear to bottom"
    else:
        d, a = num(s.get("DISAPPEARS")), num(s.get("REAPPEARS"))
        m = (d + a) / 2 if d is not None and a is not None else d if d is not None else a
        if m is None or not (0.05 <= m <= 25): why, m = "no usable reading", None
    if src == "NLA22":
        c = ch22.get((site, visit), {}); cv, tv = num(c.get("CHLA_RESULT")), num(c.get("TURB_RESULT"))
    else:
        c = ch17.get((site, visit), {}); cv, tv = c.get("CHLA"), c.get("TURB")
    T[r["id"]] = {"secchi_ft": m * FT if m is not None else None, "drop": why, "chl": cv, "turb": tv, "insitu_type": itype(cv, tv)}
print("NLA", sum(1 for r in b13 if r["src"].startswith("NLA")), "with Secchi", sum(1 for r in b13 if r["src"].startswith("NLA") and T[r["id"]]["secchi_ft"]), flush=True)
# ---------------- SYKE
B = "https://rajapinnat.ymparisto.fi/api/vesla/2.0/odata"
def get(entity, params):
    url = f"{B}/{entity}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for i in range(8):
        try:
            with urllib.request.urlopen(url, timeout=120) as r: return json.load(r)["value"]
        except Exception: time.sleep(5 * (i + 1))
    return None
import concurrent.futures as cf
def syke(r):
    sid = r["id"].split(":")[1]
    h = get("YmpHavainto", {"$filter": f"Naytteenotto_Id eq {sid} and YmpSuure_Id eq 4", "$select": "Arvo"})
    w = get("Result_Wide", {"$filter": f"Sampling_id eq {sid}", "$select": "AnalyteCode,Value,Unit,SampleDepth_m,SampleDepthUpper_m,Flag"})
    vals = [num(x.get("Arvo")) for x in (h or []) if num(x.get("Arvo")) is not None]
    m = float(np.median(vals)) if vals else None
    def pick(code):
        xs = [(num(x.get("SampleDepth_m")) if num(x.get("SampleDepth_m")) is not None else (num(x.get("SampleDepthUpper_m")) or 0.0), num(x.get("Value")))
              for x in (w or []) if x.get("AnalyteCode") == code and num(x.get("Value")) is not None]
        if not xs: return None
        top = min(d for d, v in xs); sel = [v for d, v in xs if d <= top + 0.5 and d <= 2.0]
        return float(np.median(sel)) if sel else None
    cv, tv = pick("CP"), pick("TURB")
    return r["id"], {"secchi_ft": m * FT if m is not None and 0.05 <= m <= 25 else None, "drop": None if (m is not None and 0.05 <= m <= 25) else "no reading",
                     "chl": cv, "turb": tv, "insitu_type": itype(cv, tv)}
with cf.ThreadPoolExecutor(8) as ex:
    for k, v in ex.map(syke, [r for r in b13 if r["src"] == "SYKE"]): T[k] = v
print("SYKE", sum(1 for r in b13 if r["src"] == "SYKE"), "with Secchi", sum(1 for r in b13 if r["src"] == "SYKE" and T[r["id"]]["secchi_ft"]), flush=True)
json.dump(T, open(f"{U}/truth14.json", "w"))
F = json.load(open(f"{S}/stage14/FREEZE_STAGE14.json"))
F["unsealed_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
F["files"]["stage14/unseal/truth14.json"] = hashlib.sha256(open(f"{U}/truth14.json", "rb").read()).hexdigest()
F["files"]["stage14/unseal/unseal14.py"] = hashlib.sha256(open(f"{U}/unseal14.py", "rb").read()).hexdigest()
json.dump(F, open(f"{S}/stage14/FREEZE_STAGE14.json", "w"), indent=1); print("unsealed", F["unsealed_utc"])
