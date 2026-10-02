"""Stage 11 corpus assembly (PREREGISTRATION_STAGE11.md section 2). One row per agency station-day with a direct
Sentinel-2 read: best pass (smallest |dt|, then most valid pixels), >= 5 valid pixels, production FNU, B04 and B05.
Sets: G (Guntersville, re-read through the C1 collection), N (Stage 7), F (Stage 8), E (Stage 11 expansion).
Same-site same-day truth: turbidity from the pool (NTU/FNU/FTU/NTRU; the surface-most, median), chlorophyll a (Stage 7
unit rules). Supplementary bands and geometry from sample_plus. Lake groups: single linkage within 5 km.
  python assemble.py base      -> corpus_base.json   (no supplementary reads)
  python assemble.py plus      -> corpus.json        (adds sample_plus, run after the chlorophyll fetch)"""
import csv, json, math, sys, collections, hashlib, os
import numpy as np
import concurrent.futures as cf
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage11/corpus"
FT = 3.28084
num = lambda x: float(x) if x not in ("", None) else None


def best_rows(path, idkey="id"):
    best = {}
    for r in csv.DictReader(open(path)):
        if r.get("error"):
            continue
        nv, f = int(num(r.get("n_valid")) or 0), num(r.get("fnu_prod"))
        if nv < 5 or f is None or not r.get("rho_rededge1_v") or not r.get("rho_red_v"):
            continue
        k = (abs(int(r["dt_days"])), -nv)
        if r[idkey] not in best or k < best[r[idkey]][0]:
            best[r[idkey]] = (k, r)
    return [r for _, r in best.values()]


def std_row(r, setname, site, secchi_ft, state):
    g = lambda k: num(r.get(k))
    return {"id": f"{setname}:{r['id']}", "set": setname, "site": site, "state": state, "lat": float(r["lat"]), "lon": float(r["lon"]),
            "date": r["date"], "secchi": secchi_ft, "item": r["item"], "platform": r.get("platform"), "dt": int(float(r["dt_days"])),
            "sun_elev": g("sun_elev"), "view_inc": g("view_inc"), "scene_cloud": g("scene_cloud"), "baseline": r.get("baseline"),
            "n_valid": int(float(r["n_valid"])), "fnu": g("fnu_prod"), "fnu_w": g("fnu_w"),
            "raw": {"blue": g("rho_blue_v"), "green": g("rho_green_v"), "red": g("rho_red_v"), "re1": g("rho_rededge1_v"),
                    "nir": g("rho_nir_v"), "nir08": g("rho_nir08_v"), "swir16": g("rho_swir16_v")},
            "aot": g("aot_site"), "hidden": g("hidden"),
            "veg_drop": max(int(num(r.get("drop_ndvi")) or 0), int(num(r.get("drop_fai")) or 0)), "n_water": int(num(r.get("n_water")) or 0)}


def load_all():
    rows = []
    # G: Guntersville station-days re-read through C1
    for r in best_rows(f"{D}/g_readouts.csv"):
        rows.append(std_row(r, "G", r["site"], float(r["secchi_ft"]), "AL"))
    # N: Stage 7 national rows (already the best pass; keys differ)
    for m in json.load(open(f"{S}/stage7/national_rows.json")):
        if m.get("error"):
            continue
        r = {**m, "rho_blue_v": m["rho_blue"], "rho_green_v": m["rho_green"], "rho_red_v": m["rho_red"], "rho_rededge1_v": m["rho_rededge1"],
             "rho_nir_v": m["rho_nir"], "rho_nir08_v": m["rho_nir08"], "rho_swir16_v": m["rho_swir16"], "fnu_prod": m["fnu"],
             "n_valid": m["n_valid"], "platform": None}
        if not (m.get("rho_rededge1") and m.get("rho_red")) or int(float(m["n_valid"])) < 5:
            continue
        x = std_row(r, "N", m["site_id"], float(m["secchi_m"]) * FT, m["state"])
        x["platform"] = {"S2A": "sentinel-2a", "S2B": "sentinel-2b", "S2C": "sentinel-2c"}.get(m["item"][:3])
        rows.append(x)
    # F: Stage 8 fresh national rows
    for r in best_rows(f"{S}/stage8/fresh_readouts.csv"):
        rows.append(std_row(r, "F", r["site"], float(r["secchi_ft"]), r["state"]))
    # E: Stage 11 expansion
    info = {r["id"]: r for r in csv.DictReader(open(f"{D}/e_draw.csv"))}
    for r in best_rows(f"{D}/e_readouts.csv"):
        x = std_row(r, "E", r["site"], float(r["secchi_ft"]), r["state"]); x["subset"] = info[r["id"]]["set"]; rows.append(x)
    # dedupe the same site-day across sets (E-AL overlaps G): keep the first set in order G, N, F, E
    seen, out = set(), []
    for x in rows:
        k = (x["site"], x["date"])
        if k in seen:
            continue
        seen.add(k); out.append(x)
    return out


def turbidity():
    d = collections.defaultdict(list)
    for r in csv.DictReader(open(f"{S}/q9/wqp/turbidity.csv")):
        if r["unit"] not in ("NTU", "FNU", "FTU", "NTRU"):
            continue
        try:
            v = float(r["value"])
        except ValueError:
            continue
        if not (0 <= v < 5000):
            continue
        dep = num(r.get("depth_m"))
        d[(r["site_id"], r["date"])].append((dep if dep is not None else 0.0, v, r["unit"]))
    out = {}
    for k, vs in d.items():
        top = min(v[0] for v in vs)
        sel = [v for v in vs if v[0] <= top + 0.5]
        out[k] = (float(np.median([v[1] for v in sel])), collections.Counter(v[2] for v in sel).most_common(1)[0][0])
    return out


