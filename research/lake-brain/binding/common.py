"""Shared helpers for the Lake Brain 'binding' research thread (read-only HTTP GETs, polite)."""
import json, os, time, urllib.request, urllib.parse, urllib.error, gzip, math, re, unicodedata

DATA = os.environ.get("LB_DATA", "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
BIND = os.path.join(DATA, "binding")
RAW = os.path.join(BIND, "raw")
DIRECTORY = os.path.join(DATA, "directory_lakes_2026-10-13.json")
POLYS = os.path.join(DATA, "geometry", "engine_polygons_599.geojson.gz")
UA = "SectorEngine-LakeBrain-research/1.0 (read-only; contact mgcather07@gmail.com)"
os.makedirs(RAW, exist_ok=True)


def http_get(url, headers=None, timeout=90, retries=3, sleep=0.4, binary=False):
    """GET with retry/backoff. Returns (status, body-text-or-bytes). Never raises on HTTP errors."""
    h = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    last = (0, "")
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                time.sleep(sleep)
                return r.status, (b if binary else b.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:500]
            last = (e.code, body)
            if e.code in (429, 503, 502, 504):
                time.sleep(3 * (i + 1) ** 2)
                continue
            return last
        except Exception as e:  # network / timeout
            last = (0, str(e))
            time.sleep(2 * (i + 1))
    return last


def get_json(url, headers=None, **kw):
    s, b = http_get(url, headers, **kw)
    if s != 200:
        return s, None
    try:
        return s, json.loads(b)
    except Exception:
        return s, None


def load_directory():
    return json.load(open(DIRECTORY))["lakes"]


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


_STOP = {"lake", "reservoir", "res", "dam", "lk", "the", "of", "near", "at", "river", "creek", "pool", "and", "nr", "below",
         "above", "pond", "flowage", "impoundment", "state", "park", "project", "tailwater", "forebay", "headwater", "elev", "stage"}


def norm_tokens(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return [t for t in s.split() if t not in _STOP and len(t) > 1]


def name_sim(a, b):
    """Token-set similarity in [0,1] (Jaccard with containment bonus)."""
    ta, tb = set(norm_tokens(a)), set(norm_tokens(b))
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    jac = inter / len(ta | tb)
    cont = inter / min(len(ta), len(tb))
    return round(0.5 * jac + 0.5 * cont, 3)
