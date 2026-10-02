"""Stage 16 protocol section 4 (value-blind): matched fresh events -> the fresh sample. Match rule as Stage 14 (an item,
>= 5 valid pixels, Sen2Cor red and red-edge present; best pass = smallest |dt|, then most valid pixels). <= 3 per lake
in seeded order (seed 20261001). Writes fresh_sample.csv and hashes it into FREEZE_STAGE16.json."""
import csv, json, random, hashlib, collections, datetime
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage16/fresh"
best = {}
for r in csv.DictReader(open(f"{D}/out_fresh_c1.csv")):
    if r.get("error") or not r.get("item"): continue
    try: nv = int(float(r.get("n_valid") or 0))
    except ValueError: continue
    if nv < 5 or not r.get("rho_red_v") or not r.get("rho_rededge1_v"): continue
    k = (abs(int(float(r.get("dt_days") or 0))), -nv)
    if r["id"] not in best or k < best[r["id"]][0]: best[r["id"]] = (k, r)
ev = {r["id"]: r for r in csv.DictReader(open(f"{D}/fresh_events.csv"))}
M = []
for i, (k, r) in sorted(best.items()):
    r.update({f: ev[i][f] for f in ("site", "org", "strict", "turb_present")}); M.append(r)
by = collections.defaultdict(list)
for r in M: by[r["lake"]].append(r)
g = random.Random(20261001); keep = []
for lk in sorted(by):
    rs = by[lk][:]; g.shuffle(rs); keep += rs[:3]
keep.sort(key=lambda r: r["id"])
cols = ["id", "src", "lake", "state", "lat", "lon", "date", "item", "pass_date", "pass_time", "dt_days", "platform", "season", "site", "org", "strict", "turb_present"]
with open(f"{D}/fresh_sample.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(keep)
sha = hashlib.sha256(open(f"{D}/fresh_sample.csv", "rb").read()).hexdigest()
info = {"matched": len(M), "after_lake_cap": len(keep), "lakes": len({r["lake"] for r in keep}), "states": dict(collections.Counter(r["state"] for r in keep).most_common()),
        "platforms": dict(collections.Counter(r["platform"] for r in keep)), "strict": sum(r["strict"] == "True" for r in keep), "sha256": sha,
        "wisconsin_share": sum(r["state"] == "WI" for r in keep) / max(1, len(keep))}
json.dump(info, open(f"{D}/fresh_sample.json", "w"), indent=1); print(json.dumps(info, indent=1))
F = json.load(open(f"{S}/stage16/FREEZE_STAGE16.json")); F["files"]["stage16/fresh/fresh_sample.csv"] = sha
F["fresh_sample_frozen_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
for p in ("stage16/fresh/fresh_index.py", "stage16/fresh/finalize_fresh.py", "stage16/fresh/fresh_events.csv", "stage16/fresh/in_fresh_c1.csv"):
    F["files"][p] = hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest()
json.dump(F, open(f"{S}/stage16/FREEZE_STAGE16.json", "w"), indent=1)
