"""Current Clarity candidate SHADOW job — UNCERTIFIED, never shown publicly, never replaces production.

For every new Sentinel-2 pass over a pilot lake (pilot_lakes.json) it records, per fixed point, side by side:
  production   what production shows: the published Water Clarity layer at that point for that pass
               (gs://sector-lake-surface, secchi-power-v1 feet), and the same model on the production-gated Sen2Cor
               disk at the point (stage6/extract.py, the frozen read-out)
  stage16      the frozen Stage 16 candidate (research/clarity-candidate: frozen ACOLITE path K4 -> C-gbm -> posterior
               gate, tier-2 boundary-only, S2C lower authority, algal modifier)
  stage17      the frozen Stage 17 challenger (+-10 d inverse-uncertainty consensus) when neighbouring scenes exist
plus scene ids, platform, tier, authority, evidence, uncertainty, the algal flag and the rule/model hashes.

Before writing anything, every task checks itself against the frozen outputs: research file hashes, engine14/16 on the
stored certification and fresh rows, the challenger port on the frozen dev17 outputs, and ACOLITE golden scenes (task 0
all six, other tasks one). Any difference stops the task; nothing is written but the failure record.

Writes only to the PRIVATE bucket gs://$BUCKET/shadow/v1/. Reads no field report, ever.
  python shadow.py [--lakes a,b] [--lookback DAYS] [--local DIR] [--max-items N] [--skip-golden]"""
import argparse, base64, datetime as dt, hashlib, json, math, os, platform, socket, subprocess, sys, time, traceback, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("CLARITY_RESEARCH_ROOT") or os.path.normpath(os.path.join(HERE, "../../research/clarity-candidate"))
os.environ["CLARITY_RESEARCH_ROOT"] = ROOT
for p in ("stage14/engine", "stage16/engine", "stage14/analysis", "stage16/analysis", "stage11/tools", "stage14/cert", "stage6", "golden"):
    sys.path.insert(0, os.path.join(ROOT, p))
sys.path.insert(0, HERE)

import numpy as np                       # noqa: E402
import engine14 as E14                   # noqa: E402  frozen
import engine16 as E16                   # noqa: E402  frozen
from lib14 import valid                  # noqa: E402
import safe as SAFE                      # noqa: E402
_fetch = SAFE.fetch
SAFE.fetch = lambda name, skip=("HTML/", "rep_info/", "preview", "_TCI.jp2"): _fetch(name, skip)   # addendum A1, as run_cert_aco_a1.py
import run_cert_aco as RCA               # noqa: E402  frozen driver: RCA.one(task, resdir)
import extract as E6                     # noqa: E402  frozen Sen2Cor read-out (stage6)
import golden_test as GT                 # noqa: E402
import challenger17 as C17               # noqa: E402
import s2c22 as C22                      # noqa: E402  Stage 22: nominal-S2C path (Stage 12 retired -> C3)

CANDIDATE = "clarity-candidate-v1"
LABEL = "Uncertified candidate (shadow). Not a certified clarity reading."
BUCKET = os.environ.get("BUCKET", "sector-clarity-candidate")
PREFIX = "shadow/v1"
LAYER = "https://storage.googleapis.com/sector-lake-surface/lakes/{slug}/clarity/{date}.grid.json"
PROD_A, PROD_B, PROD_RANGE = 11.123, -0.637, (-0.356, 0.520)   # secchi-power-v1 (VisibilityModel.swift, satelliteObserved)
TASK = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0")); NTASKS = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
EXECUTION = os.environ.get("CLOUD_RUN_EXECUTION") or "local-" + time.strftime("%Y%m%dT%H%M%S")


