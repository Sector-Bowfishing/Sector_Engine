"""RRFS / REFS prospective archive (Score Acceleration §15–19). RESEARCH ONLY: never read by the Candidate or production.

  python -m sector_wind_research.rrfs discover          # where (if anywhere) operational RRFS/REFS cycles are published right now
  python -m sector_wind_research.rrfs collect           # archive any new synoptic cycle (00/06/12/18Z) found; no-op until published
  python -m sector_wind_research.rrfs selftest URL      # decode one prslev conus GRIB2 (e.g. a retro file) at the 12 points

Forecasts are stored as issued (init, valid, lead, retrievedAt, decoder); nothing is reconstructed retrospectively.
Deterministic RRFS: the 10 m U/V and surface GUST GRIB2 messages are kept raw (immutable, sha256) + point samples.
REFS members: point samples + per-message sha256 only (volume); ensemble mean / spread / P(>15 mph) computed from members.
Grid-relative U/V are rotated to earth-relative (Lambert) before any direction is computed."""
from __future__ import annotations

import argparse, gzip, hashlib, json, math, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

from sector_wind.grib import decode, fetch, read_idx, find, grid, rotate_to_earth, speed_dir_from_uv
from sector_wind_research.provider_bakeoff import POINTS, ROOT, iso, sample, sealed

DECODER = "rrfs 1.0.0"
LEADS = (1, 3, 6, 12, 18)
S3 = "https://noaa-rrfs-pds.s3.amazonaws.com"
NOMADS = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/rrfs/prod"
PREFIXES = ["rrfs.{d}/{h:02d}/", "rrfs_a/rrfs.{d}/{h:02d}/", "prod/rrfs.{d}/{h:02d}/"]      # NODD layouts seen / expected
DET = re.compile(r"rrfs\.t(\d\d)z\.prslev\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
ENS = re.compile(r"(?:refs|rrfs)\.t(\d\d)z\.(?:m|mem)(\d{2,3})\.prslev\.(?:\d+km\.)?f(\d{3})\.conus\.grib2$")
MPH = 0.44704
_NEAR = {}


def _s3_keys(prefix):
    keys, tok = [], None
    while True:
        q = f"{S3}/?list-type=2&max-keys=1000&prefix={prefix}" + (f"&continuation-token={urllib.request.quote(tok)}" if tok else "")
        body = urllib.request.urlopen(q, timeout=60).read().decode()
        keys += re.findall(r"<Key>([^<]+)</Key>", body)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", body)
        if not m:
            return keys
        tok = m.group(1)


def discover(init):
    """Return {"det": {lead: url}, "ens": {member: {lead: url}}, "where": prefix} for one init, or None."""
    for p in PREFIXES:
        pre = p.format(d=f"{init:%Y%m%d}", h=init.hour)
        try:
            keys = [k for k in _s3_keys(pre) if k.endswith(".grib2")]
        except Exception:
            keys = []
        if not keys:
            continue
        det, ens = {}, {}
        for k in keys:
            base = k.rsplit("/", 1)[-1]
            if (m := DET.search(base)) and int(m.group(1)) == init.hour:
                det[int(m.group(2))] = f"{S3}/{k}"
            elif (m := ENS.search(base)) and int(m.group(1)) == init.hour:
                ens.setdefault(int(m.group(2)), {})[int(m.group(3))] = f"{S3}/{k}"
        if det or ens:
            return {"det": det, "ens": ens, "where": f"{S3}/{pre}"}
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


def sample_file(url, lead):
    """Decode 10 m U/V (+ GUST) from one GRIB2 via .idx byte ranges; earth-relative; nearest cell at each point."""
    ent = read_idx(url)
    step = f"{lead} hour fcst"
    def msg(var, level):
        e = find(ent, var, level, "", step)
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


def collect(now=None):
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    ledger = os.path.join(ROOT, "rrfs_ledger.jsonl"); done = set()
    if os.path.exists(ledger):
        done = {json.loads(l)["init"] for l in open(ledger) if '"status": "archived"' in l}
    out = []
    for back in range(0, 13):
        init = (now - timedelta(hours=back)).replace(minute=0, second=0)
        if init.hour % 6 or iso(init) in done:
            continue
        found = discover(init)
        status = {"init": iso(init), "checkedAt": iso(now), "status": "not published" if not found else "archived", "where": found and found["where"]}
        if found:
            rows = []
            for L in LEADS:
                if L in found["det"]:
                    pts, raw, meta = sample_file(found["det"][L], L)
                    shas = {k: _save_raw(init, f"det_f{L:03d}_{k}", b) for k, b in raw.items() if b}
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
            d = os.path.join(ROOT, "normalized"); os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, f"{now:%Y%m%d}.jsonl"), "a") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            status["samples"] = len(rows)
        with open(ledger, "a") as f:
            f.write(json.dumps(status) + "\n")
        out.append(status)
    return out


def selftest(url):
    lead = int(re.search(r"f(\d{3})", url).group(1))
    pts, raw, meta = sample_file(url, lead)
    print(meta)
    for p, x in pts.items():
        print(f"{p:<20} {x['speedMS']:6.2f} m/s from {x['dirFromDeg']:5.0f}°  gust {x['gustMS']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["discover", "collect", "selftest"]); ap.add_argument("url", nargs="?"); a = ap.parse_args()
    if a.cmd == "discover":
        now = datetime.now(timezone.utc)
        for back in range(0, 25, 6):
            t = (now - timedelta(hours=back)).replace(minute=0, second=0, microsecond=0); t = t - timedelta(hours=t.hour % 6)
            print(iso(t), discover(t) or "not published (NODD prefixes rrfs.*, rrfs_a/rrfs.*, prod/rrfs.*; NOMADS prod)")
    elif a.cmd == "collect":
        for s in collect():
            print(s)
    else:
        selftest(a.url)
