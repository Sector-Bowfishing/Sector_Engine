"""Fetch a Sentinel-2 L1C (or L2A) SAFE product from the Google Cloud public bucket (anonymous, read-only).
  python safe.py <PRODUCT_NAME>        e.g. S2C_MSIL1C_20241214T162731_N9905_R040_T16SED_20241214T181831
  -> <cache>/<PRODUCT_NAME>.SAFE/ with every object of the product (the preview HTML is skipped).
Library: fetch(name) -> path; listing(tile, prefix) -> [product names]; delete(name)."""
import json, os, sys, shutil, urllib.request, urllib.parse, concurrent.futures as cf

BUCKET = "gcp-public-data-sentinel-2"
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "safe_cache")
API = "https://storage.googleapis.com/storage/v1/b/%s/o" % BUCKET


def _get(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise


def _prefix(name):
    t = name.split("_")[5][1:]           # T16SED -> 16SED
    base = "L2/tiles" if "MSIL2A" in name else "tiles"
    return f"{base}/{t[:2]}/{t[2]}/{t[3:]}/{name}.SAFE/"


def objects(name):
    out, tok = [], None
    while True:
        q = {"prefix": _prefix(name), "maxResults": 1000}
        if tok: q["pageToken"] = tok
        d = json.loads(_get(API + "?" + urllib.parse.urlencode(q)))
        out += [(o["name"], int(o["size"])) for o in d.get("items", []) if not o["name"].endswith("$folder$")]
        tok = d.get("nextPageToken")
        if not tok:
            return out


def listing(tile, prefix):
    """Product names on a tile starting with prefix (e.g. 'S2C_MSIL1C_2024')."""
    t = tile.lstrip("T"); out, tok = [], None
    while True:
        q = {"prefix": f"tiles/{t[:2]}/{t[2]}/{t[3:]}/{prefix}", "delimiter": "/", "maxResults": 1000}
        if tok: q["pageToken"] = tok
        d = json.loads(_get(API + "?" + urllib.parse.urlencode(q)))
        out += [p.rstrip("/").split("/")[-1][:-5] for p in d.get("prefixes", [])]
        tok = d.get("nextPageToken")
        if not tok:
            return sorted(set(out))


def fetch(name, skip=("HTML/", "rep_info/", "preview")):
    root = os.path.join(CACHE, name + ".SAFE")
    done = os.path.join(root, ".complete")
    if os.path.exists(done):
        return root
    objs = [(o, s) for o, s in objects(name) if not any(k in o for k in skip)]
    if not objs:
        raise FileNotFoundError(name)
    pre = _prefix(name)
    def one(o):
        rel = o[0][len(pre):]
        dst = os.path.join(root, rel)
        if os.path.exists(dst) and os.path.getsize(dst) == o[1]:
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = _get(f"https://storage.googleapis.com/{BUCKET}/" + urllib.parse.quote(o[0]))
        with open(dst + ".part", "wb") as f:
            f.write(data)
        os.replace(dst + ".part", dst)
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(one, objs))
    open(done, "w").write(str(sum(s for _, s in objs)))
    return root


def delete(name):
    shutil.rmtree(os.path.join(CACHE, name + ".SAFE"), ignore_errors=True)


if __name__ == "__main__":
    for n in sys.argv[1:]:
        print(fetch(n))


def l1c_for(c1_id, hint=None):
    """The Google-bucket L1C for a C1 L2A item (same satellite, same day, closest sensing time within an hour)."""
    if hint:
        return hint
    sat, tile, dtt = c1_id.split("_")[0], c1_id.split("_")[1].lstrip("T"), c1_id.split("_")[2]
    cands = listing(tile, f"{sat}_MSIL1C_{dtt[:8]}")
    if not cands:
        return None
    sec = lambda t: int(t[9:11]) * 3600 + int(t[11:13]) * 60 + int(t[13:15])
    diff = lambda n: abs(sec(n.split("_")[2]) - sec(dtt))
    best = min(cands, key=lambda n: (diff(n), -int(n.split("_")[3][1:])))
    return best if diff(best) < 3600 else None