# ------------------------------------------------------------------ storage (GCS JSON API; no new packages in the frozen env)
class Store:
    def __init__(self, bucket, local=None):
        self.bucket, self.local, self._tok = bucket, local, (None, 0)

    def token(self):
        if self._tok[1] > time.time() + 60: return self._tok[0]
        try:
            req = urllib.request.Request("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", headers={"Metadata-Flavor": "Google"})
            d = json.load(urllib.request.urlopen(req, timeout=10)); self._tok = (d["access_token"], time.time() + d["expires_in"])
        except Exception:   # off Cloud Run: gcloud hands back a cached token of unknown remaining life, so keep it briefly
            t = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip(); self._tok = (t, time.time() + 240)
        return self._tok[0]

    def _req(self, method, url, data=None, ctype=None):
        h = {"Authorization": f"Bearer {self.token()}"}
        if ctype: h["Content-Type"] = ctype
        for i in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h), timeout=60) as r: return r.read()
            except urllib.error.HTTPError as e:
                if e.code == 404: return None
                if e.code == 401 and i == 0:            # an expired token: fetch a new one and retry once
                    self._tok = (None, 0); h["Authorization"] = f"Bearer {self.token()}"; continue
                if e.code < 500 and e.code != 429: raise
            except (urllib.error.URLError, TimeoutError, socket.timeout):
                pass
            time.sleep(2 * (i + 1))
        raise IOError(f"{method} {url} failed")

    def get(self, key):
        if self.local:
            p = os.path.join(self.local, key); return json.load(open(p)) if os.path.exists(p) else None
        b = self._req("GET", f"https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/{urllib.parse.quote(key, safe='')}?alt=media")
        return json.loads(b) if b is not None else None

    def put(self, key, obj, ctype="application/json"):
        data = (obj if isinstance(obj, (bytes, str)) else json.dumps(obj, default=str, separators=(",", ":"))).encode() if not isinstance(obj, bytes) else obj
        if self.local:
            p = os.path.join(self.local, key); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data); return
        q = urllib.parse.urlencode({"uploadType": "media", "name": key})
        self._req("POST", f"https://storage.googleapis.com/upload/storage/v1/b/{self.bucket}/o?{q}", data, ctype)

    def list(self, prefix):
        if self.local:
            base = os.path.join(self.local, prefix)
            return sorted(os.path.relpath(os.path.join(a, f), self.local) for a, d, fs in os.walk(base) for f in fs) if os.path.isdir(base) else []
        out, tok = [], None
        while True:
            q = {"prefix": prefix, "fields": "items(name),nextPageToken"}
            if tok: q["pageToken"] = tok
            d = json.loads(self._req("GET", f"https://storage.googleapis.com/storage/v1/b/{self.bucket}/o?" + urllib.parse.urlencode(q)) or b"{}")
            out += [o["name"] for o in d.get("items", [])]; tok = d.get("nextPageToken")
            if not tok: return out


# ------------------------------------------------------------------ versions
def sha_file(p, rewritten=False):
    b = open(p, "rb").read()
    return hashlib.sha256(GT.unrewrite(b) if rewritten else b).hexdigest()


def versions():
    F18 = json.load(open(f"{ROOT}/stage18/FREEZE_STAGE18.json"))["files"]
    lock = json.load(open(f"{ROOT}/env/acolite.lock.json"))
    path = {"aco_driver": "stage14/cert/run_cert_aco.py", "aco_a1": "stage14/cert/run_cert_aco_a1.py", "aco_crop": "stage13/tools/aco13_one.py",
            "aco_run": "stage12/tools/aco12_one.py", "sampler": "stage13/tools/sample_variants.py", "safe": "stage11/tools/safe.py",
            "sen2cor_readout": "stage6/extract.py"}
    return {"candidate": CANDIDATE, "uncertified": True,
            "frozen": F18,   # engine14, frozen_engine, frozen_gbm, engine16, rule16, lib16, dev17, prereg17, challenger17, freeze18
            "path": {k: sha_file(f"{ROOT}/{p}", rewritten=True) for k, p in path.items()},
            "lake_surface_dws": sha_file(f"{ROOT}/vendor/Sector_Engine-fusion/jobs/lake-surface/derive_water_surface.py"),
            "acolite": {"commit": lock["commit"], "tree": lock["tree"], "lut_lock_sha256": sha_file(f"{ROOT}/env/acolite.lock.json")},
            "production_model": {"id": "secchi-power-v1", "a": PROD_A, "b": PROD_B, "range80_log10": PROD_RANGE},
            "job": {"commit": os.environ.get("JOB_COMMIT", "dev"), "shadow_py": sha_file(__file__), "challenger17_py": sha_file(C17.__file__),
                    "pilot_lakes": sha_file(os.path.join(HERE, "pilot_lakes.json"))},
            "s2c22": {"path": C22.PATH, "scope": "nominal S2C baselines >= 05.11 (Stage 12 retired)", "hashes": C22.HASHES, "s2c22_py": sha_file(C22.__file__),
                      "aco21_one": sha_file(f"{ROOT}/stage21/aco21_one.py"), "aco20_one": sha_file(f"{ROOT}/stage20/aco20_one.py"), "toa21": sha_file(f"{ROOT}/stage21/toa21.py")}}


