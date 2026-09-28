"""Clarity Fusion Stage 5: check a deployed Current Clarity revision against itself.

Reads the revision's lake summary and composite, then picks real cells of
every kind (direct / filled / grass / none x each evidence level that occurs,
and the named creeks) and asks the tap endpoint about each. The map and the
tap must agree: the API's level, confidence and magnitudeSupported for a
cell must equal the summary table's entry for that cell's region and key.
Also times the routes (warm), and the composite over a throttled link.

usage: python3 current_cloud_check.py BASE_URL OUT.json [--lake Guntersville|AL]
"""
import sys, json, gzip, math, time, random, subprocess, urllib.request, urllib.parse

BASE, OUT = sys.argv[1].rstrip("/"), sys.argv[2]
LAKE = sys.argv[sys.argv.index("--lake") + 1] if "--lake" in sys.argv else "Guntersville|AL"
Q = urllib.parse.quote(LAKE, safe="")
KEYS = ["direct", "filled<=500", "filled<=5000", "filled>5000", "grass<=5000", "grass>5000", "none"]
NAMED = {"town-creek-marshall": "Town Creek", "south-sauty-creek": "South Sauty", "browns-creek": "Browns Creek"}


def get(path, headers=None):
    req = urllib.request.Request(BASE + path, headers=headers or {})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
            return r.status, dict(r.headers), body, time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(), time.time() - t0


def varints(b):
    out, x, shift = [], 0, 0
    for c in b:
        x |= (c & 0x7F) << shift
        if c & 0x80:
            shift += 7
        else:
            out.append(x); x, shift = 0, 0
    return out


def decode(sccc):
    u32 = lambda o: int.from_bytes(sccc[o:o + 4], "little")
    assert sccc[:4] == b"SCCC" and u32(4) == 1
    w, h, n, ml = u32(8), u32(12), u32(16), u32(24)
    o = 28
    runs = varints(sccc[o:o + ml]); o += ml
    value, code, dist, region = (sccc[o + k * n:o + (k + 1) * n] for k in range(4))
    o += 4 * n
    zone = [int.from_bytes(sccc[o + 2 * i:o + 2 * i + 2], "little", signed=True) for i in range(n)]
    scene = sccc[o + 2 * n:o + 3 * n]
    pos, inw, at, spans = 0, False, 0, []      # (row, col, len, at)
    for r in runs:
        if inw:
            p, left = pos, r
            while left > 0:
                row, col = divmod(p, w)
                take = min(left, w - col)
                spans.append((row, col, take, at)); at += take; p += take; left -= take
        pos += r; inw = not inw
    assert at == n
    return dict(w=w, h=h, n=n, value=value, code=code, dist=dist, region=region, zone=zone, scene=scene, spans=spans)


def cell_ll(c, i, corners):
    for row, col, ln, at in c["spans"]:
        if at <= i < at + ln:
            col2 = col + (i - at)
            R = 6378137
            l, r = math.radians(corners[0][0]) * R, math.radians(corners[2][0]) * R
            t = math.log(math.tan(math.pi / 4 + math.radians(corners[0][1]) / 2)) * R
            b = math.log(math.tan(math.pi / 4 + math.radians(corners[2][1]) / 2)) * R
            x = l + (col2 + 0.5) / c["w"] * (r - l)
            y = t - (row + 0.5) / c["h"] * (t - b)
            return math.degrees(math.atan(math.sinh(y / R))), math.degrees(x / R)
    return None


def key_of(code, dist, has_scene):
    if not has_scene:
        return 6
    d = None if dist == 254 else (0 if dist == 0 else (dist - 1) * 100)
    if code == 255:
        return 0
    if code in (1, 2):
        dd = math.inf if d is None else d
        return 1 if dd <= 500 else 2 if dd <= 5000 else 3
    if code == 3:
        dd = math.inf if d is None else d
        return 4 if dd <= 5000 else 5
    return 6


