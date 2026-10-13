"""Reviewer workflow for Biological machine rules (nothing is approved automatically; nothing is self-promoted).

  python3 tools/review.py packet  RULES_DIR OUT.md [--species ID ...]     # concise review packet (contains rule text: keep it PRIVATE)
  python3 tools/review.py apply   RULES_DIR DECISIONS.json OUT_DIR         # write a NEW rules directory with the accepted rules re-issued as APPROVED

DECISIONS.json = [{"ruleId", "ruleVersion", "decision": "ACCEPT"|"REJECT"|"CHANGES", "reviewer", "reviewerRole": "EXTERNAL"|"OWNER", "date", "note"}]

Acceptance never edits a frozen rule. An ACCEPT re-issues the rule as ruleVersion+1 with status APPROVED and a `review` block, retires the old version through
`supersededBy`, and bumps the rules version; the new identity must then be frozen before any prediction uses it. REJECT/CHANGES leave the rule as is and are
recorded in a review ledger. The code refuses: approving a DRAFT or retired rule, a reviewer who authored the rule, a missing reviewer, a decision for a rule
that does not exist, or a rule whose evidence does not trace to at least one counting, read source.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import rules as rl   # noqa: E402

AUTHORS = ("claude", "claude-adoption", "claude-adoption-2026-10-13", "claude-adoption-2026-10-14")     # reviewers may not be rule authors
DECISIONS = ("ACCEPT", "REJECT", "CHANGES")
ROLES = ("EXTERNAL", "OWNER")

CHECKLIST = ("Every cited source exists and says what the evidence note says (open the link or the packet)",
             "'Independent streams' are really independent (one cohort reported twice is one stream)",
             "The statement does not claim more than the evidence (direction, season, region, species, life stage)",
             "Transfer tag is fair for Southeast reservoirs (PARTIAL/UNTESTED unless a Southeast stream counts)",
             "Confidence is not higher than the evidence supports (1 stream = LOW)",
             "Limitations/conflicts are stated; unknown is left unknown")


def load(rules_dir: str) -> rl.RuleSet:
    return rl.load_rules_dir(rules_dir)


def build_packet(rs: rl.RuleSet, species: list[str] | None = None) -> str:
    out = ["# Biological rule review packet (PRIVATE: contains rule text and evidence notes)", "",
           f"Rules version `{rs.rules_version}`. Review only RECONCILED rules; DRAFT rules are shown as excluded. Accepting a rule re-issues it as a new APPROVED version; it never edits the frozen original.", "",
           "## Acceptance standard", *[f"- [ ] {c}" for c in CHECKLIST], "",
           "## What acceptance does / does not do",
           "* A species reaches REVIEWED only when at least 80% of its usable rules are APPROVED by a reviewer who did not author them; promotion is a separate, recorded decision.",
           "* APPROVED is **not** VALIDATED. No rule is validated until preregistered field criteria are met.", ""]
    for sid in sorted(rs.by_species):
        if species and sid not in species:
            continue
        use = rs.for_species(sid)
        draft = [r for r in rs.by_species[sid] if r["status"] == "DRAFT" and rs.is_active(r)]
        out += [f"## {sid}  ({len(use)} usable, {len(draft)} draft)", ""]
        for r in sorted(use, key=lambda x: x["ruleId"]):
            a = r.get("applicability") or {}
            out += [f"### {r['ruleId']} v{r['ruleVersion']}  ·  {r['kind']}  ·  confidence {r['confidence']}  ·  SE transfer {r['transferability']['southeastReservoir']}",
                    f"* **Says:** {r.get('statement') or '(no statement)'}",
                    f"* **Applies:** months {a.get('months') or 'all'} · regions {a.get('regions', ['any'])} · waterbody {a.get('waterbodyTypes', ['any'])}",
                    ("* **Feature:** " + f"{r['feature']['featureId']} in {r['feature']['states']} → {r['response']}") if r["kind"] == "RESPONSE" else
                    ("* **Habitat:** " + f"{r['habitat']['direction']} {r['habitat']['habitatClass']}" + (f" (requires {r['requires']})" if r.get("requires") else "")) if r["kind"] == "HABITAT" else
                    f"* **Spawn range:** {r['phenology']['tempC']['min']:g}-{r['phenology']['tempC']['max']:g} C",
                    f"* **Independent streams counted:** {len(rl.counting_streams(r))}", "* **Evidence:**"]
            for e in r["evidence"]:
                out.append(f"  - {'✔' if e['counts'] else '✘ not counted'} `{e['packet']}` {e['sourceNo']} · {e['readStatus']} · stream `{e['streamId']}` · {e.get('studyType', '')} · {e.get('region', '')} {e.get('sample', '')}" + (f" · {e['note']}" if e.get("note") else ""))
            if r.get("conflicts"):
                out.append("* **Documented conflicts:** " + "; ".join(r["conflicts"]))
            out += ["* **Decision:** ACCEPT / REJECT / CHANGES  ·  reviewer ____  ·  date ____  ·  note ____", ""]
        if draft:
            out += ["**Excluded DRAFT rules (shown for completeness, not for approval):** " + ", ".join(sorted(r["ruleId"] for r in draft)), ""]
    return "\n".join(out)


def apply_decisions(rs: rl.RuleSet, decisions: list[dict], now: dt.datetime) -> tuple[list[dict], list[dict], list[dict], str]:
    """Returns (all rules incl. new APPROVED versions, retired list, ledger entries, new rulesVersion). Raises rl.RuleError on any violation."""
    rules = copy.deepcopy(rs.rules)
    index = {(r["ruleId"], r["ruleVersion"]): r for r in rules}
    retired = [dict(x) for x in rs.retired.values()]
    ledger, accepted = [], 0
    for d in decisions:
        key = (d.get("ruleId"), d.get("ruleVersion"))
        r = index.get(key)
        errs = []
        if r is None:
            errs.append("rule does not exist")
        if d.get("decision") not in DECISIONS:
            errs.append(f"decision must be one of {DECISIONS}")
        if not d.get("reviewer") or not str(d["reviewer"]).strip():
            errs.append("reviewer is required")
        elif str(d["reviewer"]).strip().lower() in AUTHORS:
            errs.append("a reviewer may not be the rule author")
        if d.get("reviewerRole") not in ROLES:
            errs.append(f"reviewerRole must be one of {ROLES}")
        if not d.get("date"):
            errs.append("date is required")
        if r is not None and d.get("decision") == "ACCEPT":
            if r["status"] != "RECONCILED" or not rs.is_active(r):
                errs.append("only an active RECONCILED rule can be accepted")
            elif not any(e.get("counts") and e["readStatus"] in ("READ-FULL", "READ-ABSTRACT", "PROFILE-REVIEWED") for e in r["evidence"]):
                errs.append("no counting read source")
        if errs:
            raise rl.RuleError(f"{key}: " + "; ".join(errs))
        entry = {k: d.get(k) for k in ("ruleId", "ruleVersion", "decision", "reviewer", "reviewerRole", "date", "note")}
        entry["ruleSha256"] = rl.rule_hash(r)
        if d["decision"] == "ACCEPT":
            new = copy.deepcopy(r)
            new["ruleVersion"] = r["ruleVersion"] + 1
            while (new["ruleId"], new["ruleVersion"]) in index:
                new["ruleVersion"] += 1
            new["status"] = "APPROVED"
            new["review"] = {"reviewer": d["reviewer"], "reviewerRole": d["reviewerRole"], "date": d["date"], "supersedes": r["ruleVersion"]}
            rules.append(new)
            index[(new["ruleId"], new["ruleVersion"])] = new
            retired.append({"ruleId": r["ruleId"], "ruleVersion": r["ruleVersion"], "supersededBy": {"ruleId": new["ruleId"], "ruleVersion": new["ruleVersion"]},
                            "reason": f"approved by {d['reviewer']} ({d['reviewerRole']}) on {d['date']}; re-issued as an APPROVED version", "retiredAt": d["date"]})
            entry["newVersion"] = new["ruleVersion"]
            accepted += 1
        ledger.append(entry)
    ver = rs.rules_version.rsplit("-rules", 1)[0] + f"+review.{now.strftime('%Y%m%d')}-rules" if accepted else rs.rules_version
    return rules, retired, ledger, ver


def write_dir(rules: list[dict], retired: list[dict], ledger: list[dict], version: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    by: dict[str, list] = {}
    for r in rules:
        by.setdefault(r["speciesId"], []).append(r)
    files = []
    for sid, rr in sorted(by.items()):
        body = json.dumps({"speciesId": sid, "rules": rr}, indent=1, sort_keys=True).encode()
        open(os.path.join(out_dir, f"{sid}.json"), "wb").write(body)
        files.append({"path": f"{sid}.json", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})
    json.dump({"schemaVersion": 1, "rulesVersion": version, "files": files, "retired": retired}, open(os.path.join(out_dir, "rules_manifest.json"), "w"), indent=1)
    with open(os.path.join(out_dir, "review_ledger.jsonl"), "a") as fh:
        for e in ledger:
            fh.write(json.dumps(e, sort_keys=True) + "\n")


def main(argv):
    if len(argv) >= 4 and argv[1] == "packet":
        sp = argv[argv.index("--species") + 1:] if "--species" in argv else None
        open(argv[3], "w").write(build_packet(load(argv[2]), sp))
        print("wrote", argv[3])
        return 0
    if len(argv) == 5 and argv[1] == "apply":
        rs = load(argv[2])
        rules, retired, ledger, ver = apply_decisions(rs, json.load(open(argv[3])), dt.datetime.now(dt.timezone.utc))
        write_dir(rules, retired, ledger, ver, argv[4])
        rl.load_rules_dir(argv[4])                       # the written directory must itself validate
        print(f"wrote {argv[4]}: version {ver}; {sum(1 for e in ledger if e['decision'] == 'ACCEPT')} accepted of {len(ledger)} decisions")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
