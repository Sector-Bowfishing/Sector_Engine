"""Markdown tables for the plan/history research doc (reads plan outputs; no network)."""
import json, csv, collections
from common import *
r = json.load(open(f"{PLAN}/history_ext_results.json"))
S = json.load(open(f"{DOCS_DATA}/history_extension_summary.json"))
P = json.load(open(f"{DOCS_DATA}/plan_summary.json"))
core = lambda x: x["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED")

def src_label(x):
    s = x["sources"]
    parts = []
    for u in s.split("; "):
        k = u.split(":")[0]
        nm = u.split(":", 1)[1].split("(")[0] if ":" in u else u
        parts.append({"hads": f"HADS {nm}", "usgs": f"USGS {nm.split('_')[0]} {nm.split('_')[1]}" if "_" in nm else f"USGS {nm}", "cwms": "CWMS " + nm.split('.')[0].replace('_', ' ') + " (" + nm.split('.')[-1] + ")", "coops": "CO-OPS 9034052", "twdb": "TWDB " + nm.split('_')[0], "rvd": f"RVDHUN {nm}"}.get(k, u))
    return " + ".join(parts)

rows = []
for x in sorted(r, key=lambda x: (not core(x), x["lake"])):
    if x["status"] != "EXTENDED": continue
    live = f"{x['liveMaeFt']:.3f}" if x.get("liveMaeFt") not in (None, "") else "n/a"
    rows.append(f"| {x['lake'].replace('|', ' / ')} | {'core' if core(x) else 'flagged'} | {src_label(x)} | {x['firstYear']} | {x['completeYears']} | {x['priorClass']} -> {x['newClass']} | {x.get('resolution','')} | {live} |")
T_ext = "| Lake | tier | source (precedence order) | first year | complete yr | class | resolution | live MAE ft |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(rows)

nr = []
for x in sorted(r, key=lambda x: x["lake"]):
    if x["status"] == "NOT_EXTENDED":
        nr.append(f"| {x['lake'].replace('|', ' / ')} | {'core' if core(x) else 'flagged'} | {x['priorYears']} y ({x['priorClass']}) | {x['note']} |")
T_not = "| Lake | tier | now | why not |\n|---|---|---|---|\n" + "\n".join(nr)

pr = []
for p, v in P["byProvider"].items():
    pr.append(f"| {p} | {v['lakes']} | {v['verifiedMatch']} | {v['guide']} | {v['zone']} | {v['planStrict']} | {v['floodStrict']} |")
T_prov = "| binding provider (core) | lakes | matched to an operator project | guide | zone | plan strict | flood |\n|---|---|---|---|---|---|---|\n" + "\n".join(pr)
open(f"{PLAN}/tables.json", "w").write(json.dumps({"ext": T_ext, "not": T_not, "prov": T_prov}))
print(T_not)
