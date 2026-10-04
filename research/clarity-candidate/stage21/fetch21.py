"""Stage 21: rebuild a real nominal S2C L1C SAFE from the AWS tile layout (s3://sentinel-s2-l1c, requester pays).
The bucket keeps one tile's files flat: B01..B12.jp2, metadata.xml (the granule MTD_TL), product_metadata.xml
(MTD_MSIL1C), qi/ (masks). Files are copied byte for byte into the SAFE layout ACOLITE reads, with the band file names
the product metadata lists (IMAGE_FILE). Credentials come from the user's own AWS configuration (never handled here);
every request is RequestPayer=requester; downloaded bytes are logged to stage21/aws_bytes.log for the cost record.
  fetch(rec, dest_root, bands=None) -> SAFE path        rec = select21.json["s2c"] record"""
import os, json, threading, time
import xml.etree.ElementTree as ET
import boto3
from botocore.config import Config
S = os.environ["CLARITY_RESEARCH_ROOT"]
BUCKET = "sentinel-s2-l1c"
PAY = {"RequestPayer": "requester"}
CAP_GB = 95.0
_s3 = None; _lock = threading.Lock()


def s3():
    global _s3
    with _lock:
        if _s3 is None:
            _s3 = boto3.client("s3", region_name="eu-central-1",
                               config=Config(retries={"total_max_attempts": 6, "mode": "adaptive"}, connect_timeout=10, read_timeout=120, max_pool_connections=50))
    return _s3


def _log(n, key):
    with _lock:
        open(f"{S}/stage21/aws_bytes.log", "a").write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\t{n}\t{key}\n")


def get(key, path):
    """Managed download (multipart, retries, stream cleanup); the bytes are logged for the cost record."""
    if billed_gb() >= CAP_GB: raise RuntimeError(f"AWS download cap reached ({CAP_GB} GB logged): stopping to stay inside the free transfer tier")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s3().download_file(BUCKET, key, path, ExtraArgs=PAY)
    n = os.path.getsize(path); _log(n, key); return n


def listing(prefix):
    pages = s3().get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix, **PAY)
    return [(o["Key"], o["Size"]) for page in pages for o in page.get("Contents", [])]


def fetch(rec, dest_root, bands=None, qi=True):
    """bands: None = every band; else a list like ["B05", "B08"]. qi: also copy the qi/ masks."""
    prefix = rec["assets"]["granule_metadata"].replace(f"s3://{BUCKET}/", "").rsplit("/", 1)[0] + "/"
    safe = os.path.join(dest_root, rec["product"] + ".SAFE")
    if os.path.exists(os.path.join(safe, ".complete")): return safe
    files = dict(listing(prefix))
    get(prefix + "productInfo.json", os.path.join(safe, "productInfo.json"))
    ppath = json.load(open(os.path.join(safe, "productInfo.json")))["path"].rstrip("/")      # products/YYYY/M/D/<product name>
    assert ppath.endswith(rec["product"]), (ppath, rec["product"])
    get(ppath + "/metadata.xml", os.path.join(safe, "MTD_MSIL1C.xml"))
    root = ET.parse(os.path.join(safe, "MTD_MSIL1C.xml")).getroot()
    imgs = [e.text for e in root.iter("IMAGE_FILE")]
    gran = imgs[0].split("/")[1]
    get(prefix + "metadata.xml", os.path.join(safe, "GRANULE", gran, "MTD_TL.xml"))
    for im in imgs:
        b = im.rsplit("_", 1)[-1]
        if b == "TCI" or (bands is not None and b not in bands): continue
        get(prefix + f"{b}.jp2", os.path.join(safe, im + ".jp2"))
    if qi:
        for k in files:
            if k.startswith(prefix + "qi/"):
                n = k.rsplit("/", 1)[-1]
                if n.endswith(".jp2") and not n.startswith("MSK_"): n = "MSK_" + n            # the SAFE name ACOLITE globs for (MSK_DETFOO_Bxx.jp2)
                get(k, os.path.join(safe, "GRANULE", gran, "QI_DATA", n))
    open(os.path.join(safe, ".complete"), "w").write(json.dumps({"prefix": prefix, "bands": bands}))
    return safe


def billed_gb():
    p = f"{S}/stage21/aws_bytes.log"
    return sum(int(l.split("\t")[1]) for l in open(p)) / 1e9 if os.path.exists(p) else 0.0
