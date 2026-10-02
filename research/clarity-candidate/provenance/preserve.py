"""Copy the frozen Current Clarity research (Stages 10-18 chain) out of the scratchpad into the engine repo.
  python preserve.py DEST
Writes DEST/<same layout as the scratchpad>, rewrites the scratchpad path (reversibly) in .py/.sh files,
and writes DEST/provenance/{MANIFEST.sha256, PATH_REWRITES.json, FROZEN_HASH_CHECK.json}."""
import hashlib, json, os, re, shutil, sys

S = "/private/tmp/claude-501/-Users-mcather-Desktop-Development-iOS-Sector/ea2965be-d6fb-4701-8a4d-c2ceb08213d8/scratchpad"
FUSION = os.path.expanduser("~/Desktop/Development/Sector_Engine-fusion")
DEST = os.path.abspath(sys.argv[1])

SKIP_DIRS = {"__pycache__", "work", "safe_cache", "venv", "src", ".git", "ac", "tandem", "survey", "dryrun", "_s7_check", "_s8_check", "c2rcc"}
SKIP_EXT = {".pyc", ".log", ".xcresult"}
INCLUDE = [
    "stage10", "stage11/analysis", "stage11/corpus", "stage11/multisensor", "stage11/temporal", "stage11/tools",
    "stage11/FREEZE_STAGE11.json", "stage11/PREREGISTRATION_STAGE11.md", "stage11/CURRENT_CLARITY_STAGE11_REFLECTANCE_AND_SENSOR_AUDIT.md",
    "stage12", "stage13", "stage14", "stage15", "stage16", "stage17", "stage18",
    "q9/wqp/secchi.csv", "q9/wqp/turbidity.csv", "q9/wqp/sites.csv", "q9/wqp/secchi_censored.csv",
    "stage6/extract.py", "stage6/PREREGISTRATION.md", "stage8/g2026_secchi.csv", "stage8/PREREGISTRATION.md", "stage9/PREREGISTRATION.md",
    "q9/README.md", "q9/build.py", "q9/download.py", "q9/build_stats.json", "q9/report.json", "q9/report.py", "q9/flag_review.tsv",
]
# The engine files the research imported from the Sector_Engine-fusion worktree (feat/clarity-algal-warning).
VENDOR = ["jobs/lake-surface", "docs/data/hydrology/guntersville/guntersville.arm_cells.json",
          "docs/data/hydrology/guntersville/stage3a/arm_positions.npz", "docs/data/hydrology/guntersville/stage3a/arm_zones.json"]

P = S
R1 = ('"' + P, '__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "')
R3 = ('os.path.expanduser("~/Desktop/Development/Sector_Engine-fusion', 'os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion')
R2 = (P, "$CLARITY_RESEARCH_ROOT")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def rewrite(data):
    for a, b in (R3, R1, R2): data = data.replace(a.encode(), b.encode())
    return data


def unrewrite(data):
    for a, b in (R3, R1, R2): data = data.replace(b.encode(), a.encode())
    return data


def files_under(rel):
    src = os.path.join(S, rel)
    if os.path.isfile(src): yield rel; return
    for root, dirs, fs in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(".xcresult"))
        for f in sorted(fs):
            if os.path.splitext(f)[1] in SKIP_EXT or f == ".DS_Store": continue
            yield os.path.relpath(os.path.join(root, f), S)


copied, rewrites = {}, {}
for rel in INCLUDE:
    for r in files_under(rel):
        if "stage11/tools/acolite/src" in r or "stage11/tools/acolite/venv" in r: continue
        dst = os.path.join(DEST, r); os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = os.path.join(S, r)
        if r.endswith((".py", ".sh")):
            t = open(src, "rb").read(); n = rewrite(t)
            open(dst, "wb").write(n)
            if n != t:
                assert unrewrite(n) == t, r
                rewrites[r] = {"original_sha256": sha(src), "preserved_sha256": sha(dst)}
        else:
            shutil.copy2(src, dst)
        copied[r] = sha(src)
for rel in VENDOR:
    src = os.path.join(FUSION, rel)
    items = [rel] if os.path.isfile(src) else [os.path.relpath(os.path.join(a, f), FUSION) for a, d, fs in os.walk(src) for f in fs
                                               if "__pycache__" not in a and not f.endswith(".pyc")]
    for r in items:
        dst = os.path.join(DEST, "vendor/Sector_Engine-fusion", r); os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(FUSION, r), dst); copied["vendor/Sector_Engine-fusion/" + r] = sha(dst)

