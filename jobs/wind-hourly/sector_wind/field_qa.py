"""Field record intake, immutability and QA (Stage 3A Track C/D).

  python -m sector_wind.field_qa ingest <export folder> --observer mc --date 2026-10-12   # raw/, read-only, hashed
  python -m sector_wind.field_qa verify                                                   # raw/ unchanged since intake?
  python -m sector_wind.field_qa qa <raw folder>                                          # ELIGIBLE / INELIGIBLE with reasons

Raw exports are never edited: intake copies them once into field/raw/<date>-<observer>/, writes a
SHA-256 manifest and makes every file read-only. QA never repairs a record; it only says whether a
record may be used and why not. Derived files (QA results, predictions) go to field/evaluated/ and can
always be regenerated from raw/."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .fieldops import CANDIDATE, FIELD, NAMES, load_table
from .sample import parse_iso

PROTOCOL_START = datetime(2026, 10, 6, tzinfo=timezone.utc)
FIELD_SCHEMA = "sector-wind-field-v1"
TEXTURES = {"T1", "T2", "T3", "T4"}
PAIR_WINDOW_MIN = 60
SUBDIRS = ["raw", "evaluated", "calibration", "certification", "exemplars", "plans"]


def ensure_layout(root=FIELD):
    for d in SUBDIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    readme = os.path.join(root, "raw", "README.txt")
    if not os.path.exists(readme):
        open(readme, "w").write("Raw field exports. Written once by `field_qa ingest`, hashed, read-only. Never edit.\n"
                                "Everything else (evaluated/, calibration/, certification/) is derived and can be regenerated.\n")


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ingest(src, observer, date, root=FIELD):
    ensure_layout(root)
    dst = os.path.join(root, "raw", f"{date}-{observer}")
    if os.path.exists(dst):
        raise FileExistsError(f"{dst} exists: raw exports are written once. Use a new folder name (e.g. add -2) for a second export.")
    if not os.path.exists(os.path.join(src, "records.jsonl")):
        raise FileNotFoundError("export must contain records.jsonl")
    shutil.copytree(src, dst)
    files = {}
    for dp, _, fs in os.walk(dst):
        for f in fs:
            p = os.path.join(dp, f)
            files[os.path.relpath(p, dst)] = _sha(p)
    man = {"ingestedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": os.path.abspath(src), "files": files}
    json.dump(man, open(os.path.join(dst, "MANIFEST.json"), "w"), indent=1)
    for dp, ds, fs in os.walk(dst):
        for f in fs:
            os.chmod(os.path.join(dp, f), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    for dp, ds, fs in os.walk(dst, topdown=False):
        os.chmod(dp, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    return {"folder": dst, "files": len(files)}


def verify(root=FIELD):
    out = []
    base = os.path.join(root, "raw")
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        man = os.path.join(base, d, "MANIFEST.json")
        if not os.path.exists(man):
            continue
        m = json.load(open(man))
        bad = [f for f, h in m["files"].items() if not os.path.exists(os.path.join(base, d, f)) or _sha(os.path.join(base, d, f)) != h]
        out.append({"folder": d, "files": len(m["files"]), "changedOrMissing": bad})
    return out


def exemplar_set_complete(root=FIELD):
    """Pre-registration §5.4: >= 2 reviewed exemplars per surface class before certification data."""
    p = os.path.join(root, "exemplars", "exemplars.csv")
    if not os.path.exists(p):
        return False
    import csv
    rows = list(csv.DictReader(open(p)))
    ok = defaultdict(int)
    for r in rows:
        if (r.get("reviewed") or "").lower() in ("yes", "true", "1") and r.get("class"):
            ok[r["class"]] += 1
    return all(ok.get(str(c), 0) >= 2 for c in range(1, 6))


def check(r, bank_ids, photo_dir):
    """Every reason a record cannot be used. Empty list = usable."""
    why = []
    if r.get("schema") != FIELD_SCHEMA:
        why.append(f"schema {r.get('schema')!r} != {FIELD_SCHEMA}")
    if r.get("candidateId") != CANDIDATE:
        why.append(f"candidateId {r.get('candidateId')!r} is not {CANDIDATE}")
    lat, lon = r.get("latitude"), r.get("longitude")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        why.append("location missing or invalid")
    try:
        t = parse_iso(r["createdAtUTC"])
        if t < PROTOCOL_START or t > datetime.now(timezone.utc) + timedelta(minutes=5):
            why.append(f"createdAtUTC {r['createdAtUTC']} outside the protocol period")
    except Exception:
        why.append("createdAtUTC missing or not ISO-8601 UTC")
    if r.get("lake") not in NAMES:
        why.append(f"lake {r.get('lake')!r} is not a development lake with a fetch table")
    elif not r.get("bankId"):
        why.append("bank not identified (bankId missing)")
    elif r["bankId"] not in bank_ids.get(r["lake"], set()):
        why.append(f"bankId {r['bankId']} not in the {r['lake']} fetch table")
    if r.get("observedClass") not in (1, 2, 3, 4, 5):
        why.append("observed surface class missing or not 1-5")
    if r.get("observedTexture") not in TEXTURES:
        why.append("observed texture missing (required from Stage 3)")
    if not isinstance(r.get("observerWasBlinded"), bool):
        why.append("blinding state unknown")
    if not isinstance(r.get("tags"), list):
        why.append("practice status unknown (tags field missing)")
    role, pid = r.get("pairRole"), r.get("pairId")
    if pid and role not in ("A", "B"):
        why.append(f"pairId set but pairRole {role!r} is not A/B")
    if role in ("A", "B") and not pid:
        why.append("pairRole A/B without a pairId")
    for f in r.get("photoFiles") or []:
        if not os.path.exists(os.path.join(photo_dir, f)):
            why.append(f"photo {f} referenced but not in the export")
    h = r.get("handheld")
    if h is not None:
        if not isinstance(h.get("heightM"), (int, float)) or h["heightM"] <= 0:
            why.append("handheld wind without a sensor height")
        if h.get("speedMS") is None:
            why.append("handheld record without speed")
    sid = r.get("sessionId") or ""
    if r.get("lake") and not sid.startswith(f"{r['lake']}|"):
        why.append("sessionId does not start with the lake")
    return why


def qa(raw_dir, root=FIELD):
    recs = [json.loads(l) for l in open(os.path.join(raw_dir, "records.jsonl")) if l.strip()]
    bank_ids = {lk: {b["id"] for b in load_table(lk)[0]["banks"]} for lk in {r.get("lake") for r in recs} if lk in NAMES}
    photo_dir = os.path.join(raw_dir, "photos")
    exemplars_ok = exemplar_set_complete(root)
    by_pair = defaultdict(list)
    for r in recs:
        if r.get("pairId"):
            by_pair[(r.get("sessionId"), r["pairId"])].append(r)
    out = []
    for r in recs:
        why = check(r, bank_ids, photo_dir)
        if r.get("pairId"):
            mates = by_pair[(r.get("sessionId"), r["pairId"])]
            roles = sorted(m.get("pairRole") for m in mates)
            if roles != ["A", "B"]:
                why.append(f"pair {r['pairId']} has roles {roles}, needs exactly one A and one B")
            else:
                try:
                    ts = sorted(parse_iso(m["createdAtUTC"]) for m in mates)
                    if (ts[1] - ts[0]) > timedelta(minutes=PAIR_WINDOW_MIN):
                        why.append(f"pair banks visited {int((ts[1] - ts[0]).total_seconds() // 60)} min apart (> {PAIR_WINDOW_MIN})")
                except Exception:
                    pass
        practice = "practice" in (r.get("tags") or [])
        if why:
            st = "INELIGIBLE"
        elif practice:
            st = "PRACTICE"
        else:
            st = "ELIGIBLE"
        note = None
        if st == "ELIGIBLE" and not exemplars_ok:
            note = "calibration-only: collected before the photo exemplar set was complete (pre-registration §5.4)"
        out.append({"recordId": r.get("id"), "sessionId": r.get("sessionId"), "status": st, "reasons": why, "note": note})
    ensure_layout(root)
    name = os.path.basename(os.path.normpath(raw_dir))
    with open(os.path.join(root, "evaluated", f"{name}.qa.jsonl"), "w") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["layout", "ingest", "verify", "qa"])
    ap.add_argument("path", nargs="?")
    ap.add_argument("--observer"); ap.add_argument("--date")
    a = ap.parse_args(argv)
    if a.cmd == "layout":
        ensure_layout(); print(f"layout ok under {FIELD}")
    elif a.cmd == "ingest":
        print(json.dumps(ingest(a.path, a.observer, a.date), indent=1))
    elif a.cmd == "verify":
        print(json.dumps(verify(), indent=1))
    else:
        res = qa(a.path)
        from collections import Counter
        print(json.dumps({"counts": Counter(r["status"] for r in res), "ineligible": [r for r in res if r["status"] == "INELIGIBLE"]}, indent=1))


if __name__ == "__main__":
    main()
