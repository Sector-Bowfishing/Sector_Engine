"""Stage 20 part 1 (value-blind): radiometric metadata of the L1C products by satellite and processing baseline.
Reads MTD_MSIL1C.xml (public Google bucket) for: the preliminary S2C tandem products (N9905/N9906, Dec 2024) used by the
Stage 11/12 tandem; nominal S2C N0511 (2025) and N0512 (2026) as the engine actually saw them; S2A and S2B at the same
baselines. Extracts per band: PHYSICAL_GAINS, SOLAR_IRRADIANCE, RADIO_ADD_OFFSET, QUANTIFICATION_VALUE and the embedded
Spectral_Information (central wavelength, bandwidth, spectral response). Writes meta20.json."""
import json, glob, urllib.request, urllib.parse, re, sys, os
import xml.etree.ElementTree as ET
S = os.environ["CLARITY_RESEARCH_ROOT"]
BUCKET = "https://storage.googleapis.com/gcp-public-data-sentinel-2/"
def mtd_url(name):
    t = name.split("_")[5][1:]; return BUCKET + f"tiles/{t[:2]}/{t[2]}/{t[3:]}/{name}.SAFE/MTD_MSIL1C.xml"
names = set()
for l in open(f"{S}/../../../scratchpad_paths.txt").read().split() if os.path.exists(f"{S}/../../../scratchpad_paths.txt") else []: pass
# products: every L1C named in the research results, plus the preliminary tandem list
for f in glob.glob(f"{S}/stage1[2-9]*/**/res*/*.json", recursive=True):
    try: r = json.load(open(f))
    except Exception: continue
    if r.get("l1c"): names.add(r["l1c"])
TANDEM = [l.strip() for l in open(sys.argv[1]) if l.strip()] if len(sys.argv) > 1 else []
def key(n): f = n.split("_"); return (f[0], f[3], f[6][:4])          # satellite, baseline, generation year
groups = {}
for n in sorted(names) + TANDEM:
    groups.setdefault(key(n), []).append(n)
pick = {k: sorted(v)[:4] for k, v in groups.items() if k[0] in ("S2A", "S2B", "S2C")}
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
def parse(xml):
    root = ET.fromstring(xml); out = {"gains": {}, "esun": {}, "offset": {}, "srf": {}}
    q = root.find(".//QUANTIFICATION_VALUE"); out["quant"] = float(q.text) if q is not None else None
    for g in root.iter("PHYSICAL_GAINS"): out["gains"][BANDS[int(g.get("bandId"))]] = float(g.text)
    for e in root.iter("SOLAR_IRRADIANCE"): out["esun"][BANDS[int(e.get("bandId"))]] = float(e.text)
    for o in root.iter("RADIO_ADD_OFFSET"): out["offset"][BANDS[int(o.get("band_id"))]] = float(o.text)
    for si in root.iter("Spectral_Information"):
        b = BANDS[int(si.get("bandId"))]; sr = si.find("Spectral_Response")
        vals = [float(x) for x in sr.find("VALUES").text.split()] if sr is not None else []
        out["srf"][b] = {"min": float(si.find("Wavelength/MIN").text), "max": float(si.find("Wavelength/MAX").text), "central": float(si.find("Wavelength/CENTRAL").text),
                         "step": float(sr.find("STEP").text) if sr is not None else None, "values": vals}
    return out
res = {}
for k, ns in sorted(pick.items()):
    for n in ns:
        try: res[n] = {"group": list(k), **parse(urllib.request.urlopen(mtd_url(n), timeout=60).read())}; break
        except Exception as e: res[n] = {"group": list(k), "error": str(e)[:100]}
json.dump(res, open(f"{S}/stage20/meta20.json", "w"))
for n, v in res.items(): print(v["group"], n[:60], "error" if "error" in v else f"gains {len(v['gains'])} srf {len(v['srf'])} quant {v['quant']}")
