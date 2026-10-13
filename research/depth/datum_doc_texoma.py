"""Texoma: what do the TWDB 2002 survey report and the gauge records say about the datum of the survey elevations?
Reads the cached TWDB text (outside git) and queries public USGS/CWMS endpoints. Writes part_0.json into the work dir."""
import json, os, re, urllib.request
W = os.path.expanduser('~/Desktop/Development/Sector_Research_Data/depth-brain/')
txt = open(W + 'twdb2/Texoma2002_FinalReport.txt', errors='ignore').read()
m = re.search(r'The vertical datum used during this survey.*?above msl\.', txt, re.S)
quote = re.sub(r'\s+', ' ', m.group(0)) if m else None
def get(u): return urllib.request.urlopen(u, timeout=60).read().decode()
site = get('https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=07331500&siteOutput=expanded')
loc = json.loads(get('https://cwms-data.usace.army.mil/cwms-data/locations/DENI?office=SWT'))
out = {"lakes": {"Lake Texoma|TX": {
  "decision": "SAME_SOURCE", "levelDatum": "NGVD29", "referenceDatum": "NGVD29 (Denison gauge datum; 2002 report says only msl)",
  "sigmaFt": 0.1, "method": "operator-doc", "offsetStats": None,
  "summary": "TWDB 2002 survey elevations are referenced to the USACE Denison Dam gauge 07331500, the same gauge whose CWMS location SWT:DENI (NGVD29) is the Brain level series, so survey elevation and level share one gauge; the survey states 'msl' not NGVD29.",
  "evidence": [
    {"url": "https://www.twdb.texas.gov/surfacewater/surveys/completed/files/Texoma/2002-07/Texoma2002_FinalReport.pdf", "says": quote},
    {"url": "https://www.twdb.texas.gov/surfacewater/surveys/completed/files/Texoma/2002-07/Texoma2002_FinalReport.pdf", "says": "Table 2: 'Upper Limits of 2002 TWDB Volumetric Survey' 620.0 ft; 'Conservation Storage (Top of Active Pool)' 617.0 ft above msl; 620.0 contour taken from USGS 7.5 min quads; lake level during survey 617.53-619.71 per the USACE gauge"},
    {"url": "https://cwms-data.usace.army.mil/cwms-data/locations/DENI?office=SWT", "says": "CWMS location DENI long-name '%s' vertical-datum %s" % (loc.get('long-name'), loc.get('vertical-datum'))},
    {"url": "https://cwms-data.usace.army.mil/cwms-data/levels?office=SWT&level-id-mask=DENI*&unit=EN", "says": "DENI Elev levels Top of Constant Conservation 617.0, Top of Power 617.0, Bottom of Flood Control 617.0, Bottom of Conservation 590.0"},
    {"url": "https://waterservices.usgs.gov/nwis/site/?format=rdb&sites=07331500&siteOutput=expanded", "says": "USCE 07331500 'USCOE Lk Texoma nr Denison, TX' alt_va 0 alt_datum_cd NGVD29 (placeholder altitude 0, not a gauge-datum statement)"}],
  "caveat": "No document fetched states NGVD29 for the 2002 gauge; the CWMS NGVD29 stamp is current. The 3.0 ft re-base (survey boundary 620.0 -> conservation pool 617.0) is a statement about elevations on the gauge scale; if the gauge datum was redefined after 2002 that is undocumented either way. Use the 617.0 conservation pool (CWMS Top of Constant Conservation), not 620.0.",
  "confidence": "medium", "docType": "state-report+cwms-location",
  "deadEnds": ["TWDB report: no NGVD29/NAVD88 label anywhere (only 'mean sea level (msl)')", "USGS site service alt_va is 0 placeholder"],
  "stillNeeds": "USACE Tulsa District statement that the Denison gauge datum has been NGVD29 since before 2002 (pertinent data sheet)"}}}
json.dump(out, open(W + 'datum4/part_0.json', 'w'), indent=1)
print(quote)
