"""For every lake whose reference pool is a CWMS location level, ask the USACE CWMS Data API for that location's vertical datum.
Read-only HTTP GETs against the public API. Output: jobs/depth-brain/depth_brain/data/cwms_location_datums.json
Usage: python datum_cwms_locations.py DIRECTORY.json FULL_POOL.csv"""
import csv, json, re, sys, time, urllib.parse, urllib.request, datetime as dt

BASE = "https://cwms-data.usace.army.mil/cwms-data"
H = {"Accept": "application/json;version=2"}


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=40).read())


def lookup(loc, office):
    try:
        d = get(f"{BASE}/locations/{urllib.parse.quote(loc)}?office={office}")
        return {"datum": d.get("vertical-datum"), "elevation": d.get("elevation"), "name": d.get("name")}
    except Exception as e:
        return {"error": repr(e)[:120]}


def main(directory_path, full_pool_path, out):
    directory = {l["id"]: l for l in json.load(open(directory_path))["lakes"]}
    res, seen = {}, {}
    for r in csv.DictReader(open(full_pool_path)):
        m = re.match(r"CWMS (.+?)\.Elev", r["source"])
        lake = directory.get(r["id"])
        if not m or not lake or not lake.get("cwmsOffice"):
            continue
        loc, office = m.group(1).strip(), lake["cwmsOffice"]
        key = f"{office}/{loc}"
        if key not in seen:
            seen[key] = lookup(loc, office)
            time.sleep(0.2)
        res[r["id"]] = {"office": office, "location": loc, **seen[key]}
    json.dump({"schema": "depth-cwms-location-datums-v1", "fetchedAt": dt.date.today().isoformat(), "source": f"{BASE}/locations/<loc>?office=<office> (vertical-datum)",
               "lakes": res}, open(out, "w"), indent=1, sort_keys=True)
    ok = [v for v in res.values() if v.get("datum")]
    print(len(res), "lakes;", len(ok), "with datum;", {d: sum(1 for v in ok if v["datum"] == d) for d in {v["datum"] for v in ok}})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "jobs/depth-brain/depth_brain/data/cwms_location_datums.json")
