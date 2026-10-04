"""Stage 23: a LAZY Google Cloud L1C SAFE (public bucket gcp-public-data-sentinel-2, anonymous). Every object of the
product is copied locally except the band images (GRANULE/*/IMG_DATA/*.jp2): those are empty placeholders listed in
lazy.json against their public HTTPS URL, read through GDAL /vsicurl/, so ACOLITE's windowed reads fetch only the crop.
The frozen runner (stage22/aco22_one.py) already opens placeholders through lazy.json. Free; nothing is billed.
Verified before use: the lazy read reproduces the full-download ACOLITE samples exactly (check23_lazy.json).
  build(name, root) -> SAFE path;  ENV: the GDAL settings for the run"""
import os, sys, json, shutil, urllib.parse, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
SKIP = ("HTML/", "rep_info/", "preview", "_TCI.jp2")
ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".jp2", "GDAL_HTTP_MAX_RETRY": "8", "GDAL_HTTP_RETRY_DELAY": "3",
       "VSI_CACHE": "TRUE", "VSI_CACHE_SIZE": "200000000", "CPL_VSIL_CURL_CHUNK_SIZE": "1048576"}


def build(name, root):
    safe = os.path.join(root, name + ".SAFE")
    if os.path.exists(os.path.join(safe, "lazy.json")): return safe
    pre = SAFE._prefix(name); objs = [(o, s) for o, s in SAFE.objects(name) if not any(k in o for k in SKIP)]
    if not objs: raise FileNotFoundError(name)
    mapping, get = {}, []
    for o, s in objs:
        rel = o[len(pre):]; dst = os.path.join(safe, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        if "/IMG_DATA/" in rel and rel.endswith(".jp2"):
            open(dst, "wb").close(); mapping[rel] = "/vsicurl/https://storage.googleapis.com/" + SAFE.BUCKET + "/" + urllib.parse.quote(o)
        else:
            get.append((o, dst))
    def one(x):
        o, dst = x; data = SAFE._get(f"https://storage.googleapis.com/{SAFE.BUCKET}/" + urllib.parse.quote(o))
        with open(dst + ".part", "wb") as f: f.write(data)
        os.replace(dst + ".part", dst)
    with cf.ThreadPoolExecutor(8) as ex: list(ex.map(one, get))
    json.dump({"prefix": pre, "map": mapping, "source": "gcs-public"}, open(os.path.join(safe, "lazy.json"), "w"))
    return safe


def delete(name, root):
    shutil.rmtree(os.path.join(root, name + ".SAFE"), ignore_errors=True)
