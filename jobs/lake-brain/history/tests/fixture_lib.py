"""FIXTURE ONLY. Fake-but-valid lakes, a synthetic review pack, a synthetic provider server, all for the pre-seed tests.

Nothing here is real: every lake id is 'FIXTURE <Name> Lake|ZZ', every level is a formula, and the batch built from them carries packId
LBR-SAMPLE-FIXTURE0001 and bindings schema 'lake-brain-bindings-proposed-FIXTURE/v1', which preseed_fleet.py refuses without --allow-fixture
(and always refuses together with --gcs-prefix or the real bindings table). The files this module writes live under
jobs/lake-brain/history/tests/fixtures/, never in jobs/lake-brain/data or jobs/lake-brain/review.
"""
import base64
import csv
import datetime as dt
import json
import math
import os
import urllib.parse

FIXTURE_PACK_ID = "LBR-SAMPLE-FIXTURE0001"
FLAGGED_PACK_ID = "LBR-FLAGGED-FIXTURE0001"
FIXTURE_BINDINGS_SCHEMA = "lake-brain-bindings-proposed-FIXTURE/v1"
NOW = "2026-10-13T12:00:00Z"
UTC = dt.timezone.utc


def _live(provider, station, series, off=0.0):
    return dict(provider=provider, capability="DIRECT_OPERATOR_POOL", station=station, series=series, cadenceMin=60, lagMin=120, datumOffsetFt=off,
                note="FIXTURE")


# name, tz, base level, provider, live refs, history entries, history start (year, month), history lag days, history datum shift (ft)
LAKES = [
    dict(id="FIXTURE Alpha Lake|ZZ", tz="America/Denver", base=6200.0, provider="a2w", cap="DIRECT_OPERATOR_POOL", start=(2019, 3),
         live=[_live("a2w", "SPA:Alpha", "Alpha.Elev.Inst.15Minutes.0.DCP-rev")],
         history=[dict(kind="cwmsDaily", office="SPA", series="Alpha.Elev.Inst.~1Day.0.MRS")], shift=0.0),
    dict(id="FIXTURE Bravo Lake|ZZ", tz="America/Chicago", base=500.0, provider="cwms", cap="DIRECT_OPERATOR_POOL", start=(2024, 6),
         live=[_live("cwms", "LRN", "Bravo-Lake.Elev.Inst.1Hour.0.Raw")],
         history=[dict(kind="cwmsDaily", office="LRN", series="Bravo-Lake.Elev.Inst.1Hour.0.Raw")], shift=0.0),
    dict(id="FIXTURE Charlie Lake|ZZ", tz="America/New_York", base=438.0, provider="usgs", cap="DIRECT_LAKE_GAUGE", start=(2020, 1),
         live=[_live("usgs", "00000001", "62615")],
         history=[dict(kind="usgsDaily", site="00000001", param="62615", stat="dv", offsetFt=0.0)], shift=0.0),
    dict(id="FIXTURE Delta Lake|ZZ", tz="America/Chicago", base=746.0, provider="usgs", cap="DIRECT_LAKE_GAUGE", start=(2022, 5),
         live=[_live("usgs", "00000002", "62615")],
         history=[dict(kind="usgsDaily", site="00000002", param="00065", stat="iv", offsetFt=743.91)], shift=0.0, gage_offset=743.91),
    dict(id="FIXTURE Echo Lake|ZZ", tz="America/Chicago", base=1610.0, provider="nwps", cap="DIRECT_LAKE_GAUGE", start=(2019, 9),
         live=[_live("nwps", "ECHO1", "HPIRG")],
         history=[dict(kind="hadsDaily", lid="ECHO1", pe="HP", offsetFt=0.0)], shift=0.0),
    dict(id="FIXTURE Foxtrot Lake|ZZ", tz="America/Denver", base=5495.0, provider="rise", cap="DIRECT_OPERATOR_POOL", start=(2023, 1),
         live=[_live("rise", "9001", None)],
         history=[dict(kind="riseDaily", item="9001")], shift=0.0, lag=2),
    dict(id="FIXTURE Golf Lake|ZZ", tz="America/Chicago", base=812.0, provider="tva", cap="DIRECT_OPERATOR_POOL", start=(2025, 1),
         live=[_live("tva", "GLFT1", None)],
         history=[dict(kind="tvaOperatingGuide", locationId="GLFT1")], shift=0.0),
    dict(id="FIXTURE Hotel Lake|ZZ", tz="America/Chicago", base=300.0, provider="cwms", cap="DIRECT_OPERATOR_POOL", start=(2021, 1),
         live=[_live("cwms", "LRH", "Hotel-Lake.Elev.Inst.15Minutes.0.DCP-live")],
         history=[dict(kind="cwmsDaily", office="LRH", series="Hotel-Lake.Elev.Inst.~1Day.0.RUL")], shift=6.5),   # datum-shifted history
]


