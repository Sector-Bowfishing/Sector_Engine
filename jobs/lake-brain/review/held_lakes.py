"""Hold-back lists shared by the pack builder and the ingestion script, so a held lake can never reach accepted_batch.json.

Held = machine-verified strict rows that must NOT be promoted yet:
  * SERIES_MISMATCH (this file): the history series differs from the live binding by more than 15 ft (datum/series mismatch). Found by the
    rules-v2 hold-out QA: Sector_Engine-lake-rules-v2/jobs/lake-brain/validation/results/holdout_v2_results.json, seriesQa.mismatchOver15ft.
  * COORDINATE_FLAG: directory coordinate flagged identity_risk / off_water in geometry/lake_geometry_flags.csv. Those ids come from research
    data, so the builder snapshots them into held_lakes.json (committed next to this file) every time the pack is built.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SERIES_MISMATCH_REASON = ("history series differs from the live binding by more than 15 ft - datum/series mismatch pending resolution "
                          "(found by the rules-v2 hold-out QA: holdout_v2_results.json, seriesQa.mismatchOver15ft)")
SERIES_MISMATCH = frozenset({
    "Bartlett|AZ", "Blue Mesa Reservoir|CO", "Buffalo Bill Reservoir|WY", "Canyon Lake|TX", "Detroit Lake|OR", "Glendo Reservoir|WY",
    "Jackson Lake|WY", "Jordanelle Reservoir|UT", "Lake Koocanusa|MT", "Lake Shelbyville|IL", "Lake Taneycomo|MO", "Navajo Reservoir|NM",
    "Pineview Reservoir|UT", "Rend Lake|IL",
})
TERMS_PROVIDERS = frozenset({"sjrwmd", "nhdes"})
TERMS_REASON = "provider terms unconfirmed (St. Johns River WMD / NH DES): skip unclear operator endpoints unless terms are confirmed"
SNAPSHOT_FILE = os.path.join(HERE, "held_lakes.json")


def load_snapshot(path=SNAPSHOT_FILE):
    """All held lake ids known to the repository: the series-mismatch list plus the coordinate-flag snapshot written by the builder."""
    ids = set(SERIES_MISMATCH)
    if os.path.exists(path):
        d = json.load(open(path))
        ids |= set(d.get("coordinateFlagged", [])) | set(d.get("seriesMismatch", [])) | set(d.get("providerTerms", []))
    return ids