report = {"base": BASE, "lake": LAKE, "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "checks": [], "timings": {}}
def check(name, ok, **info):
    report["checks"].append({"check": name, "pass": bool(ok), **info})
    print(("✓ " if ok else "✗ ") + name + ("  " + json.dumps(info)[:220] if info else ""))

s, _, body, dt = get("/health"); check("health", s == 200, seconds=round(dt, 3))
s, hd, body, dt = get(f"/clarity/current/lake?lake={Q}")
lake = json.loads(body) if s == 200 else {}
check("lake summary", s == 200 and lake.get("schema") == "current-clarity-lake-v1", seconds=round(dt, 3))
check("prepared world, current", lake.get("freshness") == "current", freshness=lake.get("freshness"), preparedAt=lake.get("preparedAt"))
check("two user-facing tiers", (lake.get("confidenceLabels") or {}).get("high") == "Moderate")
ov = lake.get("overview") or {}
check("overview present", bool(ov.get("headline")), headline=ov.get("headline"), supported=ov.get("supportedPct"),
      changed=ov.get("changedPct"), unsupported=ov.get("unsupportedPct"), grass=ov.get("grassPct"))
report["overview"] = ov
report["scenes"] = lake.get("scenes")
report["regions"] = [{k: r.get(k) for k in ("id", "name", "sceneIndex", "runoffState", "hydrologicCap", "catchmentCompleteness", "flowProvenance", "summary")} for r in lake.get("regions", [])]

path = lake["cells"]["path"]
s, hd, gz, dt = get(path, {"Accept-Encoding": "gzip"})
enc = {k.lower(): v for k, v in hd.items()}
check("composite as gzip", s == 200 and enc.get("content-encoding") == "gzip", bytes=len(gz), etag=enc.get("etag"), seconds=round(dt, 3))
sccc = gzip.decompress(gz) if enc.get("content-encoding") == "gzip" else gz
s2, hd2, _, dt2 = get(path, {"Accept-Encoding": "gzip", "If-None-Match": enc.get("etag", "")})
check("revalidation 304", s2 == 304, seconds=round(dt2, 3))
s3, hd3, ident, dt3 = get(path, {"Accept-Encoding": "identity"})
check("identity form still served", s3 == 200 and ident == sccc, bytes=len(ident), seconds=round(dt3, 3))
c = decode(sccc)
check("composite matches the index", c["n"] == lake["cells"]["count"], cells=c["n"])

# cells by (region, key) → the table's outcome
table, regions = lake["outcomes"], lake["regions"]
rid = {r["index"]: r["id"] for r in regions}
by_outcome = {}
named = {k: [] for k in NAMED}
for i in range(c["n"]):
    r = c["region"][i]
    k = key_of(c["code"][i], c["dist"][i], c["scene"][i] != 255)
    if r >= len(table):
        continue
    o = table[r][k]
    tag = (KEYS[k], o["level"], o["confidence"], o["magnitudeSupported"])
    by_outcome.setdefault(tag, []).append(i)
    if rid.get(r) in named:
        named[rid[r]].append(i)
rng = random.Random(7)
samples = []
for tag, cells in sorted(by_outcome.items()):
    for i in rng.sample(cells, min(3, len(cells))):
        samples.append((f"{tag[0]} → {tag[1]}/{tag[2]}", i, tag))
for rid_, cells in named.items():
    if cells:
        i = rng.choice(cells)
        r, k = c["region"][i], key_of(c["code"][i], c["dist"][i], c["scene"][i] != 255)
        o = table[r][k]
        samples.append((f"{NAMED[rid_]} ({KEYS[k]})", i, (KEYS[k], o["level"], o["confidence"], o["magnitudeSupported"])))
report["cellKinds"] = {f"{a}|{b}|{c_}|{d}": len(v) for (a, b, c_, d), v in by_outcome.items()}

points, agree, times = [], 0, []
for name, i, tag in samples:
    lat, lon = cell_ll(c, i, lake["cells"]["cornersLonLat"])
    s, _, body, dt = get(f"/clarity/current?lake={Q}&lat={lat:.6f}&lon={lon:.6f}")
    times.append(dt)
    e = json.loads(body) if s == 200 else {}
    same = (e.get("evidenceLevel"), e.get("confidence"), e.get("magnitudeSupported")) == (tag[1], tag[2], tag[3])
    agree += same
    if tag[0].startswith("grass"):
        ok = e.get("magnitudeSupported") is False and e.get("centralFt") is None and e.get("lastSupported") is None
        check(f"grass bed has no number: {name}", ok, value=e.get("display", {}).get("valueText"))
    if tag[1] == "changedHistorical":
        check(f"E hides the number: {name}", e.get("centralFt") is None and e.get("lastSupported") is not None,
              value=e.get("display", {}).get("valueText"))
    if e.get("display", {}).get("confidenceText") == "High":
        check(f"no card reads High: {name}", False)
    points.append({"name": name, "cell": i, "lat": round(lat, 6), "lon": round(lon, 6), "table": list(tag),
                   "api": [e.get("evidenceLevel"), e.get("confidence"), e.get("magnitudeSupported")],
                   "valueText": e.get("display", {}).get("valueText"), "rangeText": e.get("display", {}).get("rangeText"),
                   "confidenceText": e.get("display", {}).get("confidenceText"),
                   "evidenceText": e.get("display", {}).get("evidenceText"), "agree": same, "seconds": round(dt, 3)})
check("map and tap agree on every sampled cell", agree == len(samples), agreed=agree, of=len(samples))
report["points"] = points

for name, lat, lon, want in [("land (Guntersville town)", 34.3585, -86.2945, False), ("outside the lake (Huntsville)", 34.73, -86.59, False)]:
    s, _, body, dt = get(f"/clarity/current?lake={Q}&lat={lat}&lon={lon}")
    e = json.loads(body) if s == 200 else {}
    check(f"no number on {name}", s == 200 and e.get("magnitudeSupported") is False and e.get("centralFt") is None)

# change since a report hour
since = time.strftime("%Y-%m-%dT%H:00:00Z", time.gmtime(time.time() - 3 * 3600))
s, _, body, dt = get(f"/clarity/current/change?lake={Q}&region=town-creek-marshall&since={since}")
check("change since a report (prepared)", s == 200, state=(json.loads(body).get("state") if s == 200 else None), seconds=round(dt, 3))

# warm timings
def warm(path, headers=None, n=8):
    ts = [get(path, headers)[3] for _ in range(n)]
    ts.sort(); return {"p50": round(ts[len(ts) // 2], 3), "max": round(ts[-1], 3)}
report["timings"]["lakeWarm"] = warm(f"/clarity/current/lake?lake={Q}")
report["timings"]["cellsGzipWarm"] = warm(path, {"Accept-Encoding": "gzip"})
report["timings"]["cells304Warm"] = warm(path, {"Accept-Encoding": "gzip", "If-None-Match": enc.get("etag", "")})
times.sort(); report["timings"]["pointWarm"] = {"p50": round(times[len(times) // 2], 3), "max": round(times[-1], 3), "n": len(times)}
# the composite over a ~10 Mbit/s link (curl --limit-rate), gzip and identity
for label, hdr in (("cellsGzip10Mbps", "Accept-Encoding: gzip"), ("cellsIdentity10Mbps", "Accept-Encoding: identity")):
    out = subprocess.run(["curl", "-s", "-o", "/dev/null", "-H", hdr, "--limit-rate", "1250k",
                          "-w", "%{time_connect} %{time_starttransfer} %{time_total} %{size_download}", BASE + path],
                         capture_output=True, text=True).stdout.split()
    report["timings"][label] = {"connect": float(out[0]), "firstByte": float(out[1]), "total": float(out[2]), "bytes": int(out[3])}
print(json.dumps(report["timings"], indent=1))
report["passed"] = all(x["pass"] for x in report["checks"])
json.dump(report, open(OUT, "w"), indent=1)
print("ALL PASSED" if report["passed"] else "FAILURES")