def lake(name):
    return next(l for l in LAKES if l["id"].startswith(f"FIXTURE {name}"))


def level(l, day):
    """The lake's true pool level on a date (a formula); history = this + shift; live = this."""
    doy = day.timetuple().tm_yday
    return round(l["base"] + 4.0 * math.sin(2 * math.pi * doy / 365.25) + 0.01 * (day.toordinal() % 37), 2)


def bindings_doc():
    rows = []
    for l in LAKES:
        y = l["start"][0]
        rows.append(dict(lakeId=l["id"], status="MACHINE_VERIFIED", capability=l["cap"], provider=l["provider"], researchProvider=l["provider"],
                         station=l["live"][0]["station"], series=l["live"][0]["series"], live=l["live"], history=l["history"],
                         historyCompleteYears=max(0, 2026 - y - 1), historyClass="SUFFICIENT", historyFirstYear=y, historyBasis="base",
                         historyNotes=[], timeZone=l["tz"], verification=dict(criteriaVersion="binding-review-v1", researchStatus="VERIFIED", wave="w1")))
    return dict(schema=FIXTURE_BINDINGS_SCHEMA, bindingStatus="MACHINE_VERIFIED",
                note="FIXTURE ONLY - fake lakes for the pre-seed tests. Not a bindings table.", pilotReproduction=[], bindings=rows)


