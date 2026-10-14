"""Wind live-reliability audit (docs/brains/wind/WIND_VALIDATION_PHASE_PREREG.md, section L).
Reads OPERATIONAL METADATA ONLY: ingest-ledger status lines, run-summary counters/errors, Cloud Run execution status/timestamps,
Brain-publish status lines. It opens no forecast, analysis, observation or state VALUE from the live (H2) period.

  python research/live_reliability.py META_DIR OUT.json     # META_DIR holds ledger/, runs/, executions.json, brainlogs.json"""
import glob, json, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

P = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
LIVE_START = datetime(2026, 10, 7, 4, 59, tzinfo=timezone.utc)      # first archive run (ledger 20261007T050131Z)
LAKES = ("guntersville", "wheeler", "wilson", "pickwick")
RANK = {"complete": 3, "partial": 2, "failed": 0}


def load(meta):
    led = []
    for f in sorted(glob.glob(os.path.join(meta, "ledger", "runs", "*.jsonl"))):
        for ln in open(f):
            if ln.strip():
                led.append(json.loads(ln))
    runs = {}
    for f in sorted(glob.glob(os.path.join(meta, "runs", "*", "*.json"))):
        j = json.load(open(f))
        runs[j["runAt"]] = {k: j.get(k) for k in ("runAt", "errors", "seconds", "newestNbmCycle", "nbmSkipped", "metar")}   # counters only
    ex = json.load(open(os.path.join(meta, "executions.json")))
    brain = []
    for x in json.load(open(os.path.join(meta, "brainlogs.json"))):
        j = json.loads(x["textPayload"][len("windbrain "):])
        lakes = j.get("lakes") or {}
        brain.append({"at": x["timestamp"][:19] + "Z", "ok": bool(j.get("ok")), "errors": [e[:120] for e in j.get("errors", [])][:1],
                      "lakeStates": {k: {"kind": v.get("kind"), "stale": v.get("stale"), "readiness": v.get("readiness")} for k, v in lakes.items()}})
    return led, runs, ex, sorted(brain, key=lambda b: b["at"])


