"""Extract (elevation, capacity) pairs printed on Reclamation Great Plains allocation diagrams (`resaloc`): `... Elev. 2244.0 (119,469 Acre - Feet)`. Output outside git.
Run: PYTHONPATH=<datum4/w2/pylib> /opt/homebrew/bin/python3 resaloc_pairs.py"""
import glob, json, os, re
from pypdf import PdfReader
D3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/pdf")
D5 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5")
PAIR = re.compile(r"Elev\.?\s*([\d,]+(?:\.\d+)?)\s*\(\s*([\d,]+)\s*Acre", re.I)
out = {}
for p in sorted(glob.glob(D3 + "/https___www_usbr_gov_gp_aop_resaloc_*.pdf")) + [D5 + "/dl/swanson_resaloc.pdf"]:
    name = os.path.basename(p)
    try:
        t = "\n".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
    except Exception as e:
        print(name, "ERR", repr(e)[:60]); continue
    t = re.sub(r"[ ]+", " ", t)
    pairs = sorted({(float(a.replace(",", "")), float(b.replace(",", ""))) for a, b in PAIR.findall(t)})
    title = re.sub(r"\s+", " ", t.strip().splitlines()[0]) if t.strip() else ""
    out[name] = {"title": title, "pairs": pairs, "revised": (re.search(r"Revised\s*([\d/]+)", t) or [None, None])[1]}
    print(name.split("resaloc_")[-1], len(pairs), out[name]["revised"], title[:50], flush=True)
json.dump(out, open(D5 + "/resaloc_pairs.json", "w"), indent=1)