# ---- synthetic review pack + ingest ----------------------------------------------------------------------------------------------
def make_pack(pack_dir):
    os.makedirs(pack_dir, exist_ok=True)
    ids = [l["id"] for l in LAKES]
    with open(os.path.join(pack_dir, "strict_population.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "stratum", "in_sample", "provider", "capability_class", "found_in_wave"])
        for l in LAKES:
            w.writerow([l["id"], f"{l['provider']} | {l['cap']}", "yes", l["provider"], l["cap"], "w1"])
    with open(os.path.join(pack_dir, "binding_review_sample.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lake_id", "stratum"])
        for l in LAKES:
            w.writerow([l["id"], f"{l['provider']} | {l['cap']}"])
    for name, rows in (("held_back_coordinate_flags.csv", [["FIXTURE Held Lake|ZZ", "off_water"]]),
                       ("binding_review_flagged57.csv", [["FIXTURE Flagged Lake|ZZ"]])):
        with open(os.path.join(pack_dir, name), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["lake_id", "directory_coordinate_flag"] if name.startswith("held") else ["lake_id"])
            w.writerows(rows)
    json.dump(dict(criteria="binding-review-v1", samplePackId=FIXTURE_PACK_ID, flaggedPackId=FLAGGED_PACK_ID, seed=1, snapshotDate="2026-10-13",
                   acceptRule=dict(maxErrors=1)), open(os.path.join(pack_dir, "pack_manifest.json"), "w"))
    return ids


def write_review_csv(path, pack_id, ids, decision=lambda lid: "ACCEPT"):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["pack_id", "lake_id", "lake_name", "stratum", "computer_recommendation", "decision", "notes", "decided_at_utc", "reviewer", "exported_at_utc"])
        for lid in ids:
            w.writerow([pack_id, lid, lid, "", "PASS", decision(lid), "", "2026-10-14T10:00:00Z", "FIXTURE", "2026-10-14T11:00:00Z"])


def make_fixture_batch(out_dir, work_dir, decision=lambda lid: "ACCEPT"):
    """Run the REAL ingest (ingest_review_result.main) on the synthetic pack. Returns (batch_path, result_path, bindings_path)."""
    import ingest_review_result as I
    pack = os.path.join(work_dir, "fixture_pack")
    ids = make_pack(pack)
    csvp = os.path.join(work_dir, "fixture_review.csv")
    write_review_csv(csvp, FIXTURE_PACK_ID, ids, decision)
    os.makedirs(out_dir, exist_ok=True)
    bpath = os.path.join(out_dir, "bindings.fixture.json")
    json.dump(bindings_doc(), open(bpath, "w"), indent=1, sort_keys=True)
    rc = I.main(["--review-csv", csvp, "--pack-dir", pack, "--out-dir", out_dir, "--bindings", bpath, "--write", "--now", "2026-10-14T12:00:00Z"])
    assert rc == 0
    return os.path.join(out_dir, "accepted_batch.json"), os.path.join(out_dir, "binding_review_result.json"), bpath


# ---- synthetic provider server ----------------------------------------------------------------------------------------------------
class R:
    def __init__(self, status, body=b""):
        self.status, self.body = status, body

    @property
    def ok(self):
        return 200 <= self.status < 300


def _j(o):
    return R(200, json.dumps(o).encode())


class FakeServer:
    """Implements .get(url, accept, timeout) for every provider the pre-seed reads, from the formulas above. `calls` lists the URLs."""

    def __init__(self, now=NOW, shift_overrides=None, fail=None, hads_429_first=True):
        self.now = dt.datetime.fromisoformat(now.replace("Z", "+00:00"))
        self.shift = dict(shift_overrides or {})
        self.fail = fail or (lambda url: None)          # url -> R or None
        self.calls = []
        self.hads_429_first = hads_429_first
        self.hads_seen = set()

    def _l(self, **kw):
        for l in LAKES:
            if all(l["history"][0].get(k) == v or l["live"][0].get(k) == v for k, v in kw.items()):
                return l
        raise KeyError(kw)

    def hist_value(self, l, day):
        return round(level(l, day) + self.shift.get(l["id"], l["shift"]), 2)

    def _days(self, l, lag=0):
        s = dt.date(l["start"][0], l["start"][1], 1)
        e = (self.now - dt.timedelta(days=lag)).date()
        d = s
        while d <= e:
            yield d
            d += dt.timedelta(days=1)

    def get(self, url, accept="application/json", timeout=60):
        self.calls.append(url)
        f = self.fail(url)
        if f is not None:
            return f
        u = urllib.parse.urlparse(url)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        h = u.netloc
        if h == "cwms-data.usace.army.mil":
            return self._cwms(q)
        if h == "waterservices.usgs.gov":
            return self._usgs(u.path, q)
        if h == "data.usbr.gov":
            return self._rise(q)
        if h == "mesonet.agron.iastate.edu":
            return self._hads(url, q)
        if h == "api.water.noaa.gov":
            return self._nwps(u.path)
        if h == "water.usace.army.mil":
            return self._a2w(u.path)
        if h == "www.tva.com":
            return self._tva(u.path)
        return R(404)

    # CWMS
    def _cwms(self, q):
        l = next((x for x in LAKES if any(i.get("series") == q["name"] for i in x["history"] + x["live"])), None)
        if l is None:
            return R(404)
        b = dt.datetime.fromisoformat(q["begin"].replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(q["end"].replace("Z", "+00:00"))
        hourly = "1Hour" in q["name"]
        is_hist = any(i.get("series") == q["name"] for i in l["history"])
        is_live = any(i.get("series") == q["name"] for i in l["live"])
        val = (lambda d: self.hist_value(l, d)) if (is_hist and not is_live) or l["id"] != "FIXTURE Hotel Lake|ZZ" else (lambda d: level(l, d))
        pts = []
        for d in self._days(l):
            if hourly:
                for hr in range(24):
                    t = dt.datetime(d.year, d.month, d.day, hr, tzinfo=UTC)
                    pts.append((t, round(val(d) + 0.01 * (hr - 12), 2)))
            else:
                t = dt.datetime(d.year, d.month, d.day, 12, tzinfo=UTC)
                pts.append((t, val(d)))
        pts = [(t, v) for t, v in pts if b <= t < e]
        page = int(q.get("page", "1") or 1) if q.get("page", "").isdigit() else 1
        chunk = pts[(page - 1) * 5000: page * 5000]
        body = dict(units="ft", values=[[int(t.timestamp() * 1000), v, 0] for t, v in chunk])
        if page * 5000 < len(pts):
            body["next-page"] = str(page + 1)
        return _j(body)

    # USGS
    def _usgs(self, path, q):
        site, param = q["sites"], q["parameterCd"]
        l = next((x for x in LAKES if x["history"][0].get("site") == site or x["live"][0]["station"] == site), None)
        if l is None:
            return R(404)
        gage = l.get("gage_offset", 0.0)
        pts = []
        if "/dv/" in path:
            for d in self._days(l):
                pts.append(("%s" % d.isoformat() + "T00:00:00.000", self.hist_value(l, d) - gage))
            s, e = q["startDT"], q["endDT"]
            pts = [(t, v) for t, v in pts if s <= t[:10] <= e]
            var = dict(noDataValue=-999999.0, options=dict(option=[dict(optionCode="00003")]))
            return _j(dict(value=dict(timeSeries=[dict(variable=var, values=[dict(value=[dict(dateTime=t, value=str(v)) for t, v in pts])])])))
        if "period" in q:                       # live (an elevation parameter: no gage-height offset)
            gage = 0.0
            hrs = int(q["period"][2:-1])
            t0 = self.now - dt.timedelta(hours=hrs)
            t = t0
            while t <= self.now:
                pts.append((t, level(l, t.date()) - gage))
                t += dt.timedelta(hours=6)
        else:
            s = dt.datetime.fromisoformat(q["startDT"] + "T00:00:00+00:00")
            e = dt.datetime.fromisoformat(q["endDT"] + "T23:59:59+00:00")
            for d in self._days(l):
                for hr in (3, 9, 15, 21):
                    t = dt.datetime(d.year, d.month, d.day, hr, tzinfo=UTC)
                    if s <= t <= e:
                        pts.append((t, self.hist_value(l, d) - gage + (0.5 if hr == 21 else 0.0)))
        vals = [dict(dateTime=t.strftime("%Y-%m-%dT%H:%M:%S.000+00:00"), value=str(round(v, 2))) for t, v in pts]
        return _j(dict(value=dict(timeSeries=[dict(values=[dict(value=vals)])])))

    # RISE
    def _rise(self, q):
        l = next((x for x in LAKES if x["live"][0]["station"] == q["itemId"]), None)
        if l is None:
            return R(404)
        after = q["dateTime[after]"]
        items = []
        for d in self._days(l, lag=l.get("lag", 0)):
            if d.isoformat() < after:
                continue
            res = self.hist_value(l, d)
            attrs = dict(dateTime=f"{d.isoformat()}T07:00:00+00:00", result=res, resultAttributes=dict(resultType="observed"))
            if d.day == 15:
                attrs["result"] = 0.0                          # RISE placeholder for a missing day
            if d.day == 16:
                attrs["resultAttributes"] = dict(resultType="modeled")
            items.append(dict(attributes=attrs))
        page = int(q["page"])
        per = 2000
        body = dict(data=items[(page - 1) * per: page * per], links=dict(next="x" if page * per < len(items) else ""))
        return _j(body)

    # HADS
    def _hads(self, url, q):
        l = next((x for x in LAKES if x["history"][0].get("lid") == q["stations"]), None)
        if l is None:
            return R(404)
        if self.hads_429_first and url not in self.hads_seen:
            self.hads_seen.add(url)
            if q["sts"].startswith("2024"):
                return R(429)
        s = dt.datetime.strptime(q["sts"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        e = dt.datetime.strptime(q["ets"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)
        lines = ["station,utc_valid,HPIRGZZ,HPIRZZZ"]
        for d in self._days(l):
            for hr in (0, 6, 12, 18):
                t = dt.datetime(d.year, d.month, d.day, hr, tzinfo=UTC)
                if s <= t < e:
                    v = self.hist_value(l, d)
                    # the gauge moved its pool column in 2021: first non-empty HPIR column wins
                    lines.append(f"{q['stations']},{t.strftime('%Y-%m-%d %H:%M:%S')},{v if d.year < 2021 else ''},{'' if d.year < 2021 else v}")
        return R(200, ("\n".join(lines) + "\n").encode())

    # NWPS
    def _nwps(self, path):
        lid = path.rstrip("/").split("/")[-3]
        l = next((x for x in LAKES if x["live"][0]["station"] == lid), None)
        if l is None:
            return R(404)
        rows = []
        t = self.now - dt.timedelta(days=30)
        while t <= self.now:
            rows.append(dict(validTime=t.strftime("%Y-%m-%dT%H:%M:%SZ"), primary=level(l, t.date()) + self.shift.get(l["id"], 0.0)))
            t += dt.timedelta(hours=3)
        return _j(dict(pedts="HPIRG", primaryUnits="ft", data=rows))

    # Access2Water
    def _a2w(self, path):
        out = []
        for l in LAKES:
            r = l["live"][0]
            if r["provider"] == "a2w" and path.endswith(f"/{r['station'].split(':')[0].lower()}/locations"):
                v = level(l, self.now.date())
                out.append(dict(provider=r["station"].split(":")[0], code=r["station"].split(":")[1],
                                timeseries=[dict(tsid=r["series"], unit="ft", latest_time=(self.now - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                 latest_value=v, delta24hr=0.12)]))
        return _j(out)

    # TVA
    def _tva(self, path):
        loc = path.rstrip("/").split("/")[-1]
        l = next((x for x in LAKES if x["live"][0]["station"] == loc), None)
        if l is None:
            return R(404)
        if "operating-guide" in path:
            items = []
            y = self.now.year
            d = dt.date(y, 1, 1)
            while d.year == y:
                cur = self.hist_value(l, d) if d <= self.now.date() else 0
                prev = self.hist_value(l, dt.date(y - 1, d.month, min(d.day, 28)))
                items.append(dict(Day=f"{d.month}/{d.day}/2025", GuideCurve="0", CurYrElev=f"{cur:,.2f}" if cur else "0", PrevYrElev=f"{prev:,.2f}"))
                d += dt.timedelta(days=1)
            return _j(dict(items=items))
        rows = []
        for back in range(48, -1, -3):
            t = self.now - dt.timedelta(hours=back)
            loc_t = t.astimezone(dt.timezone(dt.timedelta(hours=-5)))        # CDT
            hr = loc_t.hour
            label = "Midnight" if hr == 0 else "Noon" if hr == 12 else (f"{hr} AM" if hr < 12 else f"{hr - 12} PM")
            rows.append(dict(Day=f"{loc_t.month:02d}/{loc_t.day:02d}/{loc_t.year}", Time=f"{label} CDT", ReservoirElevation=f"{level(l, loc_t.date()):,.2f}"))
        return _j(rows)
