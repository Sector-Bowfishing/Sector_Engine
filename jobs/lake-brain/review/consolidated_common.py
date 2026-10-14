"""Shared constants and helpers of the consolidated (individually reviewed) binding review: the pack builder, the HTML form and the ingest all
import this, so the decision vocabulary, the row fingerprint and the file names cannot drift apart.

The consolidated review is the INDIVIDUAL path: every lake is accepted by Michael personally, one row at a time. Nothing is extrapolated from a
sample (that is the other path, ingest_review_result.py). See README in the packet and the module docstring of ingest_batch_review.py.
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(HERE, "..", "data"))
BATCH_DIR = os.path.join(DATA_DIR, "review_batches")
BINDINGS = os.path.join(DATA_DIR, "bindings.proposed.v1.json")

DECISIONS = ("ACCEPT", "REJECT", "NEEDS REVIEW")          # the only decisions Michael can give
UNDECIDED = ("", "PENDING")
SECTION_A, SECTION_B = "A", "B"
PACK_PREFIX = "LBR-CONSOLIDATED-"
SCHEMA_PACK = "lake-brain-consolidated-review-pack/v1"
SCHEMA_RESULT = "lake-brain-individual-review-result/v1"
RESULT_BASENAME = "consolidated_result.json"
PILOT_COUNT = 5                                            # the REVIEWED pilot bindings today
COVERAGE_THRESHOLD = 63                                    # 10 % of 621 directory lakes, profiled lakes needed for the next coverage step
NEEDED_ACCEPTS = COVERAGE_THRESHOLD - PILOT_COUNT          # 58
CRITERIA_VERSION = "binding-review-v1"                     # same rules as the sample path; individually reviewed
REVIEW_KIND = "individual-cumulative"

# Fields the packet locks per row; the reviewer's export must carry them unchanged (tamper check in the ingest).
LOCKED_COLUMNS = ("section", "lake_name", "state", "provider", "provider_identifier", "computer_recommendation", "row_digest")
EXPORT_COLUMNS = ("pack_id", "section", "lake_id", "lake_name", "state", "provider", "provider_identifier", "computer_recommendation", "row_digest",
                  "decision", "notes", "decided_at_utc", "reviewer", "exported_at_utc")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def row_digest(core):
    """Fingerprint of what the reviewer was shown as the binding: lake, section, source identity and the computer's recommendation."""
    keys = ("id", "section", "name", "state", "provider", "identifier", "station", "series", "recommendation")
    return sha256_text(json.dumps({k: core[k] for k in keys}, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def pack_id_for(rows, seed):
    h = sha256_text(str(seed) + "|" + ",".join(sorted(f"{r['section']}|{r['id']}|{r['digest']}" for r in rows)))[:10]
    return PACK_PREFIX + h
