"""Parse Reclamation TSC area / capacity tables (ACAP '1-Foot Increments' layout) from the PDFs fetched earlier into compact JSON (outside git).
Run with: PYTHONPATH=<datum4/w2/pylib> /opt/homebrew/bin/python3 tsc_tables_parse.py
A row is `<base elevation> v0 v1 ... v9.` where every value ends with a period; text extraction sometimes splits a number with a space (`3 316.`), which is joined."""
import json, os, re, sys, glob
from pypdf import PdfReader

BASE = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3")
OUT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5/tsc_tables.json")
ROW = re.compile(r"^\s*(\d{3,5})\s+((?:[\d ,]+\.\s*){1,10})\s*$")


def parse_rows(lines):
    out = {}
    for ln in lines:
        m = ROW.match(ln)
        if not m:
            continue
        base = int(m.group(1))
        vals = [float(re.sub(r"[\s,]", "", v)) for v in m.group(2).split(".") if v.strip()]
        for i, v in enumerate(vals):
            out[base + i] = v
    return out


def header_kind(low):
    """Table header lines on a page -> 'area' | 'cap' | 'skip' (0.1 / 0.01 ft increments) | None. Only lines that START with `[the] area|capacity table(s)` count (so a sentence such as
    '2019 area-capacity tables are in RPVD ... one foot' cannot mislabel a page); the last header on the page wins."""
    last = None
    for ln in low.splitlines():
        m = re.match(r"\s*(?:the )?(area|capacity) tables?\b(.*)", ln)
        if not m:
            continue
        rest = m.group(2)
        if re.search(r"0\.01|hundredth|0\.1\b|0\.1-|one[- ]tenth|ten(?:th)?\b", rest):
            last = "skip"
        elif re.search(r"1-foot|one[- ]foot|1\.0", rest):
            last = "area" if m.group(1) == "area" else "cap"
    return last


def tables(path):
    r = PdfReader(path)
    res = {"area": {}, "cap": {}}
    cur = None
    for pg in r.pages:
        t = pg.extract_text() or ""
        k = header_kind(t.lower())
        if k:
            cur = k
        if cur in ("area", "cap"):
            rows = parse_rows(t.splitlines())
            if rows:
                res[cur].update(rows)
    return res


def main():
    out = {}
    for p in sorted(glob.glob(BASE + "/tsc/*.pdf") + glob.glob(BASE + "/pdf/*.pdf")):
        name = os.path.basename(p)
        if not re.search(r"(?i)capacity|area|acap|tables", name):
            continue
        try:
            t = tables(p)
        except Exception as e:
            out[name] = {"error": repr(e)[:100]}; continue
        if t["area"] or t["cap"]:
            def span(d):
                return [min(d), max(d)] if d else None
            out[name] = {"nArea": len(t["area"]), "nCap": len(t["cap"]), "areaSpan": span(t["area"]), "capSpan": span(t["cap"]), "area": {str(k): v for k, v in t["area"].items()}, "cap": {str(k): v for k, v in t["cap"].items()}}
            print(name, out[name]["nArea"], out[name]["nCap"], out[name]["areaSpan"], out[name]["capSpan"], flush=True)
        else:
            print(name, "no tables", flush=True)
    json.dump(out, open(OUT, "w"))


main()