def chl_file(path, lab_only=False):
    d = collections.defaultdict(list)
    for r in csv.DictReader(open(path)):
        if lab_only and "probe" in (r.get("CharacteristicName") or "").lower():
            continue
        u = (r.get("ResultMeasure/MeasureUnitCode") or "").strip().lower()
        try:
            v = float(r["ResultMeasureValue"])
        except (ValueError, TypeError):
            v = 0.0 if r.get("ResultDetectionConditionText") else None
        if v is None:
            continue
        if u in ("ug/l", "mg/m3", "ppb", "µg/l"):
            pass
        elif u == "mg/l":
            v *= 1000
        else:
            continue
        if 0 <= v < 5000:
            d[(r["MonitoringLocationIdentifier"], r["ActivityStartDate"])].append(v)
    return {k: float(np.median(v)) for k, v in d.items()}


def lake_groups(rows, km=5.0):
    sites = sorted({(x["site"], round(x["lat"], 5), round(x["lon"], 5)) for x in rows})
    uniq = {}
    for s, la, lo in sites:
        uniq.setdefault(s, (la, lo))
    names = list(uniq); xy = np.array([uniq[n] for n in names])
    par = list(range(len(names)))
    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    lat = np.radians(xy[:, 0]); lon = np.radians(xy[:, 1])
    order = np.argsort(xy[:, 0])
    for a_i in range(len(order)):
        i = order[a_i]
        for b_i in range(a_i + 1, len(order)):
            j = order[b_i]
            if xy[j, 0] - xy[i, 0] > km / 111.0:
                break
            dlat, dlon = lat[j] - lat[i], lon[j] - lon[i]
            h = math.sin(dlat / 2) ** 2 + math.cos(lat[i]) * math.cos(lat[j]) * math.sin(dlon / 2) ** 2
            if 2 * 6371.0 * math.asin(math.sqrt(h)) <= km:
                par[find(i)] = find(j)
    g = {n: find(i) for i, n in enumerate(names)}
    rep = {}
    for n, r in g.items():
        rep.setdefault(r, n)
    return {n: "L" + hashlib.md5(rep[r].encode()).hexdigest()[:10] for n, r in g.items()}


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "base":
        rows = load_all()
        tb = turbidity()
        gm = {m["id"].split("|")[0] + "|" + m["date"]: m for m in json.load(open(f"{S}/stage6/matchups.json"))}
        for x in rows:
            t = tb.get((x["site"], x["date"]))
            x["turb"], x["turbUnit"] = (t if t else (None, None))
            if x["turb"] is None and x["set"] == "G":
                m = gm.get(x["site"] + "|" + x["date"])
                if m and m.get("turb") is not None:
                    x["turb"], x["turbUnit"] = m["turb"], "NTU (stage6)"
        grp = lake_groups(rows)
        for x in rows:
            x["lake"] = grp[x["site"]]
        json.dump(rows, open(f"{D}/corpus_base.json", "w"))
        c = collections.Counter(x["set"] for x in rows)
        print("rows", len(rows), dict(c), "lakes", len(set(grp.values())), "with same-day turbidity", sum(x["turb"] is not None for x in rows),
              "same-day turbidity and dt=0", sum(x["turb"] is not None and x["dt"] == 0 for x in rows))
        # the E sites that still need a chlorophyll fetch
        open(f"{D}/e_matched_sites.txt", "w").write("\n".join(sorted({x["site"] for x in rows if x["set"] == "E"})))
    elif mode == "plus":
        rows = json.load(open(f"{D}/corpus_base.json"))
        chl = {}
        for p in (f"{S}/stage6/wqp_Chlorophylla.csv", f"{S}/stage7/wqp_national_chl.csv", f"{S}/stage8/wqp_fresh_chl.csv", f"{D}/wqp_e_chl.csv"):
            if os.path.exists(p):
                for k, v in chl_file(p).items():
                    chl.setdefault(k, v)
        for x in rows:
            x["chl"] = chl.get((x["site"], x["date"]))
        sys.path.insert(0, D)
        import sample_plus as SP
        cache_p = f"{D}/plus_cache.json"
        cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
        todo = [x for x in rows if x["id"] not in cache]
        def one(x):
            try:
                it = SP.item_by_id(x["item"])
                return x["id"], (SP.sample_plus(it, x["lat"], x["lon"]) if it else {"error": "item not found"})
            except Exception as e:
                return x["id"], {"error": str(e)[:120]}
        with cf.ThreadPoolExecutor(10) as ex:
            for i, (k, v) in enumerate(ex.map(one, todo)):
                cache[k] = v
                if i % 100 == 0:
                    json.dump(cache, open(cache_p, "w")); print(i, len(todo), flush=True)
        json.dump(cache, open(cache_p, "w"))
        for x in rows:
            p = cache.get(x["id"]) or {}
            x["plus"] = p
            for k in ("coastal", "rededge2", "rededge3", "swir22", "nir09"):
                x["raw"][k] = p.get(f"rho_{k}_v")
            for k in ("dist_nonwater_m", "glint_deg", "sun_az", "view_az"):
                x[k] = p.get(k)
            if x.get("platform") is None:
                x["platform"] = p.get("platform")
        json.dump(rows, open(f"{D}/corpus.json", "w"))
        print("rows", len(rows), "with chl", sum(x["chl"] is not None for x in rows), "with B07", sum(x["raw"].get("rededge3") is not None for x in rows),
              "with glint", sum(x.get("glint_deg") is not None for x in rows))
