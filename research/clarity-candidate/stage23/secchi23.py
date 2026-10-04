"""Stage 23 section 7 (PREREGISTRATION_STAGE23.md): S2C Secchi validation AFTER the section 6 sensor evaluation is recorded
(eval23.json must exist). Executes stage22/secchi22.py verbatim up to its summaries (the same rows: dev outer-fold models with
fold posteriors; cert/fresh production model), on all 137 eligible S2C rows (Stage 22's re-runs plus the re-run SYKE row),
then splits by sun elevation (>= 25 / < 25), season (Apr-Oct / Nov-Mar) and pool. Reference = S2A/B rows (at sun >= 25 for
the decision checks). Writes secchi23.json, secchi23_rows.json."""
import json, os, sys, re, hashlib, collections
S = os.environ["CLARITY_RESEARCH_ROOT"]
F23 = json.load(open(f"{S}/stage23/FREEZE_STAGE23.json"))
assert hashlib.sha256(open(f"{S}/stage23/PREREGISTRATION_STAGE23.md", "rb").read()).hexdigest() == F23["prereg_sha256"]
assert os.path.exists(f"{S}/stage23/eval23.json"), "section 6 must be evaluated first"
src = open(f"{S}/stage22/secchi22.py").read()
cut = src.index('out = {"selected": SEL, "dev_reproduction_check": repro, "pools": {}}')
src = src[:cut]
old = 'glob.glob(f"{S}/stage22/res22_truth/*.json")'
assert src.count(old) == 1
src = src.replace(old, 'sorted(glob.glob(f"{S}/stage22/res22_truth/*.json")) + sorted(glob.glob(f"{S}/stage22/_res_syke/*.json"))')
ns = {"__name__": "secchi23"}
exec(compile(src, "secchi22(verbatim rows)", "exec"), ns)
ROWS, TT, cs, fs, corp_path = ns["ROWS"], ns["TT"], ns["cs"], ns["fs"], f"{S}/stage11/corpus/corpus.json"
smp, smpf, summ, CONTAINS = ns["smp"], ns["smpf"], ns["summ"], ns["CONTAINS"]
corp = {x["id"]: x for x in json.load(open(corp_path))}
date8 = lambda item: (re.search(r"_(20\d{6})T", item or "") or [None, None])[1]
SUN, DAY = {}, {}
for x in TT: SUN[("dev", x["id"])] = x.get("sun_elev"); DAY[("dev", x["id"])] = date8(corp.get(x["id"], {}).get("item")) or (corp.get(x["id"], {}).get("date") or "").replace("-", "")
for (rid, lake, plat, pt, sun, ft), r in zip(cs, smp): SUN[("cert", rid)] = sun; DAY[("cert", rid)] = date8(r.get("item"))
for (rid, lake, plat, pt, sun, ft), r in zip(fs, smpf): SUN[("fresh", rid)] = sun; DAY[("fresh", rid)] = date8(r.get("item"))
for r in ROWS:
    r["sun"] = SUN.get((r["pool"], r["id"])); d = DAY.get((r["pool"], r["id"]))
    r["season"] = None if not d else ("warm" if 4 <= int(d[4:6]) <= 10 else "winter")
missing = sum(1 for r in ROWS if r["sun"] is None or r["season"] is None)
V = {"C3": "C3", "raw": "A"}
def block(rs):
    out = {"reference": summ([r for r in rs if r["variant"] == "ref"])}
    for name, v in V.items(): out[name] = summ([r for r in rs if r["platform"] == "sentinel-2c" and r["variant"] == v])
    return out
subsets = {"all": lambda r: True, "sun_ge25": lambda r: (r["sun"] or 0) >= 25, "sun_lt25": lambda r: r["sun"] is not None and r["sun"] < 25,
           "warm": lambda r: r["season"] == "warm", "winter": lambda r: r["season"] == "winter",
           "dev": lambda r: r["pool"] == "dev", "cert": lambda r: r["pool"] == "cert", "fresh": lambda r: r["pool"] == "fresh",
           "sun_ge25_warm": lambda r: (r["sun"] or 0) >= 25 and r["season"] == "warm", "sun_ge25_winter": lambda r: (r["sun"] or 0) >= 25 and r["season"] == "winter"}
out = {"rows_without_sun_or_season": missing, "subsets": {k: block([r for r in ROWS if f(r)]) for k, f in subsets.items()}}
g = out["subsets"]["sun_ge25"]; c3, ref = g["C3"], g["reference"]
out["checks_sun_ge25"] = {"n_c3": c3["n"], "n_reference": ref["n"], "harmful_le_ref_plus_0.05": c3["harmful"] <= ref["harmful"] + 0.05, "severe_le_0.02": c3["severe"] <= 0.02,
                          "bias_within_0.05_of_ref": abs(c3["signed_log_bias_median"] - ref["signed_log_bias_median"]) <= 0.05,
                          "values": {"c3_harm": c3["harmful"], "ref_harm": ref["harmful"], "c3_sev": c3["severe"], "c3_bias": c3["signed_log_bias_median"], "ref_bias": ref["signed_log_bias_median"]}}
out["checks_sun_ge25"]["PASSED"] = all(out["checks_sun_ge25"][k] for k in ("harmful_le_ref_plus_0.05", "severe_le_0.02", "bias_within_0.05_of_ref"))
json.dump(out, open(f"{S}/stage23/secchi23.json", "w"), indent=1, default=str)
json.dump([{k: r[k] for k in ("pool", "id", "lake", "platform", "variant", "tier", "p", "y", "c", "score", "harmful", "severe", "covered", "sun", "season")} | {"state": r["o"]["state"]} for r in ROWS], open(f"{S}/stage23/secchi23_rows.json", "w"), default=str)
for k, b in out["subsets"].items():
    print(k, " | ".join(f"{n} n{v['n']} op {v.get('operational', 0):.3f} bias {v.get('signed_log_bias_median', 0):+.3f} harm {v.get('harmful', 0):.3f} sev {v.get('severe', 0):.3f} cov {v.get('interval_coverage', 0):.2f}" if v.get("n") else f"{n} n0" for n, v in b.items()))
print("CHECKS sun>=25", out["checks_sun_ge25"], "| rows lacking sun/season", missing)
