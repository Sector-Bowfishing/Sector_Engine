"""Addendum A3 (value-blind): reproduce finalize_wqp.py's selection order exactly, then trim WQP rows of any state above
15% of the combined US core (NLA + WQP), last-selected first. Rewrites wqp_sample.csv and blind_checks14.json."""
import csv, json, hashlib, shutil, collections, runpy, sys
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
C = f"{S}/stage14/cert"
shutil.copy(f"{C}/wqp_sample.csv", f"{C}/wqp_sample_pre_a3.csv")
src = open(f"{C}/finalize_wqp.py").read()
sel = src.split("keep.sort(key=lambda r: r[\"id\"])")[0]          # everything up to the final sort: keep is in selection order
ns = {}; exec(sel, ns); keep = ns["keep"]
prev = {r["id"] for r in csv.DictReader(open(f"{C}/wqp_sample_pre_a3.csv"))}
assert {r["id"] for r in keep} == prev, "selection replay mismatch"
nla = [r for r in csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv")) if r["src"].startswith("NLA")]
removed = []
while True:
    us = nla + keep; st = collections.Counter(r["state"] for r in us)
    over = [s for s, n in st.items() if n / len(us) > 0.15]
    if not over: break
    s = over[0]; i = max(j for j, r in enumerate(keep) if r["state"] == s); removed.append(keep.pop(i)["id"])
print("removed", len(removed), collections.Counter(r.split("|")[0][:12] for r in removed))
rest = src.split("keep.sort(key=lambda r: r[\"id\"])")[1]
ns2 = dict(ns); ns2["keep"] = keep
exec("keep.sort(key=lambda r: r[\"id\"])" + rest, ns2)
F = json.load(open(f"{S}/stage14/FREEZE_STAGE14.json"))
for p in ("stage14/cert/ADDENDUM_A3_statecap.md", "stage14/cert/finalize_a3.py", "stage14/cert/wqp_sample_pre_a3.csv", "stage14/cert/wqp_sample.csv"):
    F["files"][p] = hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest()
import datetime
F["addenda"].append({"id": "A3", "at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "file": "stage14/cert/ADDENDUM_A3_statecap.md",
                     "summary": f"state cap applied over the combined US core; {len(removed)} WQP rows removed (value-blind)"})
json.dump(F, open(f"{S}/stage14/FREEZE_STAGE14.json", "w"), indent=1)
