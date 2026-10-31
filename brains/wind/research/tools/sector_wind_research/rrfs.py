"""RRFS / REFS prospective archive (Score Acceleration §15–19). RESEARCH ONLY: never read by the Candidate or production.

  python -m sector_wind_research.rrfs discover          # where (if anywhere) operational RRFS/REFS cycles are published right now
  python -m sector_wind_research.rrfs collect           # archive any new synoptic cycle (00/06/12/18Z) found; no-op until published
  python -m sector_wind_research.rrfs backfill --start 2026-08-12 [--end ISO]   # cycles missed since go-live: point samples only, rows flagged backfill
  python -m sector_wind_research.rrfs selftest URL      # decode one prslev conus GRIB2 (e.g. a retro file) at the 12 points

Forecasts are stored as issued (init, valid, lead, retrievedAt, decoder); nothing is reconstructed retrospectively. A BACKFILL reads cycles that were
published but missed (the collector looked in the wrong bucket until 2026-10-31): its rows carry `backfill: true`, `asIssued: false` and the real retrievedAt,
so an evaluation includes or excludes them by a pre-registered rule, never after seeing results.

Where operational cycles live (NODD `noaa-rrfs-ops-pds`, operational since 2026-08-12; recorded listing in tests/fixtures): deterministic RRFS under
`rrfs.YYYYMMDD/HH/`, REFS members under `rrfsens.YYYYMMDD/HH/mNNN/`. The 10 m U/V and surface GUST are in the `2dfld` files (`prslev` carries pressure
levels only, e.g. 10 mb), and member .idx lines carry an `ENS=+N` tail.
Deterministic RRFS: the 10 m U/V and surface GUST GRIB2 messages are kept raw (immutable, sha256) + point samples.
REFS members: point samples + per-message sha256 only (volume); ensemble mean / spread / P(>15 mph) computed from members.
Grid-relative U/V are rotated to earth-relative (Lambert) before any direction is computed."""
from __future__ import annotations

import argparse, gzip, hashlib, json, math, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

from sector_wind.grib import decode, fetch, read_idx, find, grid, rotate_to_earth, speed_dir_from_uv
from sector_wind_research.provider_bakeoff import POINTS, ROOT, iso, sample, sealed