# ------------------------------------------------------------------ self-checks against frozen outputs
def golden_one_scene():
    """The smallest frozen validation scene through the frozen ACOLITE path, compared exactly."""
    import tempfile, shutil
    T = [t for t in json.load(open(f"{ROOT}/stage14/cert/validate_tasks.json")) if t["item"] == "S2A_T10TFQ_20210728T185732_L2A"]
    d = tempfile.mkdtemp(prefix="g1-"); tp = os.path.join(d, "t.json"); json.dump(T, open(tp, "w"))
    try:
        p = subprocess.run([sys.executable, f"{ROOT}/stage14/cert/run_cert_aco_a1.py", tp, d + "/res", "--workers", "1"], capture_output=True, text=True)
        a = json.load(open(f"{d}/res/{T[0]['item']}.json")); b = json.load(open(f"{ROOT}/stage14/cert/validate_res/{T[0]['item']}.json"))
        n, mx, diffs = GT.compare_res(a, b)
        return {"scene": T[0]["item"], "values": n, "max_abs_diff": mx, "structural_diffs": diffs[:3], "pass": p.returncode == 0 and n == 22 and mx == 0.0 and not diffs}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def self_check(store, full_scenes, skip_golden):
    r = {"task": TASK, "host": socket.gethostname(), "machine": platform.machine(), "python": platform.python_version()}
    try:
        r["cpu"] = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    except Exception:
        r["cpu"] = platform.processor()
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as cf
        r["numpy_simd"] = sorted(k for k, v in cf.items() if v)
    except Exception:
        pass
    r["env"] = json.loads(subprocess.run([sys.executable, f"{ROOT}/env/verify_env.py", "--json"], capture_output=True, text=True).stdout or "{}")
    r["hashes"] = GT.check_hashes(); r["engine"] = GT.check_selfcheck(); r["challenger"] = C17.check_fixtures()
    if skip_golden:
        r["scenes"] = {"skipped": True, "pass": True}
    elif full_scenes:
        r["scenes"] = GT.check_scenes(workers=2)
    else:
        r["scenes"] = golden_one_scene()
    r["pass"] = bool(r["env"].get("ENV_OK")) and all(r[k]["pass"] for k in ("hashes", "engine", "challenger", "scenes"))
    store.put(f"{PREFIX}/runs/{EXECUTION}/selfcheck-task{TASK}.json", r)
    return r


# ------------------------------------------------------------------ production answers
def prod_feet(fnu):
    ft = PROD_A * max(fnu, 0.1) ** PROD_B
    band = "< 1 ft" if ft < 1 else "1–2 ft" if ft < 2 else "2–4 ft" if ft < 4 else "4–6 ft" if ft < 6 else "6+ ft"
    return {"feet": ft, "range80_ft": [ft * 10 ** PROD_RANGE[0], ft * 10 ** PROD_RANGE[1]], "band": band}


def production_disk(s):
    if not s: return {"available": False, "reason": "point outside this scene"}
    if s.get("fnu_prod") is None or (s.get("n_valid") or 0) < 5:
        return {"available": False, "reason": f"production gates left {s.get('n_valid', 0)} of {s.get('n_disk', 0)} disk pixels (< 5)"}
    return {"available": True, "fnu": s["fnu_prod"], "n_valid": s["n_valid"], **prod_feet(s["fnu_prod"])}


_layer_cache = {}


