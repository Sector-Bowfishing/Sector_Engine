"""Cortex 2.2 Firebase data audit (FD-01..FD-14): the production Brain RTDB shape, as recorded in a value-free inventory, against the
Engine's own contracts. Offline, stdlib + pytest; no credentials, no network, no production access.

* every production path family is classified (KEEP / LEGACY / ORPHANED / ...) and its declared writer is the one the ownership table allows
* Brain ids are canonical everywhere (no /brains/fish, no aliases); Vegetation's absence is INACTIVE_EXPECTED
* score authority: only the platform scorer may write /scores and the /engine/score alias
* orphaned rollup parents are writable by nobody and ignored by the control rollup
* the inventory itself carries no values or identifiers
"""
import datetime as dt
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))
sys.path.insert(0, os.path.dirname(HERE))
from sector_brain_platform import ownership  # noqa: E402
from sector_brain_platform.control import fleet_rollup, slot_max_age  # noqa: E402
from sector_brain_platform.keys import BRAINS  # noqa: E402
import path_inventory  # noqa: E402

INVENTORY = json.load(open(os.path.join(HERE, "fixtures", "production-path-inventory-2026-10-21.json")))
PATHS = INVENTORY["paths"]
FAMILIES = json.load(open(os.path.join(HERE, "path_families.json")))
LIVE_BRAINS = sorted(b for b in BRAINS if b != "vegetation")
ALIASES = {"fish", "biological-brain", "biological", "bio", "lake", "intelligence", "clarity", "water-temperature", "watertemp", "temperature"}
SAMPLE = {"{k}": "Lake_X_ZZ", "{id}": "species_x", "{uid}": "uid0", "{event}": "20261021T000000Z-{brain}-1", "{source}": "x-source",
          "{job}": "x-job", "{execution}": "x-exec"}


def _expand(pattern: str, writer: str = ""):
    """Family pattern -> [(brain, concrete path)] for every Brain the pattern (or its writer) ranges over."""
    out = []
    brains = LIVE_BRAINS if any(x in pattern + writer for x in ("{brain}", "{slot}", "{snapshotField}")) else [None]
    for b in brains:
        p = pattern
        if b:
            p = p.replace("{brain}", b).replace("{slot}", BRAINS[b][0]).replace("{snapshotField}", BRAINS[b][1])
        for ph, v in SAMPLE.items():
            p = p.replace(ph, v.replace("{brain}", b or "brain-platform"))
        out.append((b, p))
    return out


def _family_regex(pattern: str) -> re.Pattern:
    slots = "|".join(BRAINS[b][0] for b in BRAINS)
    fields = "|".join(BRAINS[b][1] for b in BRAINS)
    rx = re.escape(pattern)
    for ph, sub in {"{brain}": "|".join(map(re.escape, BRAINS)), "{slot}": slots, "{snapshotField}": fields}.items():
        rx = rx.replace(re.escape(ph), f"(?:{sub})")
    for ph in ("{k}", "{id}", "{uid}", "{event}", "{source}", "{job}", "{execution}"):
        rx = rx.replace(re.escape(ph), r"[^/]+")
    return re.compile(rx + r"(?:/.*)?$")


def classify(path: str):
    best = None
    for f in FAMILIES["families"]:
        if _family_regex(f["path"]).match(path) and (best is None or len(f["path"]) > len(best["path"])):
            best = f
    return best


# ---- inventory hygiene ------------------------------------------------------------------------------------
def test_inventory_is_value_free():
    text = json.dumps(INVENTORY)
    for rx in (r"gs://", r"\d{4}-\d{2}-\d{2}T", r"@", r"sha256:", r"_(AL|SC|TN|GA|KY|NC|VA|MS|TX|OK|AR|MO|LA|FL)\b"):
        assert not re.search(rx, text), rx
    for p, meta in PATHS.items():
        assert set(meta) <= {"count", "types"}, p


def test_inventory_generator_masks_identifiers_and_values():
    export = {"lakes": {"Some_Lake_AL": {"speciesPresence": {"rare_fish": {"sourceRef": "gs://private/x"}}, "states": {"wind": {"v": 3}}}},
              "species": {"rare_fish": {"name": "secret"}}, "access": {"opsUsers": {"UIDabcdefghijklmnopqrstu": True}},
              "control": {"beta": {"Some_Lake_AL": {"x": 1}}}}
    text = json.dumps(path_inventory.inventory(export))
    for leaked in ("Some_Lake_AL", "rare_fish", "UIDabcdefghijklmnopqrstu", "gs://", "secret"):
        assert leaked not in text
    assert "/lakes/{k}/speciesPresence/{id}/sourceRef" in text and "/control/beta/{k}" in text


