"""Parse Reclamation ACAP capacity-EQUATION tables: per equation `n  base  capacityBase  A1  A2  A3`, valid for elevations base_n <= E < base_{n+1}:
    capacity(E) = A1 + A2*x + A3*x^2,   area(E) = A2 + 2*A3*x,   x = E - base_n      (checked against the printed 1-ft tables of Cheney: 614.4 af and 375.8 ac at 1383 ft)
PDF text extraction sometimes splits a number (`1 072.9555`, `143 9.00`); every row is parsed by trying all ways to merge adjacent tokens into exactly six fields of the right format and is kept
only if (a) exactly one merge is consistent and (b) its capacity equation reproduces the next row's printed capacity base within 1.5 acre-feet. A lake is accepted only when the kept rows are
contiguous over the stored elevation range. Run with: PYTHONPATH=<datum4/w2/pylib> /opt/homebrew/bin/python3 tsc_equations_parse.py"""
import itertools, json, os, re, sys
from pypdf import PdfReader

BASE = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3")
DL = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5")
OUT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum5/tsc_equations.json")
FILES = ["tsc/BlueMesaReservoir2019AreaAndCapacityTables_Final508.pdf", "tsc/Edward_Arthur_Patterson_CapacityTable_2013.pdf", "tsc/Lake_Tschida_2013_Capacity_Tables.pdf",
         "tsc/Calamus_2012_Area-Capacity_table_final.pdf", "tsc/Fresno_Reservoir_2010_Area_and_Capatity_Tables.pdf", "tsc/Cheney" + "Reservoir2015AreaCapacityTables_Final508.pdf",
         "tsc/Elephant_Butte_Reservoir_2017_&_2019_Area_and_Capacity_Tables.pdf", "tsc/NavajoReservoir2019AreaCapacityTables_final508VI.pdf",
         "tsc/BighornReservoirAreaCapacityTables2017_Final508.pdf", "tsc/El_Vado_Capacity_Tables_2007.pdf", "tsc/Heron_Reservoir_2010_Capacity_Tables.pdf",
         "dl/ElVado2018_tables.pdf"]
FMT = [r"\d{1,4}", r"\d{3,5}(?:\.\d{1,2})?", r"\d{1,8}", r"-?\d{1,8}\.\d{4}", r"-?\d{1,8}\.\d{4}", r"-?\d{1,8}\.\d{4}"]


def parse_line(line):
    toks = line.replace(",", "").split()
    if len(toks) < 6 or len(toks) > 14:
        return None
    found = []
    for cuts in itertools.combinations(range(1, len(toks)), 5):
        parts = [toks[a:b] for a, b in zip((0,) + cuts, cuts + (len(toks),))]
        fields = ["".join(p) for p in parts]
        if all(re.fullmatch(f, x) for f, x in zip(FMT, fields)):
            found.append(fields)
    return found


def rows_from(path):
    r = PdfReader(path)
    rows = {}
    for pg in r.pages:
        t = pg.extract_text() or ""
        if "EQUATION" not in t.upper():
            continue
        for ln in t.splitlines():
            ln = ln.strip()
            if not re.match(r"^\d{1,4}\s", ln):
                continue
            c = parse_line(ln)
            if not c:
                continue
            cs = []
            for f in c:
                n, base, capb, a1, a2, a3 = int(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5])
                if capb - 1.0 <= a1 <= capb + 1.0 + 1e-9 or abs(a1 - capb) < 1.5:       # A1 is the unrounded capacity base
                    cs.append((n, base, capb, a1, a2, a3))
            if len(cs) == 1:
                rows[cs[0][0]] = cs[0]
    return rows


def validate(rows):
    ns = sorted(rows)
    good = {}
    for a, b in zip(ns, ns[1:]):
        if b != a + 1:
            continue
        n, base, capb, a1, a2, a3 = rows[a]
        nb = rows[b]
        x = nb[1] - base
        if x <= 0 or x > 12:
            continue
        if abs(a1 + a2 * x + a3 * x * x - nb[2]) <= 1.5:
            good[a] = rows[a]
    return good


def main():
    out = {}
    for f in FILES:
        p = os.path.join(DL if f.startswith("dl/") else BASE, f)
        try:
            rows = rows_from(p)
        except Exception as e:
            print(f, "ERR", repr(e)[:80]); continue
        good = validate(rows)
        if not good:
            print(f, "no equations"); continue
        ns = sorted(good)
        bases = [good[n][1] for n in ns]
        print(f.split("/")[-1], "rows", len(rows), "validated", len(good), "base range", min(bases), max(bases), "gaps", sum(1 for a, b in zip(ns, ns[1:]) if b != a + 1), flush=True)
        out[f.split("/")[-1]] = {"rows": [list(good[n]) for n in ns]}
    json.dump(out, open(OUT, "w"))


main()
