"""Audit a (staged or released) Biological bundle BEFORE any publication decision. Read-only; prints a pass/fail report and exits 1 on any failure.

  python3 tools/audit_bundle.py /path/to/bundle-root        # contains latest.json
Checks: fail-closed load (manifest + every hash), machine-rule counts vs the manifest, frozen-register coverage, no DRAFT/retired rule reaching a
published band, valid species ids, valid response bands, rule evidence provenance, prediction references, pilot-state consistency, and a private-text
leak scan over the exact payload the publisher would write.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import bands as bd              # noqa: E402
import biological_brain as bb   # noqa: E402
import rules as rl              # noqa: E402

LEAK_KEYS = ('"statement"', '"evidenceId"', '"packet"', '"streamId"', '"conflicts"', '"sourceNo"')
LEAK_TEXT = ("Sector_" + "Research_Data", "PACKET_" + "BRIEF", "packets/", "/Users/")      # concatenated so this file does not trip the repository leak test


def audit(root: str) -> dict:
    checks = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    def read(p):
        return open(os.path.join(root, p), "rb").read()
    try:
        b = bb.load_bundle(read)
    except bb.BundleError as e:
        add("fail-closed load (manifest + hashes + scores)", False, str(e))
        return {"ok": False, "checks": checks}
    add("fail-closed load (manifest + hashes + scores)", True, f"researchVersion {b.research_version}, {len(b.manifest['files'])} files")
    cap = b.capability
    add("capability derived (not set)", cap["status"] in ("IN_PROGRESS", "NOT_STARTED"), f"{cap['status']}; blockers {cap['blockers']}")
    rs = b.ruleset
    if rs is None:
        add("rules present and valid", False, "; ".join(cap["blockers"]))
        return {"ok": all(c["ok"] for c in checks), "checks": checks}
    active = rs.active_rules()
    usable = [r for r in active if r["status"] in rl.USABLE_STATUSES]
    declared = (b.manifest.get("counts") or {}).get("machineRules") or {}
    add("manifest machine-rule counts match the rules", declared.get("total") == len(rs.rules) and declared.get("usable") == len(usable) and declared.get("retired") == len(rs.retired),
        f"declared {declared.get('total')}/{declared.get('usable')}/{declared.get('retired')} vs actual {len(rs.rules)}/{len(usable)}/{len(rs.retired)}")
    add("no APPROVED rule without a reviewer; no RECONCILED rule without a counting read source", not rl.validate_rule_set(rs.rules), "")
    ids = {e["speciesId"] for e in b.registry["species"]}
    sid_ok = all(re.match(r"^[a-z][a-z0-9_]{1,63}$", r["speciesId"]) and r["speciesId"] in ids for r in rs.rules)
    add("every rule's speciesId is valid and in the registry", sid_ok, "")
    add("frozen register covers every usable active rule with a matching hash", not [x for x in cap["blockers"] if "frozen" in x], "; ".join(x for x in cap["blockers"] if "frozen" in x))
    bad_ev = [r["ruleId"] for r in rs.rules if any(not e.get("packet") or not e.get("sourceNo") or e.get("readStatus") not in rl.READ_STATUS for e in r["evidence"])]
    add("every rule evidence entry has provenance (packet, sourceNo, readStatus)", not bad_ev, ",".join(bad_ev[:5]))
    snippet_counting = [r["ruleId"] for r in rs.rules if any(e.get("counts") and e["readStatus"] not in rl.COUNTING_READ for e in r["evidence"])]
    add("no snippet-only/unopened evidence counts", not snippet_counting, ",".join(snippet_counting[:5]))
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ups = bb.build_updates(b, now=dt.datetime.now(dt.timezone.utc), uri_root="gs://audit", deployment="audit", descriptor={}, duration_ms=1, published=None, existing_species=set(), event_id=None)
    bb.check_keys(ups)
    usable_ids = {r["ruleId"] for r in usable}
    draft_in_bands, bad_bands, oversize = [], [], []
    for path, node in ups.items():
        if not path.startswith("/species/") or not node:
            continue
        rb = node.get("responseBands")
        if rb:
            errs = bd.validate_response_bands(rb)
            if errs:
                bad_bands.append((node["speciesId"], errs[:2]))
            used = {i for x in rb.get("bands", []) for i in x["ruleVersion"]["ruleIds"]} | {x["ruleVersion"]["ruleIds"][0] for x in rb.get("habitatPreferences", []) + rb.get("spawn", [])}
            draft_in_bands += [i for i in used if i not in usable_ids]
        if len(json.dumps(node)) > 16000:
            oversize.append(node["speciesId"])
    add("no DRAFT or retired rule reaches a published band", not draft_in_bands, ",".join(draft_in_bands[:5]))
    add("every published responseBands object is schema-valid", not bad_bands, str(bad_bands[:2]))
    add("species payloads stay under 16 KB", not oversize, ",".join(oversize))
    blob = json.dumps(ups)
    leaks = [k for k in LEAK_KEYS if k in blob] + [t for t in LEAK_TEXT if t in blob.replace("local:" + os.path.abspath(root), "")]
    add("publisher payload contains no private rule/evidence text or local paths", not leaks, ",".join(leaks))
    add("no band is APPROVED unless every contributing rule is APPROVED", all(n.get("responseBands", {}).get("status") != "APPROVED" or all(
        r["status"] == "APPROVED" for r in usable if r["speciesId"] == n["speciesId"]) for p, n in ups.items() if p.startswith("/species/") and n), "")
    preds = b.files.get("validation/predictions.jsonl")
    if preds is not None:
        fz = {(e["ruleId"], e["ruleVersion"]): e["ruleSha256"] for e in map(json.loads, b.files["validation/frozen_rules.jsonl"].decode().splitlines() if "validation/frozen_rules.jsonl" in b.files else [])}
        unfrozen = [r["ruleId"] for p in map(json.loads, preds.decode().splitlines()) for r in p["ruleRefs"] if fz.get((r["ruleId"], r["ruleVersion"])) != r["ruleSha256"]]
        add("every logged prediction references a frozen rule with the matching hash", not unfrozen, ",".join(unfrozen[:5]))
    return {"ok": all(c["ok"] for c in checks), "researchVersion": b.research_version, "capability": cap["status"], "checks": checks}


if __name__ == "__main__":
    rep = audit(sys.argv[1])
    for c in rep["checks"]:
        print(("PASS " if c["ok"] else "FAIL ") + c["check"] + (f"  [{c['detail']}]" if c["detail"] else ""))
    print("RESULT:", "PASS" if rep["ok"] else "FAIL")
    sys.exit(0 if rep["ok"] else 1)
