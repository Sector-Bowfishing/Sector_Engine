#!/usr/bin/env python3
"""Parse NWS Huntsville 'Daily River and Lake Summary' (RVDHUN) text archive (IEM AFOS) into
daily pool elevation per TVA mainstem project. Output csv: date,station,name,value_ft,hr_local_label
usage: parse_rvdhun.py <in_dir> <out_csv>"""
import re, sys, glob, csv
inp, out = sys.argv[1:3]
rows = []
for f in sorted(glob.glob(f"{inp}/rvdhun_*.txt")):
    txt = open(f, errors="replace").read()
    for prod in re.split(r"(?m)^RVDHUN\s*$", txt)[1:]:
        m = re.search(r"DC(\d{4})(\d{2})(\d{2})(\d{4})", prod)
        if not m: continue
        date = f"{m[1]}-{m[2]}-{m[3]}"
        hdr = re.search(r"(\d+AM|\d+ AM)", prod)
        blk = None
        for ln in prod.splitlines():
            if ln.startswith(".B ") and "/HP/" in ln: blk = "HP"
            elif ln.startswith(".B ") and "/HG/" in ln: blk = "HG"
            elif ln.startswith(".END"): blk_end = True
            if blk != "HP": continue
            mm = re.match(r"^([A-Z]{3}[A-Z0-9]{2}):\s*([A-Za-z .&/]+?)\s*[\d.]*\s*:\s*(M|-?\d+\.\d+)\s*/", ln)
            if mm:
                sid, name, val = mm.groups()
                rows.append((date, sid, name.strip(), "" if val == "M" else val, m[4]))
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["date", "station", "name", "value_ft", "issue_hhmm"]); w.writerows(rows)
print(len(rows))