def production_layer(lake_id, date, lat, lon):
    """The published Water Clarity layer (what the app shows) at the point, for this pass date."""
    import re
    slug = re.sub(r"[^A-Za-z0-9]+", "_", lake_id).strip("_"); key = (slug, date)
    if key not in _layer_cache:
        try:
            with urllib.request.urlopen(LAYER.format(slug=slug, date=date), timeout=30) as r: _layer_cache[key] = json.load(r)
        except Exception as e:
            _layer_cache[key] = {"error": str(e)[:80]}
    g = _layer_cache[key]
    if "values" not in g: return {"available": False, "reason": f"production published no layer for {date}"}
    (wl, nl), (el, _), (_, sl), _ = g["cornersLonLat"]
    mx = lambda lo: math.radians(lo); my = lambda la: math.log(math.tan(math.pi / 4 + math.radians(la) / 2))
    c = int((mx(lon) - mx(wl)) / (mx(el) - mx(wl)) * g["width"]); r = int((my(nl) - my(lat)) / (my(nl) - my(sl)) * g["height"])
    if not (0 <= r < g["height"] and 0 <= c < g["width"]): return {"available": False, "reason": "point outside the published grid"}
    v = base64.b64decode(g["values"])[r * g["width"] + c]; m = base64.b64decode(g["measured"])[r * g["width"] + c]
    if v == 0: return {"available": False, "reason": "no value in the published cell"}
    e = g["encoding"]; fnu = 10 ** (e["lo"] + (v - 1) / (e["top"] - 1) * (e["hi"] - e["lo"]))
    return {"available": True, "fnu": fnu, "measured": m == 255, "cell_m": g["cellMetresMercator"], **prod_feet(fnu)}


# ------------------------------------------------------------------ scenes
def search(points, start, end):
    lats = [p["lat"] for p in points]; lons = [p["lon"] for p in points]
    body = {"collections": [E6.dws.S2_COLLECTION], "bbox": [min(lons) - 0.01, min(lats) - 0.01, max(lons) + 0.01, max(lats) + 0.01],
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 100}
    items, url = [], E6.ES_SEARCH
    while True:
        d = E6.post(url, body); items += d.get("features", [])
        nxt = next((l for l in d.get("links", []) if l.get("rel") == "next"), None)
        if not nxt or len(items) >= 500: break
        body = nxt.get("body") or body; url = nxt.get("href") or url
    return sorted({i["id"]: i for i in items}.values(), key=lambda i: i["properties"]["datetime"])


