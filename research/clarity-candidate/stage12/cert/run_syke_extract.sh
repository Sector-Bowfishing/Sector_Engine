#!/bin/bash
# Certification protocol section 3 + addendum B: SYKE candidates matched by year (2017: sentinel-2-l2a offset 0;
# 2022: sentinel-2-l2a offset -0.1; other years: the production C1 collection). Concatenates into out_syke.csv.
cd "$(dirname "$0")"
G=../../geo/bin/python
$G - <<'PY'
import csv
R = list(csv.DictReader(open("syke_candidates.csv")))
for tag, cond in (("s17", lambda r: r["date"].startswith("2017")), ("s22", lambda r: r["date"].startswith("2022")), ("sc1", lambda r: r["date"][:4] not in ("2017", "2022"))):
    with open(f"in_{tag}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(R[0].keys())); w.writeheader(); w.writerows([r for r in R if cond(r)])
print("split done")
PY
CERT_COLLECTION=sentinel-2-l2a CERT_OFFSET=0 $G extract_cert.py in_s17.csv out_s17.csv --max-dt 1 --workers 6 > ex_s17.log 2>&1 &
CERT_COLLECTION=sentinel-2-l2a CERT_OFFSET=0 $G extract_cert.py in_s22.csv out_s22.csv --max-dt 1 --workers 6 > ex_s22.log 2>&1 &
$G extract_cert.py in_sc1.csv out_sc1.csv --max-dt 1 --workers 8 > ex_sc1.log 2>&1 &
wait
$G - <<'PY'
import csv
rows, cols = [], None
for t in ("s17", "s22", "sc1"):
    try:
        r = list(csv.DictReader(open(f"out_{t}.csv"))); rows += r; cols = cols or (list(r[0].keys()) if r else None)
    except FileNotFoundError:
        pass
with open("out_syke.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
print("SYKE_EXTRACT_DONE", len(rows))
PY
