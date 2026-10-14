"""SYNTHETIC helpers for the consolidated-review tests. Every lake here is 'Synth <n> Lake|ZZ'; nothing real, nothing written outside tmp_path."""
import copy
import csv
import json
import os

import build_consolidated_pack as C
import consolidated_common as CC

RULES = [dict(id=f"R{i}", name=n, res="PASS", meaning=f"{n} ok") for i, n in
         enumerate(["Position", "Identity", "Not a trap", "State", "Unique", "Live", "Level", "Datum", "Agreement"], 1)]
RULES[8]["res"] = "n-a"


def mk_row(i, provider="a2w", state="ZZ", **over):
    lid = f"Synth {i} Lake|{state}"
    row = dict(
        seq=i, id=lid, name=f"Synth {i} Lake", state=state, kind="sample", provider=provider, capability="DIRECT_OPERATOR_POOL", capPlain="the dam operator's own pool-level feed",
        operator="USACE Synth", wave="w1", sourceLabel="x", sourceId=f"{provider}: ST{i}", station=f"ST{i}", series="Elev", stationName=f"Synth {i} Lake Dam",
        links=[dict(l="gauge page", u=f"https://example.invalid/{i}")], lake=dict(lat=40.0, lon=-100.0, map=dict(l="Map", u="https://example.invalid/m")),
        gauge=dict(lat=40.0, lon=-100.0, map=dict(l="Map", u="https://example.invalid/g")),
        dist=dict(m=0.0, km=0.0, outline=True, text="inside the lake outline"), nameMatch=dict(lake=f"Synth {i} Lake", station=f"Synth {i} Lake Dam", sim=1.0),
        level=dict(lastFt=1000.0, medFt=1000.5, obsUtc="2026-10-13T05:00:00Z", ageH=2.0, snapshot="2026-10-13"),
        pool=dict(ft=1001.0, conf="high", basis="fullPool", diff=-0.5, diffNow=-1.0),
        second=None, alsoAgrees=[], rules=copy.deepcopy(RULES), nid=dict(id="X", name="Synth Dam", score=100.0, distM=10.0, linked=True),
        history=dict(years=20, first=2005, cls="SUFFICIENT", series="cwms:x"), pointFlag="ok", pointWhy="", checks="R1,R2,R3,R4,R5,R6,R8,R7=strong", status="VERIFIED",
        r7class="strong", rec="PASS", recReasons=["all checks pass"], recNotes=["single agency only (no independent second source)"],
    )
    row.update(over)
    return row


def mk_binding(row, **over):
    b = dict(lakeId=row["id"], status="MACHINE_VERIFIED", capability=row["capability"], provider=row["provider"], researchProvider=row["provider"], station=row["station"],
             series=row["series"], live=[dict(provider=row["provider"], station=row["station"], series=row["series"], datumOffsetFt=0.0)], history=[],
             historyCompleteYears=20, historyClass="SUFFICIENT", historyFirstYear=2005, historyBasis="base", historyNotes=[], context=dict(region=dict(value="W")))
    b.update(over)
    return b


def mk_reg(**over):
    r = dict(geometryConfidence=dict(level="HIGH", score=0.95), pointFlag="ok", memberIds=[], areaKm2=10.0)
    r.update(over)
    return r


def mk_world(n=10, providers=("a2w", "cwms", "usgs", "rise"), pilots=(), held=(), coord=(), sample=()):
    """n qualifying rows (cycling providers) + the context for them."""
    rows, table, reg = {}, {}, {}
    for i in range(1, n + 1):
        r = mk_row(i, provider=providers[i % len(providers)], state=["AA", "BB", "CC", "DD", "EE"][i % 5])
        rows[r["id"]] = r
        table[r["id"]] = mk_binding(r)
        reg[r["id"]] = mk_reg()
    ctx = C.Ctx(table, pilots, held, coord, sample, reg, {l: 5 for l in rows}, {})
    return rows, ctx


def write_manifest_and_export(tmp, rows_a, rows_b=(), pack_suffix="TEST000001", decision_of=lambda sec, lid: "ACCEPT", table_ids=None, in_table_b=(), held=(), pilots=()):
    """A synthetic packet manifest + the export the review form would download. Returns (manifest_path, export_path, manifest, export_rows)."""
    mrows = []
    for sec, rows in ((CC.SECTION_A, rows_a), (CC.SECTION_B, rows_b)):
        for i, r in enumerate(rows, 1):
            core = dict(id=r["id"], section=sec, name=r["name"], state=r["state"], provider=r["provider"], identifier=r["sourceId"], station=r["station"],
                        series=r["series"], recommendation=r["rec"])
            mrows.append(dict(section=sec, id=r["id"], seq=i, digest=CC.row_digest(core), name=r["name"], state=r["state"], provider=r["provider"],
                              identifier=r["sourceId"], recommendation=r["rec"], inBindingsTable=sec == "A"))
    pack_id = CC.PACK_PREFIX + pack_suffix
    manifest = dict(schema=CC.SCHEMA_PACK, packId=pack_id, selectionRule="test", decisions=list(CC.DECISIONS), pilots=sorted(pilots), held=sorted(held), rows=mrows,
                    inputs=dict(bindingsTableSha256=None))
    mp = os.path.join(str(tmp), f"pack_manifest_{pack_suffix}.json")
    json.dump(manifest, open(mp, "w"), indent=1)
    erows = []
    for m in mrows:
        erows.append({"pack_id": pack_id, "section": m["section"], "lake_id": m["id"], "lake_name": m["name"], "state": m["state"], "provider": m["provider"],
                      "provider_identifier": m["identifier"], "computer_recommendation": m["recommendation"], "row_digest": m["digest"],
                      "decision": decision_of(m["section"], m["id"]), "notes": "", "decided_at_utc": "2026-10-14T10:00:00Z", "reviewer": "Michael",
                      "exported_at_utc": "2026-10-14T11:00:00Z"})
    ep = os.path.join(str(tmp), f"export_{pack_suffix}.csv")
    write_export(ep, erows)
    return mp, ep, manifest, erows


def write_export(path, erows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(CC.EXPORT_COLUMNS))
        w.writeheader()
        for r in erows:
            w.writerow(r)


def write_table(path, lake_ids, pilots=(), extra=None):
    doc = dict(schema="lake-brain-bindings-proposed/v1", pilotReproduction=[dict(lakeId=p) for p in pilots],
               bindings=[dict(lakeId=l, status="MACHINE_VERIFIED", provider="a2w", capability="DIRECT_OPERATOR_POOL") for l in lake_ids])
    if extra:
        doc["bindings"] += extra
    json.dump(doc, open(path, "w"), indent=1)
    return path