def process_item(lake, item, workdir, twins):
    """-> per-point records for one L2A item, or None when no pilot point lies in the scene. `twins` maps an L1C name to a
    stored scene of this lake: Earth Search splits one acquisition into datastrip items that share one L1C, and ACOLITE on
    the same L1C and crop gives the same samples, so they are reused rather than run again."""
    p = item["properties"]
    meta = {"item": item["id"], "pass_time": p["datetime"], "pass_date": p["datetime"][:10], "platform": p.get("platform"),
            "tile": p.get("grid:code"), "baseline": p.get("s2:processing_baseline"), "scene_cloud": p.get("eo:cloud_cover"),
            "sun_elev": p.get("view:sun_elevation"), "view_inc": p.get("view:incidence_angle")}
    readouts = {}
    for pt in lake["points"]:
        try:
            readouts[pt["key"]] = E6.sample(item, pt["lat"], pt["lon"])
        except Exception as e:
            readouts[pt["key"]] = {"readout_error": str(e)[:160]}
    covered = {k for k, v in readouts.items() if v}
    if not covered: return None, meta
    task = {"item": item["id"], "pass_time": p["datetime"],
            "crops": [c for c in lake["crops"] if any(q[2] in covered for q in c["points"])]}
    t0 = time.time(); l1c = RCA.l1c_name(task); twin = twins.get(l1c) if l1c else None
    need = {(c["lat"], c["lon"]) for c in task["crops"]}
    if twin and need <= {tuple(x) for x in twin["meta"].get("crops_run", [])}:
        pts = twin["acolite_points"]
        meta.update({"l1c": l1c, "acolite_reused_from": twin["meta"]["item"], "acolite_seconds": 0.0, "crops_run": twin["meta"]["crops_run"]})
    else:
        RCA.one(task, workdir)
        aco = json.load(open(os.path.join(workdir, item["id"] + ".json")))
        meta.update({"l1c": aco.get("l1c"), "acolite_error": aco.get("error"), "acolite_seconds": round(time.time() - t0, 1),
                     "crops_run": [[c["lat"], c["lon"]] for c in aco.get("crops", [])]})
        pts = {}
        for c in aco.get("crops", []):
            for k, v in (c.get("points") or {}).items(): pts[k] = v
    # Stage 22: nominal S2C also runs the C3 path (TOA B11/B12 offsets before ACOLITE); datastrip twins reuse it
    c3, c3pts = None, {}
    if C22.nominal(meta["platform"], meta["baseline"]) and meta.get("l1c"):
        if twin and twin.get("c3_points") is not None and need <= {tuple(x) for x in twin["meta"].get("crops_run", [])}:
            c3pts = twin["c3_points"]; c3 = dict(twin["meta"].get("c3") or {}, reused_from=twin["meta"]["item"])
        else:
            _fetch = lambda n: SAFE.fetch(n, ("HTML/", "rep_info/", "preview", "_TCI.jp2"))
            r3 = C22.run_c3(task, meta["l1c"], _fetch, SAFE.delete, workdir)
            c3 = {"toa_sub": r3.get("toa_sub"), "m_C": r3.get("m_C"), "acolite_seconds": r3.get("seconds"), "errors": [c.get("error") for c in r3["crops"] if c.get("error")]}
            for c in r3["crops"]:
                for kk, v in (c.get("points") or {}).items(): c3pts[kk] = v
        c3.update({"path": C22.PATH, "hashes": C22.HASHES, "stage12_retired": True, "authority": "lower"})
        meta["s2c_path"] = C22.PATH; meta["c3"] = c3
    out = {}
    for pt in lake["points"]:
        k = pt["key"]; s = readouts.get(k)
        if not s: continue
        a = pts.get(k) or {}
        g = (lambda x: float(x) if x not in (None, "") else None)
        sen = {"blue": g(s.get("rho_blue_v")), "green": g(s.get("rho_green_v")), "red": g(s.get("rho_red_v")), "re1": g(s.get("rho_rededge1_v")),
               "swir16": g(s.get("rho_swir16_v"))} if not s.get("readout_error") else None
        o16 = E16.answer16(a.get("M0"), a.get("M3"), sen, meta["sun_elev"], meta["platform"])
        o16_stage12 = None
        if c3 is not None:                                   # Stage 22: nominal S2C answered on the C3 path; Stage 12 answer kept
            a3 = c3pts.get(k) or {}; o16_stage12 = o16
            o16 = C22.answer16_c3(a3.get("M0"), a3.get("M3"), sen, meta["sun_elev"], E14, E16)
        out[k] = {"point": k, "lat": pt["lat"], "lon": pt["lon"],
                  "readout": {x: s.get(x) for x in ("n_disk", "n_valid", "n_water", "fnu_prod", "readout_error")},
                  "inputs": {"M0": a.get("M0"), "M3": a.get("M3"), "n_radius": a.get("n_radius"), "sen2cor": sen, "sun_elev": meta["sun_elev"],
                             "platform": meta["platform"], "acolite_point_error": a.get("error")},
                  "production": {"layer": production_layer(lake["directory_id"], meta["pass_date"], pt["lat"], pt["lon"]), "disk": production_disk(s)},
                  "stage16": o16}
        if c3 is not None:
            out[k]["stage16_stage12"] = o16_stage12
            out[k]["inputs_c3"] = {"M0": (c3pts.get(k) or {}).get("M0"), "M3": (c3pts.get(k) or {}).get("M3"), "acolite_point_error": (c3pts.get(k) or {}).get("error")}
    meta["_acolite_points"] = pts
    if c3 is not None: meta["_c3_points"] = c3pts
    return out, meta


def scene_view(rec, meta):
    """The fields the challenger needs from one point-scene record."""
    o = rec["stage16"]
    return {"item": meta["item"], "day": dt.date.fromisoformat(meta["pass_date"]).toordinal(), "date": meta["pass_date"], "platform": meta["platform"],
            "scene_cloud": meta.get("scene_cloud"), "sun_elev": meta.get("sun_elev"), "tier": o.get("tier"), "p": o.get("p") if o.get("tier") in (1, 2) else None,
            "n_valid": (rec["readout"] or {}).get("n_valid"), "readout_error": (rec["readout"] or {}).get("readout_error"), "stage16": o}


def challenger_for(ch, anchor, history):
    nb = C17.select_neighbours(anchor, history)
    sc = C17.scene_list(anchor, nb)
    o = ch.build(sc, anchor["stage16"])
    full = [s for s in sc if s["platform"] != "sentinel-2c"]
    status = "consensus" if len(full) >= 2 else "single-scene" if full else "fallback-stage16"
    return {"status": status, "enough_neighbours": len(full) >= 2, "window": "one-sided: this pass and the 10 days before it",
            "neighbours": [{"item": n["item"], "date": n["date"], "dt_days": n["day"] - anchor["day"], "platform": n["platform"], "tier": n["tier"], "p": n["p"]} for n in nb],
            "contributing": len(full), "answer": o, "evidence": ch.evidence(o)}


