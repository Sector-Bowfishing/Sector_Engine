#!/usr/bin/env python3
"""Render the campaign ledgers (docs/research/lake-brain/ledger/*.jsonl) into the required Markdown documents.

  LAKE_BRAIN_SOURCE_LEDGER.md   every source/search incl. dead ends       (kind=source)
  LAKE_BRAIN_BLOCKER_QUEUE.md   blocker queue + Michael action queue      (kind=blocker, kind=action)
  LAKE_BRAIN_DATA_SOURCE_MATRIX.md  accepted sources by what they support (kind=source, decision ACCEPTED/LEAD)
  data/dataset_manifest.md      retention classes for Sweep               (kind=dataset)
Score history is written by hand/by research_score.py into LAKE_BRAIN_SCORE_HISTORY.md (kind=score rows are listed there too).
Tolerant of missing fields: unknown stays '—'.
"""
from __future__ import annotations

import collections
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.normpath(os.path.join(HERE, "..", "..", "..", "docs", "research", "lake-brain"))


def load() -> list[dict]:
    rows = []
    for p in sorted(glob.glob(os.path.join(DOCS, "ledger", "*.jsonl"))):
        thread = os.path.basename(p)[:-6]
        for i, line in enumerate(open(p), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                r = {"kind": "unparsed", "raw": line[:200]}
            r.setdefault("_thread", thread)
            r.setdefault("_line", i)
            rows.append(r)
    return rows


def cell(v) -> str:
    if v is None or v == "" or v == []:
        return "—"
    if isinstance(v, (list, tuple)):
        v = ", ".join(str(x) for x in v)
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def write(name: str, text: str) -> None:
    path = os.path.join(DOCS, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(text.rstrip() + "\n")
    print(f"wrote {name} ({len(text.splitlines())} lines)")


def main() -> int:
    rows = load()
    src = [r for r in rows if r.get("kind") == "source"]
    blk = [r for r in rows if r.get("kind") == "blocker"]
    act = [r for r in rows if r.get("kind") == "action"]
    # datasets: the manifest next to the data (authoritative, de-duplicated by path); per-thread dataset rows are only a fallback
    mp = os.path.join(DOCS, "data", "MANIFEST.jsonl")
    if os.path.exists(mp):
        seen = {}
        for line in open(mp):
            line = line.strip()
            if line:
                r = json.loads(line)
                seen[r["path"]] = r
        dat = list(seen.values())
    else:
        dat = [r for r in rows if r.get("kind") == "dataset"]
    sc = [r for r in rows if r.get("kind") == "score"]
    dec = collections.Counter(r.get("decision", "—") for r in src)

    # ── source ledger ──
    s = ["# Lake Brain — source ledger (generated)", "",
         "Every significant source/search of the campaign, including **dead ends** (`DEAD_END`/`REJECTED`) so nobody repeats them.",
         f"Generated from `ledger/*.jsonl` by `research/lake-brain/tools/render_ledger.py`. {len(src)} records: "
         + ", ".join(f"{k} {v}" for k, v in sorted(dec.items())) + ".", "",
         "Authority: 1 federal/operator/state authoritative · 2 peer-reviewed · 3 gov/university report · 4 documented public GIS portal · 5 scientific DB · 6 secondary · 7 lead only.", ""]
    for thread in sorted({r["_thread"] for r in src}):
        s += [f"## Thread: {thread}", ""]
        s.append(table(["ID", "Decision", "Source", "Org", "Auth", "Data / coverage", "Access", "License", "Supports → dimension", "Reason / notes", "Accessed", "URL"],
                       [[r.get("id"), r.get("decision"), r.get("name"), r.get("org"), r.get("authority"),
                         f"{cell(r.get('dataType'))}; {cell(r.get('geoCoverage'))}; lakes {cell(r.get('lakeCoverage'))}; {cell(r.get('timeCoverage'))}; {cell(r.get('cadence'))}",
                         f"{cell(r.get('access'))}{' (machine)' if r.get('machineReadable') else ''}", r.get("license"),
                         f"{cell(r.get('supports'))} → {cell(r.get('scoreDimensions'))}", f"{cell(r.get('reason'))} {cell(r.get('notes')) if r.get('notes') else ''}",
                         r.get("accessed"), r.get("url")] for r in src if r["_thread"] == thread]))
        s.append("")
    dead = [r for r in src if r.get("decision") in ("DEAD_END", "REJECTED")]
    s += ["## Dead ends and rejected sources — do not repeat", ""]
    s.append(table(["ID", "Source", "Why it failed / was rejected", "URL"], [[r.get("id"), r.get("name"), r.get("reason"), r.get("url")] for r in dead]) if dead else "_none recorded_")
    write("LAKE_BRAIN_SOURCE_LEDGER.md", "\n".join(s))

    # ── blocker + action queues ──
    prio = {"high": 0, "medium": 1, "low": 2}
    b = ["# Lake Brain — blocker queue and Michael action queue (generated)", "",
         "A blocker stops one research thread, never the campaign. Every blocker lists the proxy that was used instead.", ""]
    b += ["## BLOCKER QUEUE", ""]
    b.append(table(["ID", "Priority", "Status", "Research question", "Missing requirement", "Why it matters", "Score dimension", "Est. score impact", "Attempted", "Proxy / alternative", "Michael action?"],
                   [[r.get("id"), r.get("priority"), r.get("status"), r.get("question"), r.get("missing"), r.get("why"), r.get("scoreDimension"),
                     r.get("impact"), r.get("attempted"), r.get("proxy"), r.get("michaelAction")]
                    for r in sorted(blk, key=lambda r: (prio.get(r.get("priority"), 3), str(r.get("id"))))]) if blk else "_none recorded_")
    b += ["", "## MICHAEL ACTION QUEUE", "",
          "Concise and high-value only. Nothing here blocks the research; each item raises confidence or unlocks a dimension.", ""]
    b.append(table(["ID", "Priority", "Action", "Impact", "Related blocker"],
                   [[r.get("id"), r.get("priority"), r.get("what"), r.get("impact"), r.get("relatedBlocker")]
                    for r in sorted(act, key=lambda r: (prio.get(r.get("priority"), 3), str(r.get("id"))))]) if act else "_none recorded_")
    write("LAKE_BRAIN_BLOCKER_QUEUE.md", "\n".join(b))

    # ── data source matrix (accepted + leads) ──
    ok = [r for r in src if r.get("decision") in ("ACCEPTED", "LEAD")]
    m = ["# Lake Brain — data source matrix (generated)", "",
         "Sources worth permanently integrating (ACCEPTED) or following up (LEAD), grouped by what they support.", ""]
    groups = collections.defaultdict(list)
    for r in ok:
        groups[(r.get("supports") or "other")].append(r)
    for g in sorted(groups):
        m += [f"## {g}", ""]
        m.append(table(["Decision", "Source", "Org", "Auth", "Lake coverage", "Time", "Cadence", "Access", "License", "Dimension", "ID"],
                       [[r.get("decision"), r.get("name"), r.get("org"), r.get("authority"), r.get("lakeCoverage"), r.get("timeCoverage"), r.get("cadence"),
                         f"{cell(r.get('access'))}{' (machine)' if r.get('machineReadable') else ''}", r.get("license"), r.get("scoreDimensions"), r.get("id")] for r in groups[g]]))
        m.append("")
    write("LAKE_BRAIN_DATA_SOURCE_MATRIX.md", "\n".join(m))

    # ── dataset manifest (retention classes) ──
    d = ["# Lake Brain research — dataset retention manifest (generated)", "",
         "For Sweep: `KEEP` valuable irreplaceable research · `ARCHIVE_FIRST` valuable, large, archive before any removal · `REBUILDABLE` can be regenerated (rebuild command given) · `SAFE_TO_REMOVE` disposable cache · `REVIEW_REQUIRED`.",
         "Data lives outside Git under `~/Desktop/Development/Sector_Research_Data/lake-brain/` (see `MANIFEST.jsonl` there for checksums).", ""]
    d.append(table(["Path", "Bytes", "Track", "Retention", "Rebuild", "Note"], [[r.get("path"), r.get("bytes"), r.get("track"), r.get("retention"), r.get("rebuild"), r.get("note")] for r in dat]) if dat else "_none recorded_")
    write("data/dataset_manifest.md", "\n".join(d))
    print(f"rows: {len(rows)} (source {len(src)}, blocker {len(blk)}, action {len(act)}, dataset {len(dat)}, score {len(sc)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