def audit(meta, now=None):
    now = now or datetime.now(timezone.utc)
    led, runs, ex, brain = load(meta)
    best = {}
    first_ok = {}
    for r in led:
        if r["product"] == "METAR":
            continue
        k = (r["product"], r["cycle"], r["lake"])
        if k not in best or RANK.get(r["status"], 0) > RANK.get(best[k]["status"], 0):
            best[k] = r
    exs = []
    for e in ex:
        st = e.get("status", {})
        ok = any(c.get("type") == "Completed" and c.get("status") == "True" for c in st.get("conditions", []))
        exs.append({"name": e["metadata"]["name"], "created": e["metadata"]["creationTimestamp"][:19] + "Z",
                    "completed": (st.get("completionTime") or "")[:19] + ("Z" if st.get("completionTime") else ""),
                    "ok": ok, "failed": st.get("failedCount") or 0, "succeeded": st.get("succeededCount") or 0})
    exs.sort(key=lambda e: e["created"])
    days, d = [], LIVE_START.date()
    while d <= now.date():
        day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc); day1 = day0 + timedelta(days=1)
        closed = now >= day1 + timedelta(hours=3)          # NBM/RTMA catch-up windows are 3-4 h: a day is final 3 h after it ends
        why = []
        exp_n = 24; exp_q = 96
        start_h = 0; start_q = 0
        if day0 < LIVE_START < day1:
            start_h = LIVE_START.hour + (1 if LIVE_START.minute else 0); start_q = start_h * 4
            why.append(f"clock started {LIVE_START:%H:%MZ}: only {24 - start_h} hourly cycles possible")
        nbm = {}
        for lk in LAKES:
            c = sum(1 for h in range(24) if best.get(("NBM", f"{day0 + timedelta(hours=h):%Y-%m-%dT%H:00:00Z}", lk), {}).get("status") == "complete")
            nbm[lk] = c
        rtma = {}
        for lk in LAKES:
            rtma[lk] = sum(1 for q in range(96) if best.get(("RTMA-RU", f"{day0 + timedelta(minutes=15 * q):%Y-%m-%dT%H:%M:00Z}", lk), {}).get("status") == "complete")
        nbm_min = min(nbm.values()); rtma_min = min(rtma.values())
        nbm_pct = nbm_min / exp_n; rtma_pct = rtma_min / exp_q
        if nbm_pct < 0.99 and not why:
            why.append(f"NBM complete cycles {nbm_min}/24 on the worst lake ({nbm_pct:.1%} < 99%)")
        elif nbm_pct < 0.99:
            why.append(f"NBM {nbm_min}/24")
        if rtma_pct < 0.95:
            why.append(f"RTMA-RU quarter-hours {rtma_min}/96 on the worst lake ({rtma_pct:.1%} < 95%)")
        metar_n = max([(r["metar"] or {}).get(f"{d}", 0) for r in runs.values() if r["runAt"] >= f"{day1:%Y-%m-%dT00:00:00Z}" and r["runAt"] < f"{day1 + timedelta(hours=3):%Y-%m-%dT%H:%M:%SZ}"] or [0])
        # run gaps (state refresh): consecutive successful executions' creation times inside the day
        dx = [e for e in exs if e["created"][:10] == day0.strftime("%Y-%m-%d")]
        okx = sorted(P(e["created"]) for e in dx if e["ok"])
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(okx, okx[1:]) if day0 <= b < day1]
        maxgap = round(max(gaps), 1) if gaps else None
        if maxgap and maxgap > 90 and not closed is False:
            why.append(f"state refresh gap {maxgap:.0f} min > 90")
        failed_ex = [e["name"] for e in exs if day0.strftime("%Y-%m-%d") == e["created"][:10] and not e["ok"] and e["completed"]]
        if failed_ex:
            why.append(f"{len(failed_ex)} execution(s) did not complete OK: {failed_ex[:3]}")
        bday = [b for b in brain if b["at"][:10] == f"{d}"]
        if not (closed and metar_n):
            if closed:
                why.append("METAR day count unavailable")
        days.append({"date": f"{d}", "closed": closed, "nbmCompletePerLake": nbm, "nbmPct": round(nbm_pct, 4), "rtmaCompletePerLake": rtma,
                     "rtmaPct": round(rtma_pct, 4), "metarObsCount": metar_n, "executions": len(dx), "maxStateGapMin": maxgap,
                     "brainPublishOk": sum(b["ok"] for b in bday), "brainPublishFailed": sum(not b["ok"] for b in bday),
                     "brainStaleStates": sum(1 for b in bday for s in b["lakeStates"].values() if s.get("stale")),
                     "valid": closed and not why, "reasons": why if closed else (["day still open"] + why)})
        d += timedelta(days=1)
    # Brain-publish days: >= 23 successful hourly publishes, none failed, no gap > 90 min between successes, no stale state
    bdays, d = [], datetime(2026, 10, 12, tzinfo=timezone.utc).date()
    while d <= now.date():
        day0 = datetime(d.year, d.month, d.day, tzinfo=timezone.utc); day1 = day0 + timedelta(days=1)
        closed = now >= day1 + timedelta(hours=3)
        ok = sorted(P(b["at"]) for b in brain if b["ok"] and day0 <= P(b["at"]) < day1)
        bad = [b for b in brain if not b["ok"] and day0 <= P(b["at"]) < day1]
        stale = sum(1 for b in brain if day0 <= P(b["at"]) < day1 for v in b["lakeStates"].values() if v.get("stale"))
        gaps = [(y - x).total_seconds() / 60 for x, y in zip(ok, ok[1:])]
        why = []
        if len(ok) < 23: why.append(f"{len(ok)}/24 successful publishes" + (f" (chain started {ok[0]:%H:%MZ})" if ok and ok[0].hour >= 1 and len(ok) < 23 and d.day == 12 else ""))
        if bad: why.append(f"{len(bad)} failed publish(es)")
        if gaps and max(gaps) > 90: why.append(f"publish gap {max(gaps):.0f} min")
        if stale: why.append(f"{stale} stale state(s)")
        bdays.append({"date": f"{d}", "closed": closed, "okPublishes": len(ok), "failedPublishes": len(bad), "maxGapMin": round(max(gaps), 1) if gaps else None, "staleStates": stale,
                      "valid": closed and not why, "reasons": why if closed else ["day still open"] + why})
        d += timedelta(days=1)
    # summary + projected gates
    import statistics
    first = {}
    for r in led:
        if r["product"] == "NBM" and r["status"] == "complete":
            k = (r["cycle"], r["lake"])
            if k not in first or r["at"] < first[k]:
                first[k] = r["at"]
    lat = sorted((P(v) - P(k[0])).total_seconds() / 3600 for k, v in first.items() if k[0] >= "2026-10-07T05")
    partial_keys = {(r["cycle"], r["lake"]) for r in led if r["product"] == "NBM" and r["status"] == "partial"}
    rtma_fail = [r for r in led if r["product"] == "RTMA-RU" and r["status"] == "failed"]
    nvalid = sum(1 for x in days if x["valid"]); bvalid = sum(1 for x in bdays if x["valid"])
    def gate(valid_days, rows, need=30):
        remaining = need - valid_days
        if remaining <= 0:
            return "reached"
        last = datetime.strptime(rows[-1]["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        open_today = not rows[-1]["closed"]
        # the next days (open day counts if it ends valid) are assumed valid: 30th valid day ends at midnight, verified +3h
        start = last if open_today else last + timedelta(days=1)
        thirtieth = start + timedelta(days=remaining - 1)
        return (thirtieth + timedelta(days=1, hours=3)).strftime("%Y-%m-%dT%H:%MZ")
    summary = {"asOf": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "calendarDate": f"{now.date()}", "validArchiveDays": nvalid, "validBrainPublishDays": bvalid,
               "invalidArchiveDays": [{"date": x["date"], "reasons": x["reasons"]} for x in days if x["closed"] and not x["valid"]],
               "invalidBrainDays": [{"date": x["date"], "reasons": x["reasons"]} for x in bdays if x["closed"] and not x["valid"]],
               "executions": len(exs), "failedExecutions": sum(1 for e in exs if not e["ok"] and e["completed"]),
               "nbmPartialLakeCycles": len(partial_keys), "nbmPartialRecovered": sum(1 for k in partial_keys if k in first),
               "staleStatesLogged": sum(1 for b in brain for v in b["lakeStates"].values() if v.get("stale")), "lakeStatesLogged": sum(len(b["lakeStates"]) for b in brain),
               "freshnessHoursAfterInit": {"n": len(lat), "median": round(statistics.median(lat), 2) if lat else None, "p95": round(lat[int(0.95 * (len(lat) - 1))], 2) if lat else None, "max": round(lat[-1], 2) if lat else None},
               "sourceOutages": {"rtmaFailedAttempts": len(rtma_fail), "nbmFailedAttempts": sum(1 for r in led if r["product"] == "NBM" and r["status"] == "failed"),
                                 "rtmaFailedCycles": sorted({r["cycle"] for r in rtma_fail})},
               "projectedArchiveGate": gate(nvalid, days), "projectedBrainPublishGate": gate(bvalid, bdays),
               "projectionAssumption": "every remaining day (including today) is valid; each invalid day moves the date one day later"}
    return {"asOf": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "summary": summary, "brainDays": bdays, "days": days, "executionsTotal": len(exs), "executionsFailed": sum(1 for e in exs if not e["ok"] and e["completed"]),
            "brainFailures": [b for b in brain if not b["ok"]], "brainOk": sum(b["ok"] for b in brain), "brainFirstOk": next((b["at"] for b in brain if b["ok"]), None)}


if __name__ == "__main__":
    res = audit(sys.argv[1]); json.dump(res, open(sys.argv[2], "w"), indent=1)
    for x in res["days"]:
        print(x["date"], "closed" if x["closed"] else "open", f"nbm {x['nbmPct']:.1%} rtma {x['rtmaPct']:.1%} metar {x['metarObsCount']} maxgap {x['maxStateGapMin']} valid={x['valid']}", x["reasons"])
    print({k: res[k] for k in ("executionsTotal", "executionsFailed", "brainOk", "brainFirstOk")}, len(res["brainFailures"]))
    for b in res["brainDays"]:
        print("brain", b["date"], b["okPublishes"], "valid=" + str(b["valid"]), b["reasons"])
    print(json.dumps(res["summary"], indent=1))
