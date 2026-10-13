"""Shared helpers for the binding2 'se' (southeast/south-central) source scout. Read-only, polite GETs.

Pure-python Blosc(LZ4) decoder is included so the SJRWMD WISKI-Web zarr store can be read without extra packages.
"""
import csv, datetime as dt, gzip, io, json, math, os, struct, sys, time, urllib.parse
sys.path.insert(0, "/Users/mcather/Desktop/Development/Sector_Engine/research/lake-brain/binding")
from common import http_get, get_json, haversine_m, name_sim, load_directory  # noqa: E402
from providers import summarize, year_completeness, cwms_ts, FT_PER_M  # noqa: E402
import numpy as np  # noqa: E402

OUT = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding2"
CAND_F = f"{OUT}/cand/se.jsonl"
HIST_D = f"{OUT}/history"
RAW_D = f"{OUT}/raw/se"
for d in (f"{OUT}/cand", HIST_D, f"{OUT}/notes", RAW_D):
    os.makedirs(d, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
PROFILE = {l["lakeId"]: l for l in json.load(open(f"{OUT}/unbound_profile.json"))}


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def safe(k):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(k))[:150]


# --------------------------------------------------------------------------- candidate / history writers
CANDS = {}


def add_cand(lakeId, prov, origin, station, stationName, lat, lon, series, family, vdatum, pts, unit="ft", relay=False, fullPoolHint=None,
             hist=None, apiUrl="", pageUrl="", notes="", age_ref=None):
    """pts: list of (epoch_s, value in `unit`) for the live window (>= last 30 d). hist: {YYYY-MM-DD: value_ft} or None."""
    k = FT_PER_M if unit in ("m", "meter") else 1.0
    pts30 = [(t, v) for t, v in pts if v is not None and t >= NOW.timestamp() - 30 * 86400]
    sm = summarize(pts30 or pts, unit)
    if not sm.get("n"):
        print("   !! no points for", lakeId, station, series)
        return None
    histPath, histYears = None, None
    if hist:
        histPath = f"history/{safe(prov)}_{safe(station)}_{safe(series)}.csv.gz"
        with gzip.open(f"{OUT}/{histPath}", "wt", newline="") as f:
            w = csv.writer(f)
            for d in sorted(hist):
                w.writerow([d, round(hist[d], 4)])
        histYears = [int(min(hist)[:4]), int(max(hist)[:4])]
    c = dict(lakeId=lakeId, prov=prov, origin=origin, relay=relay, station=str(station), stationName=stationName, lat=lat, lon=lon, series=series,
             unit="ft", family=family, vdatum=vdatum, lastObs=sm["last_t"], ageH=max(0.0, sm["age_h"]), n30=len(pts30), medFt=sm["med_ft"], lastFt=sm["last_ft"],
             fullPoolHint=fullPoolHint, histPath=histPath, histYears=histYears, apiUrl=apiUrl, pageUrl=pageUrl, notes=notes)
    if hist:
        c["histCompleteYears"] = year_completeness(hist)["completeYears"]
    CANDS[(lakeId, prov, str(station), series)] = c
    print(f"  + {lakeId:34s} {prov:8s} {station} {series} last={c['lastFt']} ft age={c['ageH']}h n30={c['n30']} hist={histYears} cy={c.get('histCompleteYears')}")
    return c


def flushCANDS():
    with open(CAND_F, "w") as f:
        for c in CANDS.values():
            f.write(json.dumps(c) + "\n")
    print("wrote", len(CANDS), "candidates ->", CAND_F)


def daily_from_pts(pts, tz_offset_h=0):
    by = {}
    for t, v in pts:
        d = dt.datetime.fromtimestamp(t + tz_offset_h * 3600, dt.timezone.utc).strftime("%Y-%m-%d")
        by.setdefault(d, []).append(v)
    return {d: sum(v) / len(v) for d, v in by.items()}


# --------------------------------------------------------------------------- Blosc (lz4) decoder
def _lz4_block(src, out_size):
    out = bytearray()
    i, n = 0, len(src)
    while i < n:
        tok = src[i]; i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                b = src[i]; i += 1; ll += b
                if b != 255:
                    break
        out += src[i:i + ll]; i += ll
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        p = len(out) - off
        for _ in range(ml):
            out.append(out[p]); p += 1
    return bytes(out)


def blosc_decompress(buf):
    flags, typesize = buf[2], buf[3]
    nbytes, blocksize, cbytes = struct.unpack("<III", buf[4:16])
    if flags & 0x2:  # memcpyed
        return buf[16:16 + nbytes]
    shuffle = flags & 0x1
    compformat = flags >> 5
    if compformat != 1:
        raise ValueError(f"blosc: unsupported codec {compformat}")
    nblocks = (nbytes + blocksize - 1) // blocksize
    bstarts = struct.unpack(f"<{nblocks}I", buf[16:16 + 4 * nblocks])
    dont_split = bool(flags & 0x10)
    out = bytearray()
    for b in range(nblocks):
        bsize = blocksize if b < nblocks - 1 else nbytes - blocksize * (nblocks - 1)
        p = bstarts[b]
        if not dont_split and typesize <= 16 and bsize // typesize >= 128 and bsize == blocksize:
            nsplits = typesize
        else:
            nsplits = 1
        ssize = bsize // nsplits
        blk = bytearray()
        for _ in range(nsplits):
            cs = struct.unpack("<i", buf[p:p + 4])[0]; p += 4
            seg = buf[p:p + cs]; p += cs
            blk += seg if cs == ssize else _lz4_block(seg, ssize)
        if shuffle and typesize > 1:
            a = np.frombuffer(bytes(blk), dtype=np.uint8)
            nel = bsize // typesize
            rest = bsize - nel * typesize
            body = a[:nel * typesize].reshape(typesize, nel).T.reshape(-1)
            blk = bytes(body) + bytes(a[nel * typesize:])
        out += blk
    return bytes(out)


# --------------------------------------------------------------------------- SJRWMD WISKI-Web (zarr over static HTTP)
SJ = "https://mdp.sjrwmd.com/data/internet"


def sj_array(path):
    """Fetch a zarr v2 1-D/2-D array (single chunk-file set) from the SJRWMD store. Returns numpy array or None."""
    s, b = http_get(f"{SJ}/timeseries/{path}/.zarray", sleep=0.5)
    if s != 200:
        return None
    meta = json.loads(b)
    shape, chunks, dtype = meta["shape"], meta["chunks"], np.dtype(meta["dtype"])
    nd = len(shape)
    if shape[0] == 0:
        return np.zeros(shape, dtype)
    res = np.zeros(shape, dtype)
    nch = [(shape[i] + chunks[i] - 1) // chunks[i] for i in range(nd)]
    import itertools
    for idx in itertools.product(*[range(n) for n in nch]):
        key = ".".join(map(str, idx))
        s, c = http_get(f"{SJ}/timeseries/{path}/{key}", binary=True, sleep=0.5)
        if s != 200:
            continue
        raw = blosc_decompress(c) if meta["compressor"] else c
        arr = np.frombuffer(raw, dtype)
        cshape = [min(chunks[i], shape[i] - idx[i] * chunks[i]) for i in range(nd)]
        full = arr.reshape(chunks)[tuple(slice(0, n) for n in cshape)]
        res[tuple(slice(idx[i] * chunks[i], idx[i] * chunks[i] + cshape[i]) for i in range(nd))] = full
    return res
