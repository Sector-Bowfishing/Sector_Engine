"""Photo exemplar kit (pre-registration §5.4; Stage 3A §20-21). Human labels only.

  python -m sector_wind.exemplars add PHOTO --class 3 --texture T3 --lake guntersville --utc 2026-10-12T02:10:00Z --observer mc [--notes ...]
  python -m sector_wind.exemplars review FILE --observer-b jd --class-b 3 [--texture-b T3]
  python -m sector_wind.exemplars status

Rules:
  - Real photographs taken on the water only. No synthetic, generated or stock images. The tool cannot
    verify this; the person adding a photo is attesting to it, and their name is recorded.
  - No automatic (AI) classification. Labels come from people. An exemplar counts only after a second
    observer labels it independently and agrees on the class (`agree = yes`).
  - Photos are copied (never moved) into the class folder; the texture folder gets a link to the same file.
  - Requirement: >= 2 agreed exemplars per class 1-5 (certification data can't count before that), and,
    for the Stage 3 texture rating, >= 2 per texture T1-T4. One photo can count for both."""
from __future__ import annotations

import argparse
import csv
import os
import shutil
from collections import Counter

from .fieldops import FIELD

ROOT = os.path.join(FIELD, "exemplars")
CSV = os.path.join(ROOT, "exemplars.csv")
FIELDS = ["file", "utc", "lake", "lat", "lon", "class", "texture", "observer_a", "observer_b", "agree", "handheld_ms",
          "handheld_height_m", "notes", "class_b", "texture_b", "attested_real_photo", "agreement", "finalLabel", "finalTexture",
          "resolutionNote"]
# observer_a = labeler1, observer_b = labeler2. agreement: AGREED | REVIEW_REQUIRED | RESOLVED. A disagreement is never
# resolved silently: `resolve` needs both labelers' names and a written note, and only then sets finalLabel.
CLASS_DIRS = {1: "class-1-glassy-protected", 2: "class-2-ripple", 3: "class-3-light-chop", 4: "class-4-moderate-chop", 5: "class-5-rough"}
TEXTURE_DIRS = {"T1": "texture-T1-glassy", "T2": "texture-T2-rippled", "T3": "texture-T3-textured", "T4": "texture-T4-broken"}


def _rows():
    if not os.path.exists(CSV):
        return []
    return list(csv.DictReader(open(CSV)))


