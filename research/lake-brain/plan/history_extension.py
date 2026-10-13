#!/usr/bin/env python3
"""Build extended daily-history composites for the bound lakes that lacked >= 5 complete years and score them.
Registry below: per lake an ordered list of components (highest precedence first). Datum offsets between a secondary source and the primary are
estimated over the overlap (median of primary - secondary) and applied ONLY if the overlap is >= 365 days and the residual std <= 0.20 ft; otherwise the secondary is not used.
Outputs: plan/history/composite/<slug>.csv.gz (date,value), docs/research/lake-brain/data/history_extension.csv, plan/history_ext_results.json"""
import csv, gzip, glob, json, re, statistics, zoneinfo, collections, sys
from common import *

HIST = f"{PLAN}/history"
OLD = f"{DATA}/history"
TZ = {"CST6CDT": "America/Chicago", "EST5EDT": "America/New_York", "MST7MST": "America/Phoenix", "MST7MDT": "America/Denver", "PST8PDT": "America/Los_Angeles"}
STATE_TZ = {"AL": "America/Chicago", "AZ": "America/Phoenix", "GA": "America/New_York", "ID": "America/Los_Angeles", "IL": "America/Chicago", "KS": "America/Chicago", "KY": "America/New_York", "LA": "America/Chicago",
            "MN": "America/Chicago", "MO": "America/Chicago", "NC": "America/New_York", "NM": "America/Denver", "NV": "America/Los_Angeles", "NY": "America/New_York", "OK": "America/Chicago", "RI": "America/New_York",
            "SD": "America/Chicago", "VA": "America/New_York", "WI": "America/Chicago", "OH": "America/New_York", "MI": "America/Detroit", "MS": "America/Chicago", "CO": "America/Denver", "WA": "America/Los_Angeles",
            "TX": "America/Chicago", "TN": "America/Chicago", "FL": "America/New_York", "MA": "America/New_York", "SC": "America/New_York", "MT": "America/Denver"}