def summary_row(lake, meta, rec, c17):
    o = rec["stage16"]; L = rec["production"]["layer"]; D = rec["production"]["disk"]; a = c17["answer"]
    return {"lake": lake["slug"], "point": rec["point"], "item": meta["item"], "date": meta["pass_date"], "platform": meta["platform"], "l1c": meta.get("l1c"),
            "production_layer_ft": L.get("feet"), "production_layer_band": L.get("band"), "production_disk_ft": D.get("feet"), "production_disk_band": D.get("band"),
            "s16_state": o.get("state"), "s16_display": o.get("display"), "s16_feet_shown": o.get("feet_shown"), "s16_tier": o.get("tier"),
            "s16_authority": o.get("authority"), "s16_evidence": o.get("evidence"), "s16_conf": o.get("conf"), "s16_algal": o.get("algal"), "s16_ndci": o.get("ndci"),
            "s16_s2c": o.get("s2c"), "s16_p": o.get("p"), "s16_interval_ft": o.get("interval_ft"),
            "s17_status": c17["status"], "s17_state": a.get("state") if c17["enough_neighbours"] else None, "s17_conf": a.get("conf") if c17["enough_neighbours"] else None,
            "s17_evidence": c17["evidence"] if c17["enough_neighbours"] else None, "s17_p": a.get("p") if c17["enough_neighbours"] else None,
            "s17_n": c17["contributing"], "s17_sigma_log10": a.get("sigma_log10")}


def _mode(xs):
    from collections import Counter
    c = Counter(x for x in xs if x is not None)
    return min(c, key=lambda k: (-c[k], str(k))) if c else None


