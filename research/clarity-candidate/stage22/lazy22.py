"""Stage 22: a LAZY real-nominal S2C SAFE. Metadata (MTD_MSIL1C via productInfo.json, MTD_TL) and the detector-footprint
masks are copied locally (small, logged); every band image is an empty placeholder whose /vsis3/ object is listed in
lazy.json, so ACOLITE's windowed GDAL reads fetch only the crop (byte counts parsed from GDAL network statistics and logged
by run_aco22). Requester pays; the user's own AWS configuration; the Stage 21 95 GB cap applies to the running total.
  build(rec, root) -> SAFE path"""
import os, json, sys
import xml.etree.ElementTree as ET
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage21")
import fetch21 as F21


def build(rec, root):
    prefix = rec["assets"]["granule_metadata"].replace(f"s3://{F21.BUCKET}/", "").rsplit("/", 1)[0] + "/"
    safe = os.path.join(root, rec["product"] + ".SAFE")
    if os.path.exists(os.path.join(safe, "lazy.json")): return safe
    files = dict(F21.listing(prefix))
    F21.get(prefix + "productInfo.json", os.path.join(safe, "productInfo.json"))
    ppath = json.load(open(os.path.join(safe, "productInfo.json")))["path"].rstrip("/")
    assert ppath.endswith(rec["product"]), (ppath, rec["product"])
    F21.get(ppath + "/metadata.xml", os.path.join(safe, "MTD_MSIL1C.xml"))
    imgs = [e.text for e in ET.parse(os.path.join(safe, "MTD_MSIL1C.xml")).getroot().iter("IMAGE_FILE")]
    gran = imgs[0].split("/")[1]
    F21.get(prefix + "metadata.xml", os.path.join(safe, "GRANULE", gran, "MTD_TL.xml"))
    for k in files:
        n = k.rsplit("/", 1)[-1]
        if k.startswith(prefix + "qi/") and n.startswith("DETFOO_") and n.endswith(".jp2"):
            F21.get(k, os.path.join(safe, "GRANULE", gran, "QI_DATA", "MSK_" + n))
    mapping = {}
    for im in imgs:
        b = im.rsplit("_", 1)[-1]
        if b == "TCI": continue
        rel = im + ".jp2"; p = os.path.join(safe, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").close()
        mapping[rel] = f"/vsis3/{F21.BUCKET}/{prefix}{b}.jp2"
    json.dump({"prefix": prefix, "map": mapping}, open(os.path.join(safe, "lazy.json"), "w"))
    return safe