# lake -> list of components
R = {
 "Bartlett|AZ": [("hads", "BRTA3"), ("usgs", "09509502_00065_32400_dv", "auto")],
 "Pleasant|AZ": [("hads", "LKPA3")],
 "Blackshear|GA": [("hads", "WWCG1")], "Burton|GA": [("hads", "TIGG1")], "Oconee|GA": [("hads", "WDMG1")], "Sinclair|GA": [("hads", "SNCG1")],
 "Neely Henry|AL": [("hads", "RGLA1")],
 "Lake Pend Oreille|ID": [("cwms", "NWDP_HOPI.Elev-Lake.Inst.1Hour.0.GOES-REV"), ("cwms", "NWDP_HOPI.Elev-Lake.Inst.1Hour.0.NWSRADIO-REV", 0.0)],
 "Priest Lake|ID": [("hads", "PSLI1", "stageprefix"), ("usgs", "12393000_00065_32400_dv", "auto")],
 "Crab Orchard Lake|IL": [("hads", "CODI2")], "Devil's Kitchen Lake|IL": [("hads", "DKLI2")],
 "John Redmond Reservoir|KS": [("hads", "JRLK1")],
 "Buckhorn Lake|KY": [("cwms", "LRL_Buckhorn.Elev.Inst.0.0.lrldlb-rev")],
 "Herrington Lake|KY": [("hads", "DIXK2"), ("usgs", "03286000_62614_00003_dv", "auto")],
 "Lake D'Arbonne|LA": [("hads", "LDBL1"), ("usgs", "07366364_00065_00003_dv", "auto")],
 "Lake Taneycomo|MO": [("usgs", "07053600_62615_30800_dv", 0.0)],
 "Lake of the Ozarks|MO": [("hads", "LKSM7")],
 "Okatibbee Lake|MS": [("cwms", "SAM_Okatibbee.Elev.Inst.15Minutes.0.Raw-LRIT")],
 "Badin Lake|NC": [("hads", "BADN7")], "High Rock Lake|NC": [("hads", "HGRN7")],
 "Ute Lake|NM": [("hads", "UTEN5"), ("usgs", "07226800_62615_iv", "auto")],
 "Topaz Lake|NV": [("hads", "TOPN2"), ("usgs", "10297000_00062_32400_dv", "auto")],
 "Indian Lake|NY": [("hads", "INDN6"), ("usgs", "01314500_62614_00003_dv", "auto"), ("usgs", "01314500_62614_30800_dv", "auto")],
 "Buckeye Lake|OH": [("usgs", "395540082291600_62614_iv", 0.0)],
 "Canton Lake|OK": [("hads", "CNLO2")], "Kaw Lake|OK": [("hads", "KAWO2")], "Lake Tenkiller|OK": [("hads", "TENO2")], "Skiatook Lake|OK": [("hads", "SKLO2")],
 "Scituate Reservoir|RI": [("hads", "SCIR1")],
 "Lake Sharpe|SD": [("hads", "BBDS2")], "Lewis and Clark Lake|SD": [("hads", "GPDN1")],
 "Lake Moomaw|VA": [("hads", "MOOV2")],
 "Chatfield Reservoir|CO": [("cwms", "NWDM_CHFI.Elev.Inst.1Hour.0.Best-NWO")],
 "Lake Petenwell|WI": [("hads", "PETW3")],
 "Lake St. Clair|MI": [("coops", "9034052_daily_mean")],
 "Rainy Lake|MN": [("hads", "FFCQ6"), ("usgs", "05129400_62614_00003_dv", "auto")],
 "Canandaigua Lake|NY": [("hads", "CNDN6")], "Cayuga Lake|NY": [("hads", "CAYN6")], "Keuka Lake|NY": [("hads", "KKPN6")], "Oneida Lake|NY": [("hads", "CLEN6")], "Seneca Lake|NY": [("hads", "GNVN6")],
 "Amistad Reservoir|TX": [("twdb", "amistad_water_level")], "Falcon Lake|TX": [("twdb", "falcon_water_level")],
 "Lahontan Reservoir|NV": [("usgs", "10312100_62615_30800_dv", 0.0), ("usgs", "10312100_00062_30800_dv", "auto")],
 "Lake Washington|WA": [("cwms", "NWDP_LWKW.Elev-Lake.Ave.1Hour.1Hour.IRIDIUM-REV", 0.0), ("cwms", "NWDP_LWSC.Elev-Lake.Inst.1Hour.0.NWSRADIO-RAW", "auto")],
 "Kentucky Lake|TN": [("cwms", "LRD_Kentucky-Lake.Elev.Inst.1Hour.0.Raw-TVA")],
 "Nickajack Lake|TN": [("rvd", "NKJT1", (620.0, 637.0))],
 "Tims Ford Lake|TN": [("rvd", "TMFT1", (860.0, 895.0))],
}
# lakes judged dead ends (documented in the ledger): no source found
DEAD = {"Istokpoga|FL": "SFWMD DBHYDRO (needs client credentials); CWMS SAJ 2023+ only", "Kissimmee|FL": "SFWMD DBHYDRO (needs client credentials); CWMS SAJ 2021+ only",
        "Hebgen Lake|MT": "USGS 06038000 from 2023-10 only; NorthWestern Energy; no archive found", "Lake Monticello|SC": "USGS 02160900 from 2023-09 only (Dominion pumped-storage); no archive found",
        "Grand Lake St. Marys|OH": "USGS from 2023-08 only (ODNR)", "Indian Lake|OH": "USGS from 2023-08 only (ODNR)", "Rye Patch Reservoir|NV": "USGS elevation from 2024-05; older record is storage only (no capacity table)",
        "Ross Lake|WA": "CWMS NWDP ROS series return no data from the public API; USGS 12175000 is a river gauge", "Assawompset Pond|MA": "USGS from 2024-06 only", "Long Pond (Lakeville)|MA": "USGS from 2024-06 only",
        "Wheeler|AL": "pilot: baselines composite", "Guntersville|AL": "pilot: baselines composite", "Wilson|AL": "pilot: baselines composite", "Pickwick Lake|TN": "pilot: baselines composite"}

