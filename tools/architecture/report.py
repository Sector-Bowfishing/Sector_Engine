#!/usr/bin/env python3
"""Architecture invariant report for Sector_Engine (Repository Architecture V1).

REPORT-ONLY in Phase 1A: always exits 0 unless --strict. Legacy violations are
baseline debt and are never enforced until the owning migration phase.

Usage:
  python3 tools/architecture/report.py [--root DIR] [--json] [--strict] [--legacy]

--legacy additionally scans the pre-migration roots (jobs/, Sources/) for the
repo-wide invariants (8, 9, 15, 16) so baseline debt is visible.

Baseline comparison (Phase 1B, still report-only):
  --baseline FILE        compare against a recorded legacy baseline; every finding is
                         labelled KNOWN (in the baseline), NEW (not in it) and baseline
                         entries no longer found are RESOLVED. The baseline never hides
                         new debt. Default file: tools/architecture/baseline/legacy_violations.json
  --write-baseline FILE  record the current --legacy findings as the baseline
  --fail-on-new          exit 1 if any NEW finding exists (opt-in; CI does not use it yet)

Output prints paths and counts only, never file content.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jsonschema_lite import validate  # noqa: E402

CONTRACT_HEADINGS = [
    "IDENTITY", "MISSION", "BOWFISHER DECISION", "OWNERSHIP", "NON-OWNERSHIP",
    "DEPENDENCIES", "COMMUNICATION CONTRACTS", "RESEARCH WORKSPACE",
    "RESEARCH INITIATION RULES", "RESEARCH STOP RULES", "EVIDENCE HIERARCHY",
    "CANONICALIZATION", "VALIDATION", "PUBLISHING", "PATH OWNERSHIP", "SCORING",
    "COST RULES", "SECURITY", "SESSION CLOSEOUT FORMAT",
]
INVARIANTS = {
    1: "every registered Brain has a valid brain.json",
    2: "brainId unique",
    3: "machine id stable (never renamed)",
    4: "operating contract with all 19 sections",
    5: "declared contracts exist",
    6: "declared runtime and tests exist",
    7: "no unauthorized Brain-to-Brain private implementation import",
    8: "no runtime dependency on docs/",
    9: "no absolute Desktop/user path in runtime code",
    10: "no direct specialist production writer after that Brain's Publisher cutover",
    11: "no customer database dependency unless explicitly authorized",
    12: "provider dependency registered in PROVIDERS.json and consumer authorized",
    13: "Brain consumes another Brain only through a declared contract/state",
    14: "Platform never imports a specialist Brain implementation",
    15: "tracked files >= 1 MB require a policy exception",
    16: "no raw research data in Brain research metadata directories",
    17: "declared dependencies resolve (Signal Registry, provider catalog, published contract) and no platform manifest claims an edge a registered Brain does not declare",
}
SIGNAL_REGISTRY = os.path.join("platform", "registries", "signals", "signals.json")
EXECUTION_MANIFEST = os.path.join("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")
DEFAULT_BASELINE = os.path.join("tools", "architecture", "baseline", "legacy_violations.json")
LARGE_BYTES = 1024 * 1024
RESEARCH_ALLOWED = {"GAPS.json", "MANIFEST.json", "README.md"}
RESEARCH_DATA_EXT = {".csv", ".parquet", ".gz", ".zip", ".nc", ".grib", ".grib2", ".tif",
                     ".tiff", ".ipynb", ".sqlite", ".db", ".npy", ".npz", ".geojson", ".h5"}
RESEARCH_MAX_BYTES = 256 * 1024
CODE_EXT = {".py", ".swift", ".sh"}
WRITER_PATTERN = re.compile(r"BrainRTDBStore|firebasedatabase|sector-brain\b|RTDB_URL|\.firebaseio\.com")
# Customer Engine dependency: importing the Engine, or calling the customer endpoints GET /conditions | /lakes (the whole
# path, optionally after a URL host, followed by end-of-string or a query). RTDB paths such as "/lakes/{k}/states/wind" are
# Brain-state paths, not the customer endpoint, and do not match (Wind Phase 2 refinement).
CUSTOMER_PATTERN = re.compile(r"import\s+SectorEngine\b|from\s+engine[.\s]|['\"](?:https?://[^'\"/]+)?/(?:conditions|lakes)(?:\?[^'\"]*)?['\"]")
ABS_PATH = re.compile(r"/Users/[A-Za-z0-9._-]+/")


def _py_string_constants(text):
    """String constants of a Python module excluding docstrings; None if it does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return None
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant):
                docs.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def _code_text(path, text):
    """Text to scan for path references: Python string constants (no docstrings/comments); raw text otherwise."""
    if path.endswith(".py"):
        consts = _py_string_constants(text)
        if consts is not None:
            return "\n".join(consts)
    return text


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=True).stdout
        files = [p for p in out.decode().split("\0") if p]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    found = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", ".build", "__pycache__", "node_modules")]
        for n in names:
            found.append(os.path.relpath(os.path.join(base, n), root))
    return found


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _brain_dirs(root):
    base = os.path.join(root, "brains")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if not d.startswith(("_", ".")) and os.path.isdir(os.path.join(base, d)))


