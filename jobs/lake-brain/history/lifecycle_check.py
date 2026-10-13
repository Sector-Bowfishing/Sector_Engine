#!/usr/bin/env python3
"""Model-check of baselines_lifecycle.json against GCS lifecycle semantics for a VERSIONED bucket.

Semantics modelled (GCS docs): a rule fires when ALL its conditions match; matchesPrefix is a literal prefix list
(OR inside the list); `Delete` on a LIVE object of a versioned bucket only makes it NONCURRENT; `Delete` on a
NONCURRENT object removes it for good; `age` = days since that version was created; `daysSinceNoncurrentTime` = days
since it became noncurrent; `isLive:false` matches noncurrent versions only.

Checks: (1) a fleet simulation of the weekly-recompute policy for 400 days: every lake always has exactly one live
baselines/<key>/latest.json, and no object outside baselines/ and baselines-archive/ is ever touched;
(2) the real bucket listing (JSON from `gcloud storage ls -a -r --json`) with the job stopped for 400 days:
nothing outside baselines-archive/ is ever made noncurrent; every history/ presence/ predictions/ history_backup/
object (live and noncurrent) survives.
usage: lifecycle_check.py [bucket_listing.json]
"""
import json, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "baselines_lifecycle.json")))["rule"]

class Obj:
    def __init__(self, name, born, live=True):
        self.name, self.born, self.live, self.nc_since = name, born, live, None

def matches(o, cond, day):
    if "matchesPrefix" in cond and not any(o.name.startswith(p) for p in cond["matchesPrefix"]): return False
    if "isLive" in cond and o.live != cond["isLive"]: return False
    if "age" in cond and (day - o.born) < cond["age"]: return False
    if "daysSinceNoncurrentTime" in cond and (o.live or (day - o.nc_since) < cond["daysSinceNoncurrentTime"]): return False
    return True

def run_lifecycle(objs, day, touched):
    kill = [o for o in objs if any(matches(o, r["condition"], day) for r in RULES)]
    for o in kill:
        touched.add(o.name)
        if o.live: o.live, o.nc_since = False, day        # versioned bucket: live -> noncurrent
        else: objs.remove(o)                                # noncurrent -> gone
    return objs

def write(objs, name, day):
    for o in objs:
        if o.name == name and o.live: o.live, o.nc_since = False, day
    objs.append(Obj(name, day))

def fleet_sim(lakes=315, days=400):
    objs, touched = [], set()
    for d in range(days):
        for k in range(lakes):
            if (d + k) % 7 == 0:                                # weekly recompute, staggered
                write(objs, f"baselines-archive/L{k}/v{d}.json", d)
                write(objs, f"baselines/L{k}/latest.json", d)
            write(objs, f"history/L{k}/daily.csv", d) if k < 3 else None   # a few daily history writers
            if d == 0: write(objs, f"presence/L{k}.json", d)
        run_lifecycle(objs, d, touched)
        if d >= 8:
            live_latest = [o.name for o in objs if o.live and o.name.endswith("/latest.json")]
            assert len(live_latest) == lakes and len(set(live_latest)) == lakes, f"day {d}: latest.json missing"
    assert all(n.startswith(("baselines/", "baselines-archive/")) for n in touched), "a rule touched an out-of-scope object"
    arch = [o for o in objs if o.name.startswith("baselines-archive/")]
    return dict(lakes=lakes, days=days, live_latest=lakes, archive_objects_total=len(arch),
                archive_live=sum(o.live for o in arch), max_archive_age_days=max(days - 1 - o.born for o in arch if o.live),
                history_untouched=sum(1 for o in objs if o.name.startswith("history/")),
                latest_noncurrent_left=sum(1 for o in objs if o.name.endswith("/latest.json") and not o.live))

def real_listing(path, horizon=400):
    items = json.load(open(path))
    today = dt.date(2026, 10, 13)
    objs = []
    for it in items:
        m = it.get("metadata")
        if not m: continue
        born = (dt.datetime.fromisoformat(m["timeCreated"].replace("Z", "+00:00")).date() - today).days
        o = Obj(m["name"], born, live=not m.get("timeDeleted"))
        if not o.live: o.nc_since = (dt.datetime.fromisoformat(m["timeDeleted"].replace("Z", "+00:00")).date() - today).days
        objs.append(o)
    before = {(o.name, o.born, o.live) for o in objs}
    touched = set()
    for d in range(0, horizon):
        run_lifecycle(objs, d, touched)
    after = {(o.name, o.born, o.live) for o in objs}
    changed = sorted(before ^ after)
    return dict(objects=len(before), touched=sorted(touched), changed=changed,
                protected_prefixes_intact=all(any(a[0] == b[0] and a[1] == b[1] and a[2] == b[2] for a in after)
                                              for b in before if not b[0].startswith(("baselines/", "baselines-archive/"))),
                current_layout_baselines_intact=all(b in after for b in before if b[0].startswith("baselines/")))

if __name__ == "__main__":
    print(json.dumps(fleet_sim(5), indent=1)); print(json.dumps(fleet_sim(315), indent=1))
    if len(sys.argv) > 1: print(json.dumps(real_listing(sys.argv[1]), indent=1))
