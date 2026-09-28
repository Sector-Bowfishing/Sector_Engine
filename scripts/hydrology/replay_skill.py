"""Compare replay runs on the SAME pairs (Clarity Fusion Stage 3A, item 4).

For each replay file: the expected-vs-observed direction table, and for the
call "murkier than the scene":
  hitRate  P(observed murkier | expected murkier)
  baseRate P(observed murkier | expected same)
  pod      P(expected murkier | observed murkier)   (recall)
  pss      Peirce skill score = pod - false-alarm rate (0 = no skill, 1 = perfect)
and the authority ladder (share of next passes matching the scene, by
authority). 95% intervals: bootstrap over pass DATES (the arms of one pass
are not independent), 2,000 draws.

usage: python3 replay_skill.py <label=replay.json> ... [--arms a,b,...]
"""
import sys, json, random, collections

args = [a for a in sys.argv[1:] if not a.startswith("--")]
only = None
if "--arms" in sys.argv:
    only = set(sys.argv[sys.argv.index("--arms") + 1].split(","))
    args = [a for a in args if a != sys.argv[sys.argv.index("--arms") + 1]]
runs = {}
for a in args:
    label, path = a.split("=", 1)
    runs[label] = json.load(open(path))["pairs"]
key = lambda r: (r["arm"], r["anchor"], r["next"])
common = set.intersection(*[{key(r) for r in v} for v in runs.values()])


def metrics(rows):
    em = [r for r in rows if r["expected"] == "murkierThanPass"]
    es = [r for r in rows if r["expected"] == "sameAsPass"]
    om = [r for r in rows if r["observed"] == "murkierThanPass"]
    on = [r for r in rows if r["observed"] != "murkierThanPass"]
    hit = sum(r["observed"] == "murkierThanPass" for r in em) / len(em) if em else float("nan")
    base = sum(r["observed"] == "murkierThanPass" for r in es) / len(es) if es else float("nan")
    pod = sum(r["expected"] == "murkierThanPass" for r in om) / len(om) if om else float("nan")
    far = sum(r["expected"] == "murkierThanPass" for r in on) / len(on) if on else float("nan")
    lad = {}
    for lvl in ("high", "moderate", "low", "none"):
        x = [r for r in rows if r["authority"] == lvl]
        lad[lvl] = (len(x), sum(r["observed"] == "sameAsPass" for r in x) / len(x) if x else float("nan"))
    return {"n": len(rows), "expectedMurkier": len(em), "hitRate": hit, "baseRate": base, "pod": pod, "pss": pod - far, "ladder": lad}


def boot(rows, stat, n=2000, seed=7):
    by = collections.defaultdict(list)
    for r in rows:
        by[r["next"]].append(r)
    dates = list(by)
    rnd = random.Random(seed); vals = []
    for _ in range(n):
        s = [r for d in (rnd.choice(dates) for _ in dates) for r in by[d]]
        v = stat(metrics(s))
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


out = {}
for label, rows in runs.items():
    rows = [r for r in rows if key(r) in common and (only is None or r["arm"] in only)]
    m = metrics(rows)
    m["pssCI"] = boot(rows, lambda x: x["pss"])
    m["hitCI"] = boot(rows, lambda x: x["hitRate"])
    c = collections.Counter((r["expected"], r["observed"]) for r in rows)
    m["table"] = {e: {o: c[(e, o)] for o in ("murkierThanPass", "sameAsPass", "clearerThanPass")}
                  for e in ("murkierThanPass", "sameAsPass", "clearerThanPass", "unknown")}
    out[label] = m
    lad = " ".join(f"{k} {v[0]}:{100*v[1]:.0f}%" for k, v in m["ladder"].items())
    print(f"{label:10s} n={m['n']} expMurkier={m['expectedMurkier']} hit={100*m['hitRate']:.1f}% "
          f"[{100*m['hitCI'][0]:.0f}-{100*m['hitCI'][1]:.0f}] base={100*m['baseRate']:.1f}% "
          f"pod={100*m['pod']:.1f}% PSS={m['pss']:.3f} [{m['pssCI'][0]:.3f},{m['pssCI'][1]:.3f}] | same by authority: {lad}")
# pairs whose expectation changed between the first two runs
labels = list(runs)
if len(labels) >= 2:
    A = {key(r): r for r in runs[labels[0]]}; B = {key(r): r for r in runs[labels[1]]}
    ch = [(k, A[k]["expected"], B[k]["expected"], B[k]["observed"]) for k in common if A[k]["expected"] != B[k]["expected"]]
    cc = collections.Counter((a, b, o) for _, a, b, o in ch)
    print(f"expectation changed on {len(ch)} pairs:")
    for (a, b, o), n in cc.most_common(10):
        print(f"   {a} -> {b}: {n} (observed {o})")
json.dump(out, open("/dev/stdout", "w")) if False else None