# ---- every hash recorded in a freeze file, checked against the scratchpad and the preserved copy
HEX = re.compile(r"[0-9a-f]{64}")


def resolve(key, fdir):
    k = re.sub(r"\s*\(.*\)$", "", key.strip())
    if k.startswith("engine "):
        k = k[7:].replace(".../", "docs/data/hydrology/guntersville/")
        return "vendor/Sector_Engine-fusion/" + k, os.path.join(FUSION, k)
    for base in (S, os.path.join(S, fdir)):
        p = os.path.normpath(os.path.join(base, k))
        if os.path.exists(p): return os.path.relpath(p, S), p
    if k:
        b = os.path.basename(k)
        for d in ("stage11/corpus", "stage11/tools/aw", fdir):
            p = os.path.join(S, d, b)
            if os.path.isfile(p): return os.path.relpath(p, S), p
    return None, None


checks = []
freeze_files = ["stage10/FREEZE.json", "stage10/frozen_manifest.json"] + [f"stage{n}/FREEZE_STAGE{n}.json" for n in range(11, 19)]
for ff in freeze_files:
    d = json.load(open(os.path.join(S, ff))); fdir = os.path.dirname(ff)

    def walk(x, path, parent):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, path + [str(k)], x)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, path + [i], x)
        elif isinstance(x, str) and HEX.fullmatch(x):
            key = None
            if len(path) >= 2 and path[-2] in ("files", "tables_sha256"): key = path[-1]
            elif path == ["blind_sample13", "sha256"]: key = "stage13/cert/blind_sample13.csv"
            elif isinstance(parent, dict):
                key = parent.get("file") or parent.get("path") or (path[-1].replace(" sha256", "") if isinstance(path[-1], str) and path[-1].endswith(" sha256") else None)
            rel, src = resolve(key, fdir) if key else (None, None)
            rec = {"freeze": ff, "entry": "/".join(map(str, path)), "file": rel, "frozen_sha256": x}
            if src and os.path.isfile(src):
                rec["scratchpad_sha256"] = sha(src)
                dst = os.path.join(DEST, rel)
                if os.path.exists(dst):
                    rec["preserved"] = True
                    rec["preserved_original_bytes_sha256"] = hashlib.sha256(unrewrite(open(dst, "rb").read())).hexdigest() if rel.endswith((".py", ".sh")) else sha(dst)
                else:
                    rec["preserved"] = False
            NOTES = {"manifestSha256": "hash of frozen_manifest.json content in canonical form (checked separately)",
                     "eligible_file_list_sha256": "hash of the eligible-file list, not a file",
                     "part1_result/score_sha256": "hash of the Part 1 score table (in-memory JSON), not a file",
                     "blind_sample/checks_sha256": "hash of the blind-sample check list, not the CSV (the CSV's own sha256 entry is checked)"}
            if rec["entry"] in NOTES:
                rec["status"] = "not-a-file"; rec["note"] = NOTES[rec["entry"]]; checks.append(rec); return
            if rec["entry"] == "files/stage17/analysis/dev17.py":
                rec["note"] = "pre-analysis hash; dev17.py was then corrected (the M-agree state bug) during Stage 17; the final version is the one frozen in FREEZE_STAGE18.json"
            rec["status"] = ("ok" if rec.get("preserved") and rec.get("preserved_original_bytes_sha256") == x else
                             "preserved-but-changed-since-freeze" if rec.get("preserved") else
                             "not-in-repo" if rec.get("scratchpad_sha256") else "unresolved")
            checks.append(rec)
    walk(d, [], None)

os.makedirs(f"{DEST}/provenance", exist_ok=True)
mf = json.load(open(os.path.join(S, "stage10/frozen_manifest.json")))
canon = hashlib.sha256(json.dumps(mf, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
for c in checks:
    if c["entry"] == "manifestSha256": c["canonical_sha256_now"] = canon; c["status"] = "ok" if canon == c["frozen_sha256"] else "MISMATCH"
json.dump(rewrites, open(f"{DEST}/provenance/PATH_REWRITES.json", "w"), indent=1, sort_keys=True)
json.dump({"rules_in_order": [list(R3), list(R1), list(R2)], "scratchpad": S, "checks": checks}, open(f"{DEST}/provenance/FROZEN_HASH_CHECK.json", "w"), indent=1)
from collections import Counter
print(len(copied), "files copied;", len(rewrites), "rewritten;", Counter(c["status"] for c in checks))
for c in checks:
    if c["status"] != "ok": print(" ", c["status"], c["freeze"], c["entry"], c["file"])