# ---- classification ---------------------------------------------------------------------------------------
def test_every_production_path_is_classified():
    roots = {"/access", "/activity", "/brains", "/control", "/engine", "/health", "/jobs", "/lakeFleet", "/lakes", "/scores", "/snapshots",
             "/sources", "/species", "/validation"}
    unclassified = sorted(p for p in PATHS if p not in roots and p.count("/") >= 2 and classify(p) is None
                          and not re.fullmatch(r"/(lakeFleet|lakes|snapshots|control/fleet)/\{k\}|/snapshots/\{k\}/latest|/(health|control)/[A-Za-z]+"
                                               r"|/access/opsUsers|/(lakeFleet/\{k\}/(slots|readiness|modelVersions)|lakes/\{k\}/(states|profiles|validation)"
                                               r"|snapshots/\{k\}/latest/brainVersions)", p))
    assert not unclassified, unclassified[:20]


def test_family_writers_match_the_ownership_table():
    bad = []
    for f in FAMILIES["families"]:
        w = f["writer"]
        if w in ("external",):
            continue
        for brain, path in _expand(f["path"], w):
            if w == "nobody":
                writers = [b for b in list(BRAINS) + [ownership.PLATFORM_WRITER] if ownership.path_allowed(b, path)]
                if writers:
                    bad.append((path, "nobody", writers))
                continue
            ids = [x for x in w.split("|")]
            ids = [brain if x == "{brain}" else x for x in ids]
            if not any(ownership.path_allowed(i, path) for i in ids if i):
                bad.append((path, ids, "denied"))
            others = [b for b in LIVE_BRAINS if b not in ids and ownership.path_allowed(b, path)
                      and not path.startswith(("/activity/", "/sources/", "/health/sources/", "/health/jobs/", "/lakeFleet/Lake_X_ZZ/lakeId",
                                               "/snapshots/Lake_X_ZZ/latest/lakeId"))]
            if others:
                bad.append((path, ids, f"also writable by {others}"))
    assert not bad, bad


def test_brain_publish_declarations_land_in_classified_families_owned_by_that_brain():
    bad = []
    for b in BRAINS:
        manifest = json.load(open(os.path.join(ROOT, "brains", {"biological-state": "fish", "lake-brain": "lake", "water-temp": "water-temperature"}
                                                .get(b, b), "brain.json")))
        for fam in (p for x in manifest.get("publishes", []) for p in x.get("pathFamilies", [])):
            concrete = fam.replace("{k}", "Lake_X_ZZ").replace("{id}", "x-source" if "sources" in fam else "species_x") \
                          .replace("{event}", f"20261021T000000Z-{b}-1") \
                          .replace("{child}", "riverSystem" if fam.startswith("/lakeFleet/{k}/{child}") else "status")
            if not ownership.path_allowed(b, concrete):
                bad.append((b, fam))
    assert not bad, bad


# ---- Brain identity ---------------------------------------------------------------------------------------
def test_brain_ids_are_canonical_in_every_brain_keyed_collection():
    for root in ("/brains/", "/validation/", "/health/brains/", "/scores/"):
        keys = {p[len(root):].split("/")[0] for p in PATHS if p.startswith(root)}
        allowed = set(BRAINS) | ({"engine"} if root == "/scores/" else set())
        assert keys <= allowed, (root, keys - allowed)
        assert not keys & ALIASES, (root, keys & ALIASES)


def test_fish_is_published_under_its_canonical_id_only():
    assert "/brains/biological-state" in PATHS and "/species/{id}" in PATHS
    assert not any(p.startswith(("/brains/fish", "/brains/biological-brain")) for p in PATHS)
    assert not ownership.path_allowed("biological-state", "brains/fish/status")


def test_lake_slots_and_snapshot_fields_are_registered_names():
    slots, fields = {v[0] for v in BRAINS.values()}, {v[1] for v in BRAINS.values()}
    for p in PATHS:
        m = re.match(r"/lakes/\{k\}/(states|profiles)/([^/]+)$", p) or re.match(r"/lakeFleet/\{k\}/(slots|readiness|modelVersions)/([^/]+)$", p)
        if m:
            assert m.group(2) in slots, p
        m = re.match(r"/snapshots/\{k\}/latest/([^/]+)$", p)
        if m and m.group(1) not in ("lakeId", "brainVersions", "generatedAt", "snapshotVersion"):
            assert m.group(1) in fields, p


def test_expected_absences_are_absent_and_classified():
    for a in FAMILIES["expectedAbsences"]:
        assert not any(p == a["path"] or p.startswith(a["path"] + "/") for p in PATHS), a["path"]
        assert a["state"] in ("INACTIVE_EXPECTED", "PUBLICATION_INACTIVE", "NOT_REGISTERED")


def test_vegetation_absence_is_inactive_expected_not_a_missing_writer():
    manifest = json.load(open(os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))
    veg = manifest["brains"]["vegetation"]
    assert veg["activityState"] == "PARKED" and veg["executionTarget"]["kind"] == "none" and veg["customerPublication"] is False
    assert {a["path"]: a["state"] for a in FAMILIES["expectedAbsences"]}["/brains/vegetation"] == "INACTIVE_EXPECTED"
    assert "/control/healthV1/brains/vegetation" in PATHS          # the control plane still reports the parked Brain