def _median(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    return float(np.median(xs)) if xs else None


def lake_summary(pts):
    """One line per answer for the lake on its newest usable pass date (the app's sheet reads this)."""
    from collections import Counter
    use = [p["latest_usable"] for p in pts if p.get("latest_usable")]
    passes = [p["latest_pass"]["date"] for p in pts if p.get("latest_pass")]
    if not use:
        return {"latest_pass_date": max(passes) if passes else None, "latest_usable_date": None}
    day = max(e["date"] for e in use); on = [e for e in use if e["date"] == day]
    s16 = [e["stage16"] for e in on]; s17 = [e["stage17"] for e in on if e["stage17"]["enough_neighbours"]]
    s17d = [e["stage17_one_per_pass"] for e in on if (e.get("stage17_one_per_pass") or {}).get("enough_neighbours")]
    L = [e["production"]["layer"] for e in on if e["production"]["layer"].get("available")]
    D = [e["production"]["disk"] for e in on if e["production"]["disk"].get("available")]
    return {"latest_pass_date": max(passes), "latest_usable_date": day, "points": len(on), "points_total": len(pts),
            "stage16": {"state": _mode(o["state"] for o in s16), "states": dict(Counter(o["state"] for o in s16)),
                        "evidence": _mode(o["evidence"] for o in s16), "feet_shown_median": _median(o.get("feet_shown") for o in s16),
                        "authority": _mode(o["authority"] for o in s16), "algal_points": sum(1 for o in s16 if o.get("algal")),
                        "s2c": any(o.get("s2c") for o in s16), "conf_median": _median(o.get("conf") for o in s16),
                        "platforms": sorted({e["platform"] for e in on})},
            "stage17": ({"state": _mode(c["answer"]["state"] for c in s17), "states": dict(Counter(c["answer"]["state"] for c in s17)),
                         "evidence": _mode(c["evidence"] for c in s17), "conf_median": _median(c["answer"].get("conf") for c in s17),
                         "points": len(s17), "scenes_median": _median(c["contributing"] for c in s17)} if s17 else
                        {"state": None, "points": 0, "note": "not enough neighbouring scenes in the 10 days before this pass"}),
            "stage17_one_per_pass": {"state": _mode(c["answer"]["state"] for c in s17d), "points": len(s17d),
                                     "note": "diagnostic, not frozen: the challenger with one scene per satellite pass"},
            "production": {"layer_band": _mode(x["band"] for x in L), "layer_ft_median": _median(x["feet"] for x in L), "layer_points": len(L),
                           "disk_band": _mode(x["band"] for x in D), "disk_ft_median": _median(x["feet"] for x in D), "disk_points": len(D)}}


def run_lake(store, lake, start, end, ver, max_items, workdir):
    t0 = time.time(); key = f"{PREFIX}/scenes/{lake['slug']}"
    stored0 = [store.get(n) for n in sorted(store.list(key + "/")) if n.endswith(".json")]
    redo = {s["meta"]["item"] for s in stored0 if s and s.get("points") and C22.nominal(s["meta"].get("platform"), s["meta"].get("baseline")) and s["meta"].get("s2c_path") != C22.PATH}
    done = {s["meta"]["item"] for s in stored0 if s} - redo           # Stage 22: stored nominal-S2C scenes are re-answered on the C3 path
    items = search(lake["points"], start, end); new = [i for i in items if i["id"] not in done][:max_items or None]
    stats = {"lake": lake["slug"], "searched": len(items), "already": len(items) - len([i for i in items if i["id"] not in done]), "new": len(new), "processed": 0,
             "outside": 0, "errors": [], "acolite_seconds": 0.0}
    stored = [store.get(n) for n in sorted(store.list(key + "/")) if n.endswith(".json")]
    twins = {s["meta"]["l1c"]: s for s in stored if s and s.get("acolite_points") is not None and s["meta"].get("l1c") and s["meta"].get("crops_run")}
    for it in new:
        try:
            recs, meta = process_item(lake, it, workdir, twins)
            if recs is None:
                meta.pop("_acolite_points", None)
                store.put(f"{key}/{it['id']}.json", {"schema": "clarity-candidate-scene/1", "meta": meta, "points": {}, "note": "no pilot point in this scene"}); stats["outside"] += 1; continue
            acop = meta.pop("_acolite_points", {}); c3p = meta.pop("_c3_points", None)
            store.put(f"{key}/{it['id']}.json", {"schema": "clarity-candidate-scene/1", "candidate": CANDIDATE, "label": LABEL, "uncertified": True,
                                                 "lake": lake["slug"], "directory_id": lake["directory_id"], "meta": meta, "points": recs, "versions": ver,
                                                 "acolite_points": acop, "c3_points": c3p,
                                                 "processed_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "execution": EXECUTION})
            stats["processed"] += 1; stats["acolite_seconds"] += meta.get("acolite_seconds") or 0
            if meta.get("l1c") and meta.get("crops_run") and meta["l1c"] not in twins:
                twins[meta["l1c"]] = {"meta": meta, "points": recs, "acolite_points": acop, "c3_points": c3p}
        except Exception as e:
            stats["errors"].append({"item": it["id"], "error": f"{type(e).__name__}: {str(e)[:200]}", "trace": traceback.format_exc()[-600:]})
    # Rebuild this lake's history, challenger answers and latest view from every stored scene (cheap; scenes are small).
    # FROZEN stage17: every Earth Search item is a scene, exactly as the research selected them (unique items) - which
    # lets one datatake count twice (overlapping tiles, datastrip twins). DIAGNOSTIC stage17_one_per_pass: the same
    # frozen challenger with one scene per satellite pass (satellite + day), the best-read item kept. Not a frozen rule.
    rows = []
    scenes = [store.get(n) for n in sorted(store.list(key + "/")) if n.endswith(".json")]
    scenes = sorted([s for s in scenes if s and s.get("points")], key=lambda s: s["meta"]["pass_time"])
    ch = C17.Challenger(); latest = {}
    tier_rank = {1: 0, 2: 1, 3: 2, 0: 3}
    best = {}
    for s in scenes:
        for k, rec in s["points"].items():
            o = rec["stage16"]; a = (rec.get("inputs") or {}); r = rec.get("readout") or {}
            n_aco = max(((a.get("M0") or {}).get("n") or 0), ((a.get("M3") or {}).get("n") or 0))
            rank = (tier_rank.get(o.get("tier"), 4), -n_aco, -(r.get("n_valid") or 0), s["meta"]["item"])
            pk = (k, s["meta"]["platform"], s["meta"]["pass_date"])
            if pk not in best or rank < best[pk][0]: best[pk] = (rank, s["meta"]["item"])
    # every scene of a point (select_neighbours keeps those on or before the anchor's day, never the anchor itself)
    hist, hist1 = {}, {}
    for s in scenes:
        for k, rec in s["points"].items():
            v = scene_view(rec, s["meta"]); hist.setdefault(k, []).append(v)
            if best[(k, s["meta"]["platform"], s["meta"]["pass_date"])][1] == s["meta"]["item"]: hist1.setdefault(k, []).append(v)
    for s in scenes:
        for k, rec in s["points"].items():
            v = scene_view(rec, s["meta"])
            c17 = challenger_for(ch, v, hist[k])
            canonical = best[(k, s["meta"]["platform"], s["meta"]["pass_date"])][1] == s["meta"]["item"]
            c17d = challenger_for(ch, v, hist1[k]) if canonical else None
            row = summary_row(lake, s["meta"], rec, c17)
            row.update({"pass_canonical": canonical,
                        "s17_one_per_pass_state": c17d["answer"].get("state") if c17d and c17d["enough_neighbours"] else None,
                        "s17_one_per_pass_status": c17d["status"] if c17d else "not the pass's best-read item"})
            rows.append(row)
            if not canonical: continue
            usable = rec["stage16"].get("state") not in (None, "Unknown / Low Authority") and rec["stage16"].get("tier") in (1, 2, 3)
            ent = {"date": s["meta"]["pass_date"], "item": s["meta"]["item"], "platform": s["meta"]["platform"], "l1c": s["meta"].get("l1c"),
                   "production": rec["production"], "stage16": rec["stage16"], "stage17": c17, "stage17_one_per_pass": c17d}
            L = latest.setdefault(k, {"point": k, "lat": rec["lat"], "lon": rec["lon"]})
            L["latest_pass"] = ent
            if usable: L["latest_usable"] = ent
    store.put(f"{PREFIX}/log/{lake['slug']}.json", {"schema": "clarity-candidate-log/1", "label": LABEL, "rows": rows, "versions": ver})
    pts = [latest.get(p["key"], {"point": p["key"], "lat": p["lat"], "lon": p["lon"]}) for p in lake["points"]]
    store.put(f"{PREFIX}/latest/{lake['slug']}.json", {"schema": "clarity-candidate-latest/1", "candidate": CANDIDATE, "label": LABEL, "uncertified": True,
                                                       "lake": lake["slug"], "directory_id": lake["directory_id"], "why": lake["why"],
                                                       "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "execution": EXECUTION,
                                                       "scenes": len(scenes), "summary": lake_summary(pts), "points": pts, "versions": ver})
    stats["seconds"] = round(time.time() - t0, 1); stats["scenes_total"] = len(scenes)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lakes"); ap.add_argument("--lookback", type=int, default=int(os.environ.get("LOOKBACK_DAYS", "10")))
    ap.add_argument("--local"); ap.add_argument("--max-items", type=int, default=0); ap.add_argument("--skip-golden", action="store_true")
    a = ap.parse_args()
    store = Store(BUCKET, a.local); ver = versions()
    lakes = json.load(open(os.path.join(HERE, "pilot_lakes.json")))["lakes"]
    if a.lakes: lakes = [l for l in lakes if l["slug"] in a.lakes.split(",")]
    mine = [l for i, l in enumerate(lakes) if i % NTASKS == TASK]
    print(f"task {TASK}/{NTASKS} lakes {[l['slug'] for l in mine]}", flush=True)
    sc = self_check(store, full_scenes=(TASK == 0), skip_golden=a.skip_golden)
    print("self-check", "PASS" if sc["pass"] else "FAIL", json.dumps({k: sc[k].get("pass") for k in ("hashes", "engine", "challenger", "scenes")}), flush=True)
    if not sc["pass"]:
        store.put(f"{PREFIX}/runs/{EXECUTION}/task{TASK}.json", {"status": "self-check-failed", "selfcheck": sc}); sys.exit(2)
    end = dt.date.today(); start = end - dt.timedelta(days=a.lookback)
    workdir = os.path.join(ROOT, "stage14", "work", f"shadow-{TASK}")
    import shutil; shutil.rmtree(workdir, ignore_errors=True); os.makedirs(workdir)    # never reuse an earlier run's samples
    res = []
    for lake in mine:
        print("lake", lake["slug"], flush=True)
        res.append(run_lake(store, lake, start.isoformat(), end.isoformat(), ver, a.max_items, workdir)); print(json.dumps(res[-1])[:400], flush=True)
    store.put(f"{PREFIX}/runs/{EXECUTION}/task{TASK}.json", {"status": "ok", "window": [start.isoformat(), end.isoformat()], "lakes": res,
                                                             "selfcheck_pass": True, "versions": ver, "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat()})
    print("SHADOW_DONE", flush=True)


if __name__ == "__main__":
    main()
