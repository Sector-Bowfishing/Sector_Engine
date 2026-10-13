"""Fetch the smaller raw catalogs: USGS NWIS site+series catalog per state, TWDB, NWPS, CO-OPS, TVA. Skips files that already exist."""
import os, time
from common import *

STATES = "AK AL AR AZ CA CO CT DE FL GA HI IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY".split()
for d in ("usgs", "twdb", "nwps", "coops", "tva"):
    os.makedirs(f"{RAW}/{d}", exist_ok=True)


def save(path, url, headers=None, timeout=240):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    s, b = http_get(url, headers, timeout=timeout, sleep=0.6)
    open(path, "w").write(b if s == 200 else "")   # an empty file records 'no match' (USGS answers 404 when nothing matches)
    print(s, os.path.basename(path), len(b), flush=True)


for st in STATES:
    # lakes (all series incl. gage height) and reservoir-elevation parameters at other site types (the siteOutput=expanded variant is rejected by the service)
    save(f"{RAW}/usgs/lk_{st}.rdb", f"https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd={st}&siteType=LK&seriesCatalogOutput=true")
    save(f"{RAW}/usgs/ot_{st}.rdb", f"https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd={st}&siteType=ST,ES,SP,AT,OC&parameterCd=62614,62615,62616,00062,72020,72022,72036,00054&seriesCatalogOutput=true")
save(f"{RAW}/twdb/recent-conditions.json", "https://www.waterdatafortexas.org/reservoirs/recent-conditions.json")
save(f"{RAW}/nwps/gauges_all.json", "https://api.water.noaa.gov/nwps/v1/gauges", timeout=300)
save(f"{RAW}/coops/stations_waterlevels.json", "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json?type=waterlevels&units=english")
# TVA needs a browser User-Agent and Accept: application/json (plain curl is served the ServiceStack HTML page)
save(f"{RAW}/tva/locations.json", "https://www.tva.com/RestApi/locations", {"User-Agent": "Mozilla/5.0 (Macintosh) Chrome/120", "Accept": "application/json"})