DECODER = "rrfs 1.1.0"
LEADS = (1, 3, 6, 12, 18)
OPS = "https://noaa-rrfs-ops-pds.s3.amazonaws.com"         # operational NODD bucket (RRFS/REFS operational since 2026-08-12)
S3 = "https://noaa-rrfs-pds.s3.amazonaws.com"              # pre-operational bucket, kept as a fallback
NOMADS = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rrfs/prod"
GO_LIVE = datetime(2026, 8, 12, tzinfo=timezone.utc)       # first rrfs./refs. day in the operational bucket
# operational layout: 10 m wind + gust live in 2dfld (prslev has pressure levels only); members in rrfsens.*/HH/mNNN/
DET = re.compile(r"rrfs\.t(\d\d)z\.2dfld\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
ENS = re.compile(r"rrfs\.t(\d\d)z\.m(\d{3})\.2dfldnomads\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
# pre-operational layout (fallback bucket only)
DET_PDS = re.compile(r"rrfs\.t(\d\d)z\.prslev\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
ENS_PDS = re.compile(r"(?:refs|rrfs)\.t(\d\d)z\.(?:m|mem)(\d{2,3})\.prslev\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
SOURCES = [   # (bucket, [(prefix template, det regex, ens regex)]); the first bucket with any cycle file wins; within it every prefix is merged
    (OPS, [("rrfs.{d}/{h:02d}/", DET, None), ("rrfsens.{d}/{h:02d}/", None, ENS)]),
    (S3, [(p, DET_PDS, ENS_PDS) for p in ("rrfs.{d}/{h:02d}/", "rrfs_a/rrfs.{d}/{h:02d}/", "prod/rrfs.{d}/{h:02d}/")]),
]
PREFIXES = [p for _b, ps in SOURCES for p, _d, _e in ps]
ENS_TAIL = re.compile(r"ENS=[+-]\d+")
MPH = 0.44704
_NEAR = {}


def _s3_keys(prefix, bucket=OPS):
    keys, tok = [], None
    while True:
        q = f"{bucket}/?list-type=2&max-keys=1000&prefix={prefix}" + (f"&continuation-token={urllib.request.quote(tok)}" if tok else "")
        body = urllib.request.urlopen(q, timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+)</Key>", body)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not m:
            return keys
        tok = m.group(1)


def discover(init):
    """Return {"det": {lead: url}, "ens": {member: {lead: url}}, "where": [prefixes]} for one init, or None."""
    for bucket, prefixes in SOURCES:
        det, ens, where = {}, {}, []
        for p, det_rx, ens_rx in prefixes:
            pre = p.format(d=f"{init:%Y%m%d}", h=init.hour)
            try:
                keys = [k for k in _s3_keys(pre, bucket) if k.endswith(".grib2")]
            except Exception:
                keys = []
            n = len(det) + len(ens)
            for k in keys:
                base = k.rsplit("/", 1)[-1]
                if det_rx and (m := det_rx.search(base)) and int(m.group(1)) == init.hour:
                    det[int(m.group(2))] = f"{bucket}/{k}"
                elif ens_rx and (m := ens_rx.search(base)) and int(m.group(1)) == init.hour:
                    ens.setdefault(int(m.group(2)), {})[int(m.group(3))] = f"{bucket}/{k}"
            if len(det) + len(ens) > n:
                where.append(f"{bucket}/{pre}")
        if det or ens:
            return {"det": det, "ens": ens, "where": where}
    try:   # NOMADS fallback (may be unreachable from some networks)
        html = urllib.request.urlopen(f"{NOMADS}/rrfs.{init:%Y%m%d}/{init:%H}/", timeout=30).read().decode()
        det = {int(m.group(2)): f"{NOMADS}/rrfs.{init:%Y%m%d}/{init:%H}/{m.group(0)}" for m in DET.finditer(html) if int(m.group(1)) == init.hour}
        if det:
            return {"det": det, "ens": {}, "where": NOMADS}
    except Exception:
        pass
    return None


def _nearest(gkey):
    if gkey not in _NEAR:
        lat, lon = grid(gkey); c = math.cos(math.radians(35))
        _NEAR[gkey] = {p: int(np.argmin((lat - la) ** 2 + ((lon - lo) * c) ** 2)) for p, (la, lo) in POINTS.items()}
    return _NEAR[gkey]


def _entry(ent, var, level, step):
    """The deterministic message (empty tail) or, in an ensemble member's file, the one whose tail is ENS=+N."""
    return find(ent, var, level, "", step) or next((x for x in ent if x.var == var and x.level == level and ENS_TAIL.fullmatch(x.tail or "") and step in x.step), None)


def sample_file(url, lead):
    """Decode 10 m U/V (+ GUST) from one GRIB2 via .idx byte ranges; earth-relative; nearest cell at each point."""
    ent = read_idx(url)
    step = f"{lead} hour fcst"
    def msg(var, level):
        e = _entry(ent, var, level, step)
        if e is None:
            return None, None
        b = fetch(url, (e.start, e.end)); return decode(b), b
    (u, ub), (v, vb) = msg("UGRD", "10 m above ground"), msg("VGRD", "10 m above ground")
    g, gb = msg("GUST", "surface")
    if u is None or v is None:
        raise RuntimeError(f"no 10 m U/V in {url}")
    uu, vv = u.values, v.values
    if u.uv_relative_to_grid:
        lat, lon = grid(u.grid_key)
        uu, vv = rotate_to_earth(uu, vv, lon, u.lov_deg, u.latin1_deg)
    spd, dr = speed_dir_from_uv(uu, vv)
    near = _nearest(u.grid_key)
    pts = {p: {"speedMS": float(spd[i]), "dirFromDeg": float(dr[i]), "u": float(uu[i]), "v": float(vv[i]),
               "gustMS": float(g.values[i]) if g is not None and not g.missing[i] else None, "cell": i} for p, i in near.items()}
    raw = {"u": ub, "v": vb, "gust": gb}
    return pts, raw, {"gridKey": u.grid_key, "uvRelativeToGrid": u.uv_relative_to_grid}


def _save_raw(init, name, blob):
    d = os.path.join(ROOT, "raw", "rrfs", f"{init:%Y%m%d%H}"); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, name + ".grib2.gz")
    if not os.path.exists(p):
        open(p, "wb").write(gzip.compress(blob)); os.chmod(p, 0o444)
    return hashlib.sha256(blob).hexdigest()


def _ledger_done():
    ledger = os.path.join(ROOT, "rrfs_ledger.jsonl")
    if not os.path.exists(ledger):
        return set()
    return {json.loads(l)["init"] for l in open(ledger) if '"status": "archived"' in l}


def _cycle_rows(init, found, now, *, keep_raw=True):
    """Point samples for one cycle: deterministic RRFS rows and REFS member-derived rows at LEADS. keep_raw=False (backfill) stores no GRIB messages."""
    rows = []
    for L in LEADS:
        if L in found["det"]:
            pts, raw, meta = sample_file(found["det"][L], L)
            shas = {k: (_save_raw(init, f"det_f{L:03d}_{k}", b) if keep_raw else hashlib.sha256(b).hexdigest()) for k, b in raw.items() if b}
            vt = init + timedelta(hours=L)
            rows += [sample("rrfs", "RRFS deterministic 3 km (operational)", "forecast", p, init, now, vt, x["speedMS"], x["dirFromDeg"], x["gustMS"],
                            {"url": found["det"][L], "sha256": shas, **meta, "decoder": DECODER}, u=x["u"], v=x["v"]) for p, x in pts.items()]
        mem = {}
        for m, leads in sorted(found["ens"].items()):
            if L in leads:
                pts, raw, meta = sample_file(leads[L], L)
                mem[m] = (pts, {k: hashlib.sha256(b).hexdigest() for k, b in raw.items() if b})
        if mem:
            vt = init + timedelta(hours=L)
            for p in POINTS:
                s = np.array([x[0][p]["speedMS"] for x in mem.values()]); uu = np.array([x[0][p]["u"] for x in mem.values()]); vv = np.array([x[0][p]["v"] for x in mem.values()])
                ms, md = speed_dir_from_uv(np.array([uu.mean()]), np.array([vv.mean()]))
                rows.append(sample("refs", f"REFS ensemble mean ({len(mem)} members)", "forecast", p, init, now, vt, float(s.mean()), float(md[0]), None,
                                   {"members": {str(k): {"speedMS": v_[0][p]["speedMS"], "dirFromDeg": v_[0][p]["dirFromDeg"], "gustMS": v_[0][p]["gustMS"], "sha256": v_[1]} for k, v_ in mem.items()},
                                    "decoder": DECODER}, spread={"speedSD": float(s.std(ddof=1)) if len(s) > 1 else None},
                                   probabilities={"P(>15mph)": float((s >= 15 * MPH).mean())}))
    return rows


def _append(path, records):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def collect(now=None):
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    ledger = os.path.join(ROOT, "rrfs_ledger.jsonl"); done = _ledger_done()
    out = []
    for back in range(0, 13):
        init = (now - timedelta(hours=back)).replace(minute=0, second=0)
        if init.hour % 6 or iso(init) in done:
            continue
        found = discover(init)
        status = {"init": iso(init), "checkedAt": iso(now), "status": "not published" if not found else "archived", "where": found and found["where"]}
        if found:
            rows = _cycle_rows(init, found, now)
            _append(os.path.join(ROOT, "normalized", f"{now:%Y%m%d}.jsonl"), rows)
            status["samples"] = len(rows)
        _append(ledger, [status])
        out.append(status)
    return out


def backfill(start, end=None, now=None, run_id=None):
    """Archive every synoptic cycle in [start, end] that the ledger does not already hold as archived. Point samples only (no GRIB kept);
    every row is flagged `backfill: true, asIssued: false` with the real retrievedAt; the ledger entry says `backfill: true`. Idempotent: re-running
    skips archived cycles. Rows go to normalized/rrfs-backfill-<runId>.jsonl (one file per run, never mixed into a live day file)."""
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    end = min(end or now, now)
    run_id = run_id or f"{now:%Y%m%dT%H%M%SZ}"
    ledger, done = os.path.join(ROOT, "rrfs_ledger.jsonl"), _ledger_done()
    rows_path = os.path.join(ROOT, "normalized", f"rrfs-backfill-{run_id}.jsonl")
    init = start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=(-start.hour) % 6)
    out = []
    while init <= end:
        if iso(init) not in done:
            t = datetime.now(timezone.utc).replace(microsecond=0)
            found = discover(init)
            status = {"init": iso(init), "checkedAt": iso(t), "status": "not published" if not found else "archived", "where": found and found["where"],
                      "backfill": True, "backfillRunId": run_id}
            if found:
                try:
                    rows = _cycle_rows(init, found, t, keep_raw=False)
                except Exception as e:                                          # one bad cycle never stops the run; it stays not archived and is retried next run
                    status.update(status="error", error=repr(e)[:300])
                    rows = []
                for r in rows:
                    r.update(backfill=True, asIssued=False, backfillRunId=run_id)
                _append(rows_path, rows)
                status["samples"] = len(rows)
                status["members"] = len(found["ens"])
            _append(ledger, [status])
            out.append(status)
            print(json.dumps({k: status.get(k) for k in ("init", "status", "samples", "members")}), flush=True)
        init += timedelta(hours=6)
    return out


def selftest(url):
    lead = int(re.search(r"f(\d{3})", url).group(1))
    pts, raw, meta = sample_file(url, lead)
    print(meta)
    for p, x in pts.items():
        print(f"{p:<20} {x['speedMS']:6.2f} m/s from {x['dirFromDeg']:5.0f}°  gust {x['gustMS']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["discover", "collect", "backfill", "selftest"]); ap.add_argument("url", nargs="?")
    ap.add_argument("--start"); ap.add_argument("--end"); a = ap.parse_args()
    if a.cmd == "discover":
        now = datetime.now(timezone.utc)
        for back in range(0, 25, 6):
            t = (now - timedelta(hours=back)).replace(minute=0, second=0, microsecond=0); t = t - timedelta(hours=t.hour % 6)
            print(iso(t), discover(t) or "not published (noaa-rrfs-ops-pds rrfs.*/rrfsens.*, noaa-rrfs-pds fallback, NOMADS prod)")
    elif a.cmd == "collect":
        for s in collect():
            print(s)
    elif a.cmd == "backfill":
        parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=timezone.utc) if s else None
        res = backfill(parse(a.start) or GO_LIVE, parse(a.end))
        print(json.dumps({"cycles": len(res), "archived": sum(r["status"] == "archived" for r in res), "notPublished": sum(r["status"] == "not published" for r in res),
                          "errors": sum(r["status"] == "error" for r in res), "samples": sum(r.get("samples") or 0 for r in res)}))
    else:
        selftest(a.url)