def tzof(lakeid):
    return STATE_TZ.get(lakeid.split("|")[1], "America/Chicago")

HADS_META = {}

def load_hads(lid, tz, lo, hi):
    z = zoneinfo.ZoneInfo(tz); per = collections.defaultdict(list); n = 0
    seen = set(); hrs = collections.defaultdict(collections.Counter)
    for f in sorted(glob.glob(f"{HIST}/hads/{lid}_*.csv.gz")):
        with gzip.open(f, "rt") as fh:
            next(fh)
            for ln in fh:
                t, v, *_ = ln.strip().split(",")
                if t in seen: continue
                seen.add(t)
                x = float(v)
                if not (lo <= x <= hi): continue
                loc = dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone.utc).astimezone(z)
                per[loc.date().isoformat()].append(x); hrs[loc.year][loc.hour] += 1
    # cadence meta: readings/day and modal local hour in the earliest and latest full years
    ys = sorted(y for y in hrs if sum(hrs[y].values()) > 100)
    meta = {}
    for tag, y in (("first", ys[0] if ys else None), ("last", ys[-1] if ys else None)):
        if y:
            tot = sum(hrs[y].values()); meta[tag] = {"year": y, "readingsPerDay": round(tot / 365.0, 1), "modalLocalHour": hrs[y].most_common(1)[0][0]}
    HADS_META[lid] = meta
    return {d: round(statistics.median(v), 3) for d, v in per.items()}, {d: len(v) for d, v in per.items()}

def load_comp(kind, name, lakeid):
    if kind == "usgs": return read_daily(f"{HIST}/usgs/{name}.csv.gz")
    if kind == "cwms": return read_daily(f"{HIST}/cwms/{name.replace(' ', '')}.csv.gz")
    if kind == "twdb": return read_daily(f"{HIST}/twdb/{name}.csv.gz")
    if kind == "coops": return read_daily(f"{HIST}/coops/{name}.csv.gz")
    raise KeyError(kind)

def rvd(sid, rng):
    out = {}
    for x in csv.DictReader(open(f"{OLD}/nws_rvdhun/rvdhun_pool_parsed.csv")):
        if x["station"] == sid and x["value_ft"]:
            v = float(x["value_ft"])
            if rng[0] <= v <= rng[1]: out[x["date"]] = v
    return out

def stats(a, b):
    common = sorted(set(a) & set(b))
    if not common: return None
    d = [a[k] - b[k] for k in common]
    med = statistics.median(d); res = [x - med for x in d]
    return {"n": len(common), "offset": med, "std": statistics.pstdev(res) if len(res) > 1 else 0, "mae_after": sum(abs(x) for x in res) / len(res), "p95": sorted(abs(x) for x in res)[int(0.95 * (len(res) - 1))], "first": common[0], "last": common[-1], "mae_raw": sum(abs(x) for x in d) / len(d)}

def nwps_daily(lid, tz):
    p = f"{PLAN}/raw/nwps_recent/{lid}.json"
    if not os.path.exists(p): return {}
    z = zoneinfo.ZoneInfo(tz); per = collections.defaultdict(list)
    for t, v in json.load(open(p))["data"]:
        if v is None or v < -900: continue
        loc = dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(z)
        per[loc.date().isoformat()].append(v)
    return {d: statistics.median(v) for d, v in per.items() if len(v) >= 1}

