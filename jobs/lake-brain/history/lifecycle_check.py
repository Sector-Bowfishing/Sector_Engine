#!/usr/bin/env python3
"""Model-check of lake_brain_bucket_lifecycle_proposed.json against GCS lifecycle semantics for a VERSIONED bucket.

Semantics modelled (GCS docs, https://docs.cloud.google.com/storage/docs/lifecycle): a rule fires when ALL its conditions match;
matchesPrefix is a literal prefix list (OR inside the list); `Delete` on a LIVE object of a versioned bucket only makes it NONCURRENT;
`Delete` on a NONCURRENT object removes it for good; `age` = days since that version was created (age 0 is satisfied at the next
midnight UTC); `daysSinceNoncurrentTime` = days since it became noncurrent; `isLive:false` matches noncurrent versions only.

Checks: (1) a fleet simulation of the pointer layout (baselines/<key>/latest.json overwritten in place, immutable
baselines-archive/<key>/<name>.json written weekly when history changed, stalled lakes refreshed every 45 days): every lake's pointer is
live every day and the archive object it names is live every day; only baselines/, baselines-archive/ and history/ NONCURRENT versions are
ever deleted; (2) the job stopped for 400 days: pointers survive, the named archive object is retired after 90 days (the dangling-pointer
fallback is the Swift rebuild, tested there); (3) the real bucket listing (JSON from `gcloud storage ls -a -r --json`) with the job
stopped: nothing in predictions/, presence/, history_backup/ or any LIVE object is ever touched.
usage: lifecycle_check.py [bucket_listing.json]
"""
import json, os, sys, datetime as dt
HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "lake_brain_bucket_lifecycle_proposed.json")))["rule"]

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

REFRESH_DAYS = 45          # LakeBaselineStore.refreshDays

def fleet_sim(lakes=621, days=400, stalled_every=10, stop_at=None):
    """Weekly recompute (staggered). Lakes with k % stalled_every == 0 stall after day 20 (history stops advancing)."""
    objs, touched = [], set()
    target, refreshed = {}, {}
    for d in range(days):
        for k in range(lakes):
            if stop_at is not None and d >= stop_at: break
            stalled = (k % stalled_every == 0) and d > 20
            if (d + k) % 7 == 0 and not stalled:                       # weekly recompute, inputs changed -> new object + pointer move
                name = f"baselines-archive/L{k}/doy15_v2_{d}.json"
                write(objs, name, d); write(objs, f"baselines/L{k}/latest.json", d)
                target[k], refreshed[k] = name, d
            elif stalled and k in target and d - refreshed[k] >= REFRESH_DAYS:   # same bytes, same name, new generation
                write(objs, target[k], d); write(objs, f"baselines/L{k}/latest.json", d)
                refreshed[k] = d
            if k < 3: write(objs, f"history/L{k}/daily.csv", d)         # a few daily history writers
            if d == 0: write(objs, f"presence/L{k}.json", d)
        run_lifecycle(objs, d, touched)
        if d >= 8 and stop_at is None:
            live = {o.name for o in objs if o.live}
            for k in range(lakes):
                if (d + k) % 7 == 0 or k in target:
                    assert f"baselines/L{k}/latest.json" in live, f"day {d}: pointer L{k} missing"
                    assert target[k] in live, f"day {d}: archive object named by pointer L{k} was retired: {target[k]}"
    assert all(n.startswith(("baselines/", "baselines-archive/", "history/")) for n in touched), "a rule touched an out-of-scope object"
    arch = [o for o in objs if o.name.startswith("baselines-archive/")]
    ptr_live = sum(1 for o in objs if o.live and o.name.endswith("/latest.json"))
    return dict(lakes=lakes, days=days, stop_at=stop_at, pointers_live=ptr_live,
                archive_live=sum(o.live for o in arch), archive_noncurrent=sum(not o.live for o in arch),
                pointer_noncurrent_left=sum(1 for o in objs if o.name.endswith("/latest.json") and not o.live),
                history_live=sum(1 for o in objs if o.name.startswith("history/") and o.live),
                history_noncurrent_left=sum(1 for o in objs if o.name.startswith("history/") and not o.live),
                presence_untouched=sum(1 for o in objs if o.name.startswith("presence/") and o.live))

def real_listing(path, horizon=400, today=dt.date(2026, 10, 13)):
    """The real bucket listing, job stopped, lifecycle running for `horizon` days. Reports what disappears or goes noncurrent."""
    items = json.load(open(path))
    objs = []
    for it in items:
        m = it.get("metadata")
        if not m: continue
        born = (dt.datetime.fromisoformat(m["timeCreated"].replace("Z", "+00:00")).date() - today).days
        o = Obj(m["name"], born, live=not m.get("timeDeleted"))
        if not o.live: o.nc_since = (dt.datetime.fromisoformat(m["timeDeleted"].replace("Z", "+00:00")).date() - today).days
        o.gen = m.get("generation")
        objs.append(o)
    before = {(o.name, o.gen, o.live) for o in objs}
    touched = set()
    for d in range(0, horizon):
        run_lifecycle(objs, d, touched)
    after = {(o.name, o.gen, o.live) for o in objs}
    gone_or_changed = sorted(before ^ after)
    live_changed = sorted(b for b in before if b[2] and b not in after)
    removed_noncurrent = sorted(b for b in before if not b[2] and b not in after)
    return dict(objects=len(before), live_objects_changed=live_changed,
                noncurrent_removed=[(n, g) for n, g, _ in removed_noncurrent],
                noncurrent_removed_prefixes=sorted({n.split("/")[0] for n, _, _ in removed_noncurrent}),
                predictions_presence_backup_untouched=all(b in after for b in before if b[0].startswith(("predictions/", "presence/", "history_backup/"))))

if __name__ == "__main__":
    for n in (5, 196, 621): print(json.dumps(fleet_sim(n), indent=1))
    print(json.dumps(fleet_sim(196, stop_at=100), indent=1))
    if len(sys.argv) > 1: print(json.dumps(real_listing(sys.argv[1]), indent=1))
