#!/usr/bin/env python3
"""Depth Brain / TWDB reference-pool verification (PART A): cross-check what the TWDB final reports say (text extracted from the PDFs under
<RAW>/twdb2 with pypdf) against the elevation-area tables used by the research pipeline. Records only what the report text says, plus
the table area at the stated conservation pool and at the shares' basis elevation. Run with the lake-brain venv python, -I.
Output docs/brains/depth/data/twdb_report_facts.json."""
import hashlib, json, re
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
W = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/twdb2")
T = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain/twdb")
BASE = "https://www.twdb.texas.gov/surfacewater/surveys/completed/files/"
LAKES = {  # id: (table key, report pdf stem, url path, stated conservation pool by regex target, basis ft from terrain/twdb_truth.json)
    "Cedar Creek Reservoir|TX": ("CedarCreek_2017-10", "CedarCreek2017_FinalReport2", "CedarCreek/2017-10/CedarCreek2017_FinalReport2.pdf", 322.0, 322.0),
    "Lake Conroe|TX": ("conroe_2020-10", "Conroe2020_FinalReport", "conroe/2020-10/Conroe2020_FinalReport.pdf", 201.0, 201.0),
    "Lake Fork Reservoir|TX": ("Fork_2009-10", "Fork2009_FinalReport", "Fork/2009-10/Fork2009_FinalReport.pdf", 403.0, 403.0),
    "Lake Livingston|TX": ("Livingston_2019-11", "Livingston2019_FinalReport", "Livingston/2019-11/Livingston2019_FinalReport.pdf", 131.0, 131.1),
    "Lake Tawakoni|TX": ("tawakoni_2009-08", "Tawakoni2009_FinalReport", "tawakoni/2009-08/Tawakoni2009_FinalReport.pdf", 437.5, 437.5),
    "Lake Texoma|TX": ("Texoma_2002-07", "Texoma2002_FinalReport", "Texoma/2002-07/Texoma2002_FinalReport.pdf", 617.0, 620.0)}
M2_FT2_PER_AC = 43560.0


def table(p):
    a = []
    for line in open(p):
        try:
            e, ar, c = [float(x) for x in line.strip().split(",")[:3]]; a.append((abs(e), ar))
        except Exception:
            pass
    a = np.array(sorted(a)); return a[:, 0], a[:, 1]


out = {}
for lid, (key, stem, path, cp, basis) in LAKES.items():
    txt = (W / f"{stem}.txt").read_text(errors="ignore")
    flat = re.sub(r"\s+", " ", txt)
    m_ac = re.search(r"encompass\w*\s+([\d,]+)\s+(?:surface\s+)?acres", flat)
    rep_ac = float(m_ac.group(1).replace(",", "")) if m_ac else None
    z, A = table(T / key / "table.txt"); unit = M2_FT2_PER_AC if A.max() > 2e6 else 1.0
    ac = lambda e: float(np.interp(e, z, A)) / unit
    datum = [s for s in ("NGVD29", "NAVD88") if s in flat]
    dates = re.findall(r"(?:between|from) ([A-Z][a-z]+ \d{1,2}(?:, \d{4})?,? (?:and|through|to) [A-Z][a-z]+ \d{1,2}, \d{4})", flat)[:2]
    pdf = W / f"{stem}.pdf"
    out[lid] = dict(reportUrl=BASE + path, pdfSha256=hashlib.sha256(pdf.read_bytes()).hexdigest(), pdfBytes=pdf.stat().st_size,
                    reportAcresAtConservationPool=rep_ac, statedConservationPoolFt=cp, tableAcresAtConservationPool=round(ac(cp), 1),
                    tableAcresAtBasis=round(ac(basis), 1), basisFt=basis, tableTopFt=float(z[-1]), tableBottomFt=float(z[0]), tableStepFt=round(float(np.median(np.diff(z))), 3),
                    areaRatioTableOverReportAtConservationPool=(round(ac(cp) / rep_ac, 4) if rep_ac else None), datumLabelsInReportText=datum, surveyDateSnippets=dates)
(REPO / "docs/brains/depth/data").mkdir(parents=True, exist_ok=True)
(REPO / "docs/brains/depth/data/twdb_report_facts.json").write_text(json.dumps(out, indent=1))
for k, v in out.items():
    print(k, v["reportAcresAtConservationPool"], v["tableAcresAtConservationPool"], v["tableAcresAtBasis"], v["tableTopFt"], v["datumLabelsInReportText"], v["surveyDateSnippets"])