# ---- score authority --------------------------------------------------------------------------------------
@pytest.mark.parametrize("path", ["scores/wind", "scores/engine", "engine/score", "scores/biological-state/value"])
def test_only_the_platform_scorer_may_write_scores(path):
    assert ownership.path_allowed(ownership.PLATFORM_WRITER, path)
    assert not [b for b in BRAINS if ownership.path_allowed(b, path)]


def test_no_brain_runtime_writes_the_scores_roots():
    rx = re.compile(r"""["'/](scores|engine/score)/?[{"'A-Za-z]""")
    hits = []
    for base, _, files in os.walk(os.path.join(ROOT, "brains")):
        if "/tests" in base or "/Tests" in base or "/research/" in base + "/":
            continue
        for f in files:
            if f.endswith((".py", ".swift")) and not f.startswith("test_"):
                for i, line in enumerate(open(os.path.join(base, f), encoding="utf-8", errors="replace"), 1):
                    if rx.search(line) and re.search(r"(patch|update|set|write|\]\s*=)", line) and "brains/" not in line.split("scores")[0][-8:]:
                        hits.append(f"{os.path.relpath(os.path.join(base, f), ROOT)}:{i}")
    assert not hits, hits


def test_wind_registry_score_copy_is_classified_legacy_duplicate():
    """The one known Brain-written score copy (FD-09): /brains/wind/scores. Classified, not authoritative, with its consumer named."""
    f = classify("/brains/wind/scores")
    assert f["status"] == "DUPLICATED" and f.get("classification") == "LEGACY" and f["readers"]
    assert classify("/scores/wind")["status"] == "KEEP"
    assert classify("/engine/score")["status"] == "DUPLICATED" and classify("/scores/engine")["status"] == "KEEP"


# ---- staleness and orphaned parents ------------------------------------------------------------------------
def test_orphaned_rollup_parents_are_writable_by_nobody():
    for path in ("lakeFleet/Lake_X_ZZ/lastUpdatedAt", "snapshots/Lake_X_ZZ/latest/generatedAt", "snapshots/Lake_X_ZZ/latest/snapshotVersion"):
        assert not [b for b in list(BRAINS) + [ownership.PLATFORM_WRITER] if ownership.path_allowed(b, path)], path
        assert classify("/" + path)["status"] == "ORPHANED"


def test_control_rollup_ignores_the_frozen_parent_timestamp():
    now = dt.datetime(2026, 10, 21, 15, tzinfo=dt.timezone.utc)
    row = {"lakeId": "x", "lastUpdatedAt": "2026-10-12T00:00:00Z",
           "slots": {"wind": {"generatedAt": "2026-10-21T14:00:00Z", "stale": False}, "waterClarity": {"generatedAt": "2026-10-12T09:00:00Z", "stale": False}}}
    r = fleet_rollup("x", row, now)
    assert r["lastUpdatedAt"] == "2026-10-21T14:00:00Z"
    row["lastUpdatedAt"] = "2099-01-01T00:00:00Z"
    assert fleet_rollup("x", row, now)["lastUpdatedAt"] == "2026-10-21T14:00:00Z"


def test_write_time_stale_flag_no_longer_hides_old_data_in_the_rollup():
    """A paused Brain leaves `stale: false` on old data (export: Clarity, all 621 lakes, 109-224 h old). With the Brains' freshness policy the
    platform rollup marks it stale by AGE (2026-10-21 remediation); without a policy only the persisted flag counts (old behaviour)."""
    now = dt.datetime(2026, 10, 21, 15, tzinfo=dt.timezone.utc)
    row = {"lakeId": "x", "slots": {"waterClarity": {"generatedAt": "2026-10-12T09:00:00Z", "stale": False}}}
    assert fleet_rollup("x", row, now)["stale"] is False
    r = fleet_rollup("x", row, now, slot_max_age(None, {"water-clarity": {"staleAfterHours": 26}}))
    assert r["stale"] is True and r["staleSlots"] == {"waterClarity": "AGE"}
    assert "write-time" in classify("/lakeFleet/{k}/slots/waterClarity")["freshness"]


def test_production_registry_children_are_inside_the_publisher_contract():
    """Audit E-8 / C-8: every child a Brain has in production /brains/{id} is a declared registry child (Publisher cutover would refuse others)."""
    from sector_brain_platform.publisher import registry as REG
    declared = {"wind": REG.WIND_REGISTRY_CHILDREN, "biological-state": REG.FISH_REGISTRY_CHILDREN, "water-clarity": REG.CLARITY_REGISTRY_CHILDREN,
                "sector-intelligence": REG.INTELLIGENCE_REGISTRY_CHILDREN, "lake-brain": REG.LAKE_REGISTRY_CHILDREN,
                "water-temp": REG.WATER_TEMP_REGISTRY_CHILDREN, "depth": REG.DEPTH_REGISTRY_CHILDREN}
    bad = {}
    for b, groups in declared.items():
        flat = {c for g in (groups.values() if isinstance(groups, dict) else [groups]) for c in g}
        prod = {p.split("/")[3] for p in PATHS if p.startswith(f"/brains/{b}/") and p.count("/") >= 3}
        if prod - flat:
            bad[b] = sorted(prod - flat)
    assert not bad, bad