def _code_files(root, rel_dir):
    out = []
    for base, dirs, names in os.walk(os.path.join(root, rel_dir)):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".build", "node_modules")]
        for n in names:
            if os.path.splitext(n)[1] in CODE_EXT:
                out.append(os.path.join(base, n))
    return out


def _is_test(rel):
    parts = rel.replace("\\", "/").split("/")
    return "tests" in parts or "Tests" in parts or os.path.basename(rel).startswith("test_")


def check(root, legacy=False):
    findings = []
    excepted, stale = [], []

    def add(inv, subject, msg):
        findings.append({"invariant": inv, "subject": subject, "message": msg})

    schemas = os.path.join(root, "contracts", "schemas")
    brain_schema = _load(os.path.join(schemas, "brain.schema.json"))
    providers_schema = _load(os.path.join(schemas, "providers.schema.json"))
    stable = _load(os.path.join(HERE, "stable_brain_ids.json"))["directoryToBrainId"]

    catalog, catalog_ok = {}, False
    cat_path = os.path.join(root, "providers", "PROVIDERS.json")
    if os.path.exists(cat_path):
        try:
            cat = _load(cat_path)
            errs = validate(cat, providers_schema)
            for e in errs:
                add(12, "providers/PROVIDERS.json", e)
            catalog = {p["providerId"]: p for p in cat.get("providers", []) if isinstance(p, dict) and "providerId" in p}
            catalog_ok = not errs
        except ValueError as exc:
            add(12, "providers/PROVIDERS.json", f"unparseable: {exc}")

    brains = {}
    ids = {}
    for d in _brain_dirs(root):
        rel = f"brains/{d}"
        bj = os.path.join(root, rel, "brain.json")
        if not os.path.exists(bj):
            add(1, rel, "missing brain.json")
            continue
        try:
            data = _load(bj)
        except ValueError as exc:
            add(1, rel, f"brain.json unparseable: {exc}")
            continue
        errs = validate(data, brain_schema)
        for e in errs:
            add(1, f"{rel}/brain.json", e)
        if errs:
            continue
        brains[d] = data
        ids.setdefault(data["brainId"], []).append(d)

    for bid, dirs in ids.items():
        if len(dirs) > 1:
            add(2, bid, f"brainId declared by multiple directories: {sorted(dirs)}")

    for d, data in brains.items():
        rel = f"brains/{d}"
        if d in stable and data["brainId"] != stable[d]:
            add(3, rel, f"brainId {data['brainId']!r} != locked machine id {stable[d]!r}")
        # 4
        oc = os.path.join(root, rel, "BRAIN_OPERATING_CONTRACT.md")
        if not os.path.exists(oc):
            add(4, rel, "missing BRAIN_OPERATING_CONTRACT.md")
        else:
            text = _read(oc)
            heads = [re.sub(r"^\d+\.\s*", "", m.strip()).strip() for m in re.findall(r"^##\s+(.+)$", text, re.M)]
            for h in CONTRACT_HEADINGS:
                if h not in heads:
                    add(4, rel, f"operating contract missing section '{h}'")
        # 5
        for pub in data["publishes"]:
            ref = pub.get("schemaRef")
            if ref and not os.path.exists(os.path.join(root, ref)):
                add(5, rel, f"declared contract schema not found: {ref}")
        # 6
        ep = data["runtime"].get("entrypoint")
        if ep and not os.path.exists(os.path.join(root, ep)):
            add(6, rel, f"runtime entrypoint not found: {ep}")
        for t in data["tests"]:
            if not os.path.exists(os.path.join(root, t)):
                add(6, rel, f"declared test path not found: {t}")
        # 12
        for prov in data["providers"]:
            pid = prov["providerId"]
            if pid not in catalog:
                add(12, rel, f"provider {pid!r} not registered in providers/PROVIDERS.json")
            elif data["brainId"] not in catalog[pid].get("authorizedConsumers", []):
                add(12, rel, f"{data['brainId']!r} not an authorizedConsumer of provider {pid!r}")
        # 13 (declared edges must point at a real, publishing Brain)
        by_id = {b["brainId"]: b for b in brains.values()}
        for c in data["consumes"]:
            if c["kind"] == "brain":
                tgt = by_id.get(c.get("brainId"))
                if tgt is None:
                    add(13, rel, f"consumes unknown Brain {c.get('brainId')!r}")
                elif not any(p["contractId"] == c["contractId"] for p in tgt["publishes"]):
                    add(13, rel, f"consumes {c['contractId']!r} not published by {c.get('brainId')!r}")
        # code scans
        declared = {c.get("brainId") for c in data["consumes"] if c["kind"] == "brain"}
        for f in _code_files(root, rel):
            frel = os.path.relpath(f, root)
            if _is_test(frel):
                continue
            text = _read(f)
            for other in re.findall(r"brains[./]([a-z][a-z0-9-]*)[./]([a-z_]+)", text):
                odir, sub = other
                if odir == d or odir not in brains:
                    continue
                if sub != "contracts":
                    add(7, frel, f"references private implementation of brains/{odir}/{sub}")
                elif brains[odir]["brainId"] not in declared:
                    add(13, frel, f"uses brains/{odir}/contracts without a declared consumes edge")
            if "runtime" in frel.split(os.sep):
                scan = _code_text(frel, text)
                if re.search(r"docs/", scan):
                    add(8, frel, "runtime references docs/")
                if ABS_PATH.search(scan):
                    add(9, frel, "absolute user path in runtime code")
            if data["publisherRequired"]["cutoverStatus"] == "CUTOVER_COMPLETE" and WRITER_PATTERN.search(text):
                add(10, frel, "direct sector-brain writer in a Brain already cut over to the Publisher")
            if data["customerIntegrationMode"] == "none" and CUSTOMER_PATTERN.search(text):
                add(11, frel, "customer Engine/API dependency but customerIntegrationMode is 'none'")

    # 17: declared dependencies (brain.json consumes[] / providers[]) resolve against the platform registries, and no platform-authored
    #     manifest declares a Brain -> Brain edge for a REGISTERED Brain that the Brain does not declare itself (the Engine never invents a graph)
    sig_path = os.path.join(root, SIGNAL_REGISTRY)
    signals = None
    if os.path.exists(sig_path):
        try:
            sdoc = _load(sig_path)
            for e in validate(sdoc, _load(os.path.join(schemas, "registry-signals.schema.json"))):
                add(17, SIGNAL_REGISTRY, e)
            signals = {s["signalId"]: s for s in sdoc.get("signals", []) if isinstance(s, dict) and "signalId" in s}
        except ValueError as exc:
            add(17, SIGNAL_REGISTRY, f"unparseable: {exc}")
    by_id = {b["brainId"]: b for b in brains.values()}
    declared_edges = {}
    for d, data in brains.items():
        rel = f"brains/{d}"
        declared_edges[data["brainId"]] = set()
        for i, c in enumerate(data["consumes"]):
            if c["kind"] == "signal":
                if signals is None:
                    add(17, rel, f"consumes signal {c.get('signalId')!r} but no Signal Registry exists at {SIGNAL_REGISTRY}")
                elif c.get("signalId") not in signals:
                    add(17, rel, f"consumes signal {c.get('signalId')!r} not defined in the Signal Registry")
                elif signals[c["signalId"]].get("status") == "RETIRED":
                    add(17, rel, f"consumes RETIRED signal {c['signalId']!r}")
            elif c["kind"] == "brain":
                declared_edges[data["brainId"]].add(c.get("brainId"))
                tgt = by_id.get(c.get("brainId"))
                if tgt is not None and tgt.get("authorizedConsumers") is not None and data["brainId"] not in tgt["authorizedConsumers"]:
                    add(17, rel, f"{data['brainId']!r} consumes {c.get('brainId')!r} but is not one of its authorizedConsumers")
            if c.get("freshness") and not (c["freshness"].get("maxAgeHours") and c["freshness"].get("reason")):
                add(17, rel, f"consumes[{i}] freshness needs maxAgeHours and reason")
    man_path = os.path.join(root, EXECUTION_MANIFEST)
    if os.path.exists(man_path) and declared_edges:
        try:
            man = _load(man_path)
            for bid, b in (man.get("brains") or {}).items():
                if bid not in declared_edges:
                    continue
                for dep in b.get("dependencies") or []:
                    if dep.get("id") not in declared_edges[bid]:
                        add(17, EXECUTION_MANIFEST, f"claims {bid} -> {dep.get('id')} but brains/*/brain.json does not declare it (consumes kind=brain)")
        except ValueError as exc:
            add(17, EXECUTION_MANIFEST, f"unparseable: {exc}")

    # 14: platform must not import a specialist Brain implementation
    if os.path.isdir(os.path.join(root, "platform")):
        for f in _code_files(root, "platform"):
            frel = os.path.relpath(f, root)
            if _is_test(frel):
                continue
            for odir, sub in re.findall(r"brains[./]([a-z][a-z0-9-]*)[./]([a-z_]+)", _read(f)):
                if odir != "_template" and sub != "contracts":
                    add(14, frel, f"platform references brains/{odir}/{sub} implementation")

    # 8/9 for non-Brain new-structure roots
    for top in ("platform", "providers", "engine"):
        if os.path.isdir(os.path.join(root, top)):
            for f in _code_files(root, top):
                frel = os.path.relpath(f, root)
                if _is_test(frel):
                    continue
                scan = _code_text(frel, _read(f))
                if re.search(r"docs/", scan):
                    add(8, frel, "runtime references docs/")
                if ABS_PATH.search(scan):
                    add(9, frel, "absolute user path in runtime code")

    # 15 / 16 / legacy 8,9
    exc_doc = _load(os.path.join(HERE, "large_file_exceptions.json"))
    for e in validate(exc_doc, _load(os.path.join(schemas, "large-file-exceptions.schema.json"))):
        add(15, "tools/architecture/large_file_exceptions.json", e)
    exceptions = {e["path"]: e for e in exc_doc["exceptions"] if isinstance(e, dict) and "path" in e}
    tracked = _tracked_files(root)
    tracked_set = set(tracked)
    for rel in tracked:
        full = os.path.join(root, rel)
        try:
            size = os.path.getsize(full)
        except OSError:
            continue
        if size >= LARGE_BYTES and rel not in exceptions:
            add(15, rel, "tracked file >= 1 MB without a recorded policy exception")
        elif size >= LARGE_BYTES:
            excepted.append({"path": rel, "status": exceptions[rel].get("status"), "reviewPhase": exceptions[rel].get("reviewPhase")})
        elif rel in exceptions:
            stale.append(rel)
        parts = rel.split("/")
        if parts[0] == "brains" and len(parts) >= 4 and parts[2] == "research" and not parts[1].startswith("_"):
            name = parts[-1]
            ext = os.path.splitext(name)[1].lower()
            in_tools = len(parts) > 4 and parts[3] == "tools"
            if ext in RESEARCH_DATA_EXT or size > RESEARCH_MAX_BYTES or (not in_tools and name not in RESEARCH_ALLOWED):
                add(16, rel, "not research metadata (data extension, oversize, or unlisted file)")
    if legacy:
        for rel in tracked:
            if not rel.startswith(("jobs/", "Sources/")) or os.path.splitext(rel)[1] not in CODE_EXT or _is_test(rel):
                continue
            scan = _code_text(rel, _read(os.path.join(root, rel)))
            if ABS_PATH.search(scan):
                add(9, rel, "absolute user path in legacy runtime code (baseline debt)")
            if rel.endswith(".py") and re.search(r"docs/(brains|data)/", scan):
                add(8, rel, "legacy runtime references a docs/ path (baseline debt)")
    for path in exceptions:
        if path not in tracked_set:
            stale.append(path)
    check.last_excepted = excepted      # large files covered by a recorded exception (not violations)
    check.last_stale = sorted(set(stale))   # exceptions whose file is gone or shrank below 1 MB
    return findings