def _write(rows):
    with open(CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def add(photo, cls, texture, lake, utc, observer, lat="", lon="", notes="", handheld_ms="", handheld_h=""):
    if cls not in CLASS_DIRS or texture not in TEXTURE_DIRS:
        raise ValueError("class must be 1-5 and texture T1-T4")
    if not observer:
        raise ValueError("observer (the person attesting this is a real photo from the water) is required")
    name = os.path.basename(photo)
    dst = os.path.join(ROOT, CLASS_DIRS[cls], name)
    if os.path.exists(dst):
        raise FileExistsError(f"{dst} exists")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(photo, dst)
    tdir = os.path.join(ROOT, TEXTURE_DIRS[texture]); os.makedirs(tdir, exist_ok=True)
    link = os.path.join(tdir, name)
    if not os.path.exists(link):
        os.symlink(os.path.relpath(dst, tdir), link)
    rows = _rows()
    rows.append({"file": os.path.relpath(dst, ROOT), "utc": utc, "lake": lake, "lat": lat, "lon": lon, "class": cls, "texture": texture,
                 "observer_a": observer, "observer_b": "", "agree": "", "handheld_ms": handheld_ms, "handheld_height_m": handheld_h,
                 "notes": notes, "attested_real_photo": observer})
    _write(rows)
    return dst


def review(file, observer_b, class_b, texture_b=""):
    rows = _rows()
    r = next((x for x in rows if x["file"].endswith(file)), None)
    if r is None:
        raise KeyError(file)
    if observer_b == r["observer_a"]:
        raise ValueError("the second label must come from a different person")
    agree = str(class_b) == str(r["class"]) and (not texture_b or texture_b == r["texture"])
    r.update({"observer_b": observer_b, "class_b": class_b, "texture_b": texture_b, "agree": "yes" if agree else "no",
              "agreement": "AGREED" if agree else "REVIEW_REQUIRED",
              "finalLabel": r["class"] if agree else "", "finalTexture": r["texture"] if agree else ""})
    _write(rows)
    return r


def resolve(file, final_class, final_texture, labelers, note):
    """Close a REVIEW_REQUIRED exemplar after both labelers discussed it. Never automatic."""
    rows = _rows()
    r = next((x for x in rows if x["file"].endswith(file)), None)
    if r is None or r.get("agreement") != "REVIEW_REQUIRED":
        raise ValueError("only a REVIEW_REQUIRED exemplar can be resolved")
    if set(labelers) != {r["observer_a"], r["observer_b"]} or not note.strip():
        raise ValueError("resolution needs both labelers by name and a written note")
    r.update({"agreement": "RESOLVED", "finalLabel": str(final_class), "finalTexture": final_texture, "resolutionNote": note})
    _write(rows)
    return r


def status():
    rows = _rows()
    agreed = [r for r in rows if r.get("agreement") in ("AGREED", "RESOLVED") and r.get("finalLabel")]
    cls = Counter(r["finalLabel"] for r in agreed); tex = Counter(r["finalTexture"] for r in agreed if r.get("finalTexture"))
    need_c = {c: max(0, 2 - cls.get(str(c), 0)) for c in CLASS_DIRS}
    need_t = {t: max(0, 2 - tex.get(t, 0)) for t in TEXTURE_DIRS}
    review = [r["file"] for r in rows if r.get("agreement") == "REVIEW_REQUIRED"]
    return {"photos": len(rows), "agreed": len(agreed), "reviewRequired": review,
            "awaitingSecondLabel": sum(not r.get("agreement") for r in rows),
            "classAgreed": {c: cls.get(str(c), 0) for c in CLASS_DIRS}, "textureAgreed": {t: tex.get(t, 0) for t in TEXTURE_DIRS},
            "stillNeeded": {"classes": need_c, "textures": need_t},
            # the set is usable only with no open disagreement
            "complete": all(v == 0 for v in need_c.values()) and not review, "textureComplete": all(v == 0 for v in need_t.values()) and not review}


def main(argv=None):
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["add", "review", "resolve", "status"])
    ap.add_argument("--final-class"); ap.add_argument("--final-texture", default=""); ap.add_argument("--labelers", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("path", nargs="?")
    ap.add_argument("--class", dest="cls", type=int); ap.add_argument("--texture"); ap.add_argument("--lake", default="")
    ap.add_argument("--utc", default=""); ap.add_argument("--observer", default=""); ap.add_argument("--notes", default="")
    ap.add_argument("--lat", default=""); ap.add_argument("--lon", default="")
    ap.add_argument("--handheld-ms", default=""); ap.add_argument("--handheld-height-m", default="")
    ap.add_argument("--observer-b"); ap.add_argument("--class-b"); ap.add_argument("--texture-b", default="")
    a = ap.parse_args(argv)
    if a.cmd == "add":
        print(add(a.path, a.cls, a.texture, a.lake, a.utc, a.observer, a.lat, a.lon, a.notes, a.handheld_ms, a.handheld_height_m))
    elif a.cmd == "review":
        print(json.dumps(review(a.path, a.observer_b, a.class_b, a.texture_b), indent=1))
    elif a.cmd == "resolve":
        print(json.dumps(resolve(a.path, a.final_class, a.final_texture, [x.strip() for x in a.labelers.split(",") if x.strip()], a.note), indent=1))
    else:
        print(json.dumps(status(), indent=1))


if __name__ == "__main__":
    main()