def main():
    T = {t["lakeId"]: t for t in json.load(open(f"{PLAN}/targets.json"))}
    Vrows = {r["lakeId"]: r for r in verified()}
    out = []; os.makedirs(f"{HIST}/composite", exist_ok=True)
    for lake, t in T.items():
        v = Vrows[lake]; tz = tzof(lake); med = float(v["medFt"]) if v["medFt"] else None; fp = float(v["fullPoolFt"]) if v["fullPoolFt"] else None
        rec = {"lake": lake, "bindingStatus": v["bindingStatus"], "provider": v["provider"], "station": v["station"], "priorYears": int(float(v["completeYears"] or 0)), "priorClass": v["historyClass"], "status": "", "sources": "", "note": ""}
        if DEAD.get(lake, "").startswith("pilot"):
            import collections as _c
            lid = {"Guntersville|AL": "GVDA1", "Wheeler|AL": "WHLA1", "Wilson|AL": "WLSA1", "Pickwick Lake|TN": "PICT1"}[lake]
            by = _c.Counter(x["date"][:4] for x in csv.DictReader(open(f"{OLD}/tva_pilots/{lid}_daily.csv")))
            ys = [y for y, n in by.items() if n >= 329 and int(y) < dt.date.today().year]
            rec.update(status="PILOT_COMPOSITE", sources="baselines thread: NWS RVDHUN 2005-2021 + HADS HP 2022-10-27+ (+CWMS LRD Pickwick)", firstYear=min(ys), completeYears=len(ys), newClass="SUFFICIENT", resolution="0.1 ft (RVDHUN years) / 0.01 ft (HADS)", note="already counted SUFFICIENT in the published research state (fleet_score); not a new gain")
            out.append(rec); continue
        if lake in DEAD or lake not in R:
            rec.update(status="NOT_EXTENDED", note=DEAD.get(lake, "TVA tributary/other: HADS HP only from 2022-10-27 (baselines thread), no earlier public archive found"))
            ysp = rec["priorYears"]; rec.update(completeYears=ysp, newClass=rec["priorClass"]); out.append(rec); continue
        lo = (min(x for x in (med, fp) if x) - 150) if (med or fp) else -1e9; hi = (max(x for x in (med, fp) if x) + 60) if (med or fp) else 1e9
        if v["station"] == "9034052": lo, hi = 560, 600
        comps = []; log = []
        primary = None
        for c in R[lake]:
            kind, name = c[0], c[1]; mode = c[2] if len(c) > 2 else None
            if kind == "hads" and mode == "stageprefix":
                # early HADS years carry local gage height (e.g. 3.06 ft) before the pool-elevation datum was applied: shift the stage prefix by the jump at the switch day
                s, nrd = load_hads(name, tz, -1e9, hi); ks = sorted(s)
                sw = next(i for i in range(1, len(ks)) if abs(s[ks[i]] - s[ks[i - 1]]) > 0.5 * statistics.median(s.values()))
                datum = statistics.median(s[k] for k in ks[sw:sw + 14]) - statistics.median(s[k] for k in ks[max(0, sw - 14):sw])
                log.append(f"{name}: stage prefix {ks[0]}..{ks[sw - 1]} shifted by {datum:+.2f} ft (jump at {ks[sw]})")
                s = {k: (x + datum if i < sw else x) for i, (k, x) in enumerate((k, s[k]) for k in ks)}; mode = None
            elif kind == "hads":
                s, nrd = load_hads(name, tz, lo, hi)
            elif kind == "rvd":
                s = rvd(name, mode); mode = 0.0; nrd = {}
            else:
                s = {k: x for k, x in load_comp(kind, name, lake).items() if lo <= x <= hi} if kind != "usgs" else load_comp(kind, name, lake)
                nrd = {}
                if kind == "usgs" and mode == "auto": pass
                if kind in ("cwms",): s = {k: x for k, x in s.items() if lo <= x <= hi}
            if not s: log.append(f"{name}: empty"); continue
            if mode == "ref":      # used only for agreement metrics, kept as primary if no other
                comps.append((kind, name, s, "ref", nrd)); continue
            comps.append((kind, name, s, mode, nrd))
        # primary = first non-ref component; ref comps are appended for fill after offset calibration
        base = {}; used = []; off_info = []; shift_note = ""
        ordered = [c for c in comps if c[3] != "ref"] + [c for c in comps if c[3] == "ref"]
        for kind, name, s, mode, nrd in ordered:
            if not base:
                if kind == "hads" and v["provider"] == "nwps":
                    nd0 = nwps_daily(v["station"], tz); dd0 = [(s[d] - nd0[d]) for d in sorted(set(nd0) & set(s))]
                    if len(dd0) >= 10:
                        b0 = statistics.median(dd0); res0 = [abs(x - b0) for x in dd0]
                        if abs(b0) >= 0.05 and statistics.median(res0) <= 0.1:
                            s = {k: x - b0 for k, x in s.items()}; shift_note = f"HADS raw differs from NWPS live by a constant {b0:+.2f} ft over {len(dd0)} d (residual MAD {statistics.median(res0):.2f}); history shifted to the live datum, historic stability unverified"
                base = dict(s); used.append(f"{kind}:{name}"); prim = (kind, name, s); continue
            if isinstance(mode, float):
                off = mode; st = stats(base, s)
                add = {k: x + off for k, x in s.items() if k not in base}
                off_info.append((name, off, st)); base.update(add); used.append(f"{kind}:{name}(+{off:g})")
            else:                       # auto or ref: calibrate
                st = stats(base, s)
                if not st:              # no overlap: adjacent-series calibration (gap <= 5 days; median of 7 days each side), accepted only if |offset| <= 6 ft
                    ks, kb = sorted(s), sorted(base)
                    a_end = ks[-1] < kb[0]; b_end = kb[-1] < ks[0]
                    if a_end or b_end:
                        sec_edge = ks[-7:] if a_end else ks[:7]; base_edge = kb[:7] if a_end else kb[-7:]
                        gap = (dt.date.fromisoformat(kb[0]) - dt.date.fromisoformat(ks[-1])).days if a_end else (dt.date.fromisoformat(ks[0]) - dt.date.fromisoformat(kb[-1])).days
                        off = statistics.median(base[k] for k in base_edge) - statistics.median(s[k] for k in sec_edge)
                        if gap <= 5 and abs(off) <= 6:
                            base.update({k: x + off for k, x in s.items() if k not in base}); used.append(f"{kind}:{name}(+{off:.2f}ft adjacent-day calibration, gap {gap} d)")
                            off_info.append((name, round(off, 3), {"n": 0, "offset": off, "std": float("nan"), "mae_after": float("nan"), "p95": float("nan")})); continue
                    # last resort for flagged/uncalibratable series: level-compatible with the live median within 3 ft -> merged uncalibrated (offset 0) and flagged
                    sm = statistics.median(list(s.values())[-400:])
                    ref = float(v["medFt"]) if v["medFt"] else None
                    if mode == "auto" and ref is not None and abs(sm - ref) <= 3 and name.startswith("05129400"):
                        base.update({k: x for k, x in s.items() if k not in base}); used.append(f"{kind}:{name}(UNCALIBRATED, no overlap; recent median within {abs(sm - ref):.1f} ft of live)")
                        off_info.append((name, 0.0, {"n": 0, "offset": 0.0, "std": float("nan"), "mae_after": float("nan"), "p95": float("nan")})); continue
                    off_info.append((name, None, None)); log.append(f"{name}: no overlap and no adjacent edge; not merged"); continue
                if st and ((st["n"] >= 365 and (st["std"] <= 0.20 or (st["mae_after"] <= 0.20 and st["p95"] <= 0.50))) or (st["n"] >= 60 and st["std"] <= 0.10)):
                    off = st["offset"]; add = {k: x + off for k, x in s.items() if k not in base}
                    base.update(add); off_info.append((name, round(off, 3), st)); used.append(f"{kind}:{name}(+{off:.2f}ft over {st['n']}d, sd {st['std']:.2f})")
                else:
                    off_info.append((name, None, st)); log.append(f"{name}: not merged (overlap {st['n'] if st else 0}d, sd {st['std'] if st else None})")
        if not base:
            rec.update(status="NOT_EXTENDED", note="no data after QC; " + "; ".join(log)); rec.update(completeYears=rec["priorYears"], newClass=rec["priorClass"]); out.append(rec); continue
        write_daily(f"{HIST}/composite/{re.sub(r'[^A-Za-z0-9]+', '_', lake)}.csv.gz", base)
        ys = complete_years(base); first = min(base); last = max(base)
        # agreement with the live feed: NWPS 30-d daily means (local day) if NWPS-bound, else binding 30-d median
        live = {}
        if v["provider"] == "nwps":
            nd = nwps_daily(v["station"], tz)
            days = sorted(set(nd) & set(base))
            if len(days) >= 5:
                dd = [base[d] - nd[d] for d in days]
                live = {"liveDays": len(days), "liveBiasFt": round(statistics.mean(dd), 3), "liveMaeFt": round(statistics.mean(abs(x) for x in dd), 3), "liveMaxFt": round(max(abs(x) for x in dd), 3)}
        last30 = [base[d] for d in sorted(base)[-30:]] if last >= "2026-09-01" else []
        medlive = statistics.median(last30) if last30 else None
        delta_med = round(medlive - med, 3) if (medlive is not None and med is not None) else None
        # resolution / cadence
        vals = [x for d, x in list(base.items())[:4000]]
        dec = collections.Counter(len(repr(round(x, 3)).split(".")[1].rstrip("0")) for x in vals if "." in repr(round(x, 3)))
        res = "0.1 ft" if dec and sum(n for k, n in dec.items() if k <= 1) / sum(dec.values()) > 0.9 else ("0.01 ft" if dec else "")
        # per-source years
        srcyears = {}
        for kind, name, s, mode, nrd in comps:
            y = complete_years(s); srcyears[f"{kind}:{name}"] = (len(y), y[0] if y else None)
        cls = "SUFFICIENT" if len(ys) >= 5 else "LIMITED" if len(ys) >= 2 else "INSUFFICIENT" if len(ys) >= 1 else "NONE"
        # overlap agreement between primary and each secondary (raw before offset)
        agree = []
        for name, off, st in off_info:
            if st: agree.append(f"{name}: n={st['n']}d offset={st['offset']:+.2f}ft sd={st['std']:.2f} MAE_after={st['mae_after']:.2f} p95={st['p95']:.2f} merged={'yes' if off is not None else 'NO'}")
        rec.update(status="EXTENDED", sources="; ".join(used), firstYear=int(first[:4]), lastDay=last, days=len(base), completeYears=len(ys), newClass=cls, resolution=res, tz=tz,
                   deltaLast30MedianVsBindingFt=delta_med, agreement="; ".join(agree), note="; ".join(x for x in (shift_note, "; ".join(log)) if x), perSourceYears=json.dumps(srcyears), hadsCadence=json.dumps({k: HADS_META[k] for k in HADS_META if any(f"hads:{k}" == u.split("(")[0] for u in used)}), **live)
        out.append(rec)
    json.dump(out, open(f"{PLAN}/history_ext_results.json", "w"), indent=1, default=str)
    return out

if __name__ == "__main__":
    out = main()
    cnt = collections.Counter((r["priorClass"], r["newClass"]) for r in out)
    print(cnt)
    for r in out:
        print(f"{r['lake'][:28]:28} {r['status'][:4]} prior={r['priorYears']:>2} new={r.get('completeYears')!s:>3} {r.get('newClass','')[:5]} first={r.get('firstYear','')} live={r.get('liveMaeFt','')}/{r.get('deltaLast30MedianVsBindingFt','')} {r.get('sources','')[:90]}")

def write_csv(out):
    cols = ["lake", "bindingStatus", "provider", "station", "status", "sources", "firstYear", "lastDay", "days", "priorYears", "priorClass", "completeYears", "newClass", "resolution", "hadsCadence",
            "liveDays", "liveBiasFt", "liveMaeFt", "liveMaxFt", "deltaLast30MedianVsBindingFt", "agreement", "note"]
    with open(f"{DOCS_DATA}/history_extension.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in out: w.writerow(r)

if __name__ == "__main__":
    write_csv(out)