def finding_key(f):
    return f"{f['invariant']}|{f['subject']}|{f['message']}"


def compare_to_baseline(findings, baseline):
    """-> (known, new, resolved) as lists of keys-with-findings. Never hides new debt."""
    base = {e["key"]: e for e in baseline.get("entries", [])}
    cur = {finding_key(f): f for f in findings}
    known = [cur[k] for k in cur if k in base]
    new = [cur[k] for k in cur if k not in base]
    resolved = [base[k] for k in base if k not in cur]
    return known, new, resolved


def build_baseline(findings, root, previous=None):
    """Annotated baseline. Entries whose key is already in `previous` keep their curated owner/reason/phase/note."""
    prev = {e["key"]: e for e in (previous or {}).get("entries", [])}
    omap = _load(os.path.join(HERE, "ownership_map.json"))["prefixes"]
    reasons = {
        8: "legacy runtime code references a docs/ path (spec, rubric label or data); retires when the owning component migrates",
        9: "legacy code contains an absolute user path; made config/env-driven at the owning component's migration",
        15: "tracked file >= 1 MB without an exception",
    }
    entries = []
    for f in sorted(findings, key=lambda x: (x["invariant"], x["subject"])):
        owner, phase = "unassigned", "Phase 6/7"
        for m in omap:
            if f["subject"].startswith(m["prefix"]):
                owner, phase = m["owner"], m["phase"]
                break
        e = {"key": finding_key(f), "invariant": f["invariant"], "path": f["subject"], "owner": owner,
             "reason": reasons.get(f["invariant"], f["message"]), "plannedMigrationPhase": phase, "status": "LEGACY_BASELINE"}
        old = prev.get(e["key"])
        if old:
            e.update({k: old[k] for k in ("owner", "reason", "plannedMigrationPhase", "note", "carriedFrom") if k in old})
        entries.append(e)
    return {"schemaVersion": "1.0.0", "createdBy": "Phase 1B baseline", "mode": "REPORT_ONLY",
            "description": "Known legacy architecture violations from `report.py --legacy`. Existing = KNOWN, absent from here = NEW, here but gone = RESOLVED. Not an approval; enforced when the owning component migrates.",
            "entries": entries}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 when findings exist (NOT used in Phase 1A)")
    ap.add_argument("--legacy", action="store_true", help="also scan pre-migration jobs/ and Sources/")
    ap.add_argument("--baseline", nargs="?", const=DEFAULT_BASELINE, default=None, help="compare to a recorded baseline (default file if no value)")
    ap.add_argument("--write-baseline", metavar="FILE", help="write the current findings as the legacy baseline")
    ap.add_argument("--fail-on-new", action="store_true", help="exit 1 if any NEW finding (opt-in)")
    args = ap.parse_args(argv)
    findings = check(args.root, legacy=args.legacy)
    if args.write_baseline:
        previous = _load(args.write_baseline) if os.path.exists(args.write_baseline) else None
        with open(args.write_baseline, "w", encoding="utf-8") as fh:
            json.dump(build_baseline(findings, args.root, previous), fh, indent=2)
            fh.write("\n")
        print(f"baseline written: {len(findings)} entries -> {args.write_baseline}")
        return 0
    if args.baseline:
        bpath = args.baseline if os.path.isabs(args.baseline) else os.path.join(args.root, args.baseline)
        known, new, resolved = compare_to_baseline(findings, _load(bpath))
        if args.json:
            print(json.dumps({"mode": "REPORT_ONLY", "known": len(known), "new": new, "resolved": resolved,
                              "largeFilesCoveredByException": check.last_excepted, "staleExceptions": check.last_stale}, indent=2))
        else:
            print("ARCHITECTURE BASELINE COMPARISON (REPORT-ONLY)")
            print(f"  KNOWN legacy findings (in baseline): {len(known)}")
            print(f"  NEW findings (not in baseline):      {len(new)}")
            print(f"  RESOLVED baseline entries:           {len(resolved)}")
            print(f"  large files covered by exception:    {len(check.last_excepted)}; stale exceptions: {len(check.last_stale)}")
            for f in new:
                print(f"    NEW  inv {f['invariant']}: {f['subject']}: {f['message']}")
            for e in resolved:
                print(f"    RESOLVED inv {e['invariant']}: {e['path']}")
            for p in check.last_stale:
                print(f"    STALE EXCEPTION: {p}")
        return 1 if (args.fail_on_new and new) else 0
    if args.json:
        print(json.dumps({"mode": "REPORT_ONLY", "findings": findings}, indent=2))
    else:
        counts = {i: 0 for i in INVARIANTS}
        for f in findings:
            counts[f["invariant"]] += 1
        print("ARCHITECTURE INVARIANT REPORT (REPORT-ONLY)")
        n_brains = len(_brain_dirs(args.root))
        print(f"  registered Brains scanned: {n_brains}" + (" (PASS on 0 Brains is vacuous)" if n_brains == 0 else ""))
        for i, label in INVARIANTS.items():
            print(f"  [{i:>2}] {'PASS' if not counts[i] else str(counts[i]) + ' finding(s)':<14} {label}")
        for f in findings:
            print(f"    - inv {f['invariant']}: {f['subject']}: {f['message']}")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
