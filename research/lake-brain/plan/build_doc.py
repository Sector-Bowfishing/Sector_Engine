"""Assemble docs/research/lake-brain/LAKE_BRAIN_PLAN_HISTORY_RESEARCH.md from doc_template.md + generated tables."""
import json
from common import *
T = json.load(open(f"{PLAN}/tables.json")); S = json.load(open(f"{DOCS_DATA}/history_extension_summary.json"))
rows = []
for k, lab in (("core", "core (258 bound lakes; 55 targets)"), ("flagged", "flagged (57 bound lakes; 16 targets)"), ("all71", "all 71 targets")):
    s = S[k]
    rows.append(f"| {lab} | {s['targets']} | **{s['newlySufficient']}** (from NONE {s['fromNone']}, from LIMITED/INSUFFICIENT {s['fromLimitedOrInsufficient']}) | {s['ge10y']} | {s['ge15y']} | {s['stillLimited']} | {s['stillNone']} | {s['pilotsAlreadyCounted']} |")
tab = "| group | targets | newly SUFFICIENT | of which >= 10 y | >= 15 y | still LIMITED | still NONE | TVA pilots (already counted) |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(rows)
t = open(f"{REPO}/research/lake-brain/plan/doc_template.md").read()
t = t.replace("{{SUMMARY_TABLE}}", tab).replace("{{EXT}}", T["ext"]).replace("{{NOT}}", T["not"]).replace("{{PROV}}", T["prov"])
open(f"{REPO}/docs/research/lake-brain/LAKE_BRAIN_PLAN_HISTORY_RESEARCH.md", "w").write(t)
print(len(t))
