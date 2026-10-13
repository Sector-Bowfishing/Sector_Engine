"""Data selection + series loading for holdout_v2.py (kept apart so the protocol file reads as the protocol).

Test set (fixed by the adoption kickoff, before any result): the strict binding rows of docs/research/lake-brain/data/verified_bindings_v2.csv
(waves w1 + w2-v1, status VERIFIED / VERIFIED_CORROBORATED) MINUS rows carrying a v1.1 rule tag (Clinton Lake|IL), MINUS providers whose only endpoint is
undocumented (UNDOCUMENTED), MINUS lakes whose directory coordinate carries any point_flag other than 'ok' (identity_risk / off_water / not assessed).
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import os
import re

import numpy as np

ENGINE_RESEARCH = "/Users/mcather/Desktop/Development/Sector_Engine"                # research checkout (read-only)
DATA = "/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain"          # (the kickoff said ~/Desktop/Sector_Research_Data; it lives under Development/)
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
V2 = os.path.join(ENGINE_RESEARCH, "docs", "research", "lake-brain", "data", "verified_bindings_v2.csv")
FEATURES = os.path.join(ENGINE_RESEARCH, "docs", "research", "lake-brain", "data", "lake_features.csv")
FLAGS = os.path.join(DATA, "geometry", "lake_geometry_flags.csv")
FULL_V2 = os.path.join(DATA, "binding2", "verified_v2_full.csv")
UNDOCUMENTED = {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg"}
TVA_PILOTS = {"Guntersville|AL": "GVDA1", "Wheeler|AL": "WHLA1", "Wilson|AL": "WLSA1", "Pickwick Lake|TN": "PICT1"}
TODAY_YEAR = 2026                                                                    # complete years are < the year of the run (2026-10-13)


def directory_pool_basis() -> dict:
    """{lakeId: 'fullPool'|'naturalSurface'} parsed from the Swift directory (the code under test)."""
    out = {}
    with open(os.path.join(REPO, "Sources", "SectorEngine", "Support", "LakeDirectory.swift")) as f:
        for line in f:
            line = line.strip().rstrip(",")
            if line.startswith('{"name"'):
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                out[f"{o['name']}|{o['state']}"] = o.get("poolBasis")
    return out


def _norm(x: str) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]+", "_", x)


def slug(lake_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id).strip("_")


def read_daily(path: str) -> dict:
    """date -> ft from a gz/plain CSV (date,value[,..]); header tolerated. v <= 1.0 is a RISE placeholder, dropped (as in the v1 harness)."""
    out = {}
    op = gzip.open if path.endswith(".gz") else open
    with op(path, "rt") as fh:
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 2 or not parts[1]:
                continue
            try:
                d, v = dt.date.fromisoformat(parts[0][:10]), float(parts[1])
            except ValueError:
                continue
            if v > 1.0:
                out[d] = v
    return out


def complete_years(daily: dict, today_year: int = TODAY_YEAR) -> list:
    n = {}
    for d in daily:
        n[d.year] = n.get(d.year, 0) + 1
    return sorted(y for y, c in n.items() if c >= 329 and y < today_year)


def selection() -> tuple:
    """-> (selected rows list, exclusion counts dict)."""
    rows = [r for r in csv.DictReader(open(V2)) if r["wave"] in ("w1", "w2-v1") and r["binding_status"] in ("VERIFIED", "VERIFIED_CORROBORATED")]
    ex = {"strict": len(rows)}
    keep = [r for r in rows if "v1.1" not in r["checks_passed"]]
    ex["v1.1-tagged"] = len(rows) - len(keep)
    rows = keep
    keep = [r for r in rows if r["provider"] not in UNDOCUMENTED]
    ex["undocumented-provider"] = len(rows) - len(keep)
    rows = keep
    flags = {r["id"]: r["point_flag"] for r in csv.DictReader(open(FLAGS))}
    keep = [r for r in rows if flags.get(r["lake_id"]) == "ok"]
    ex["coordinate-flag"] = len(rows) - len(keep)
    ex["coordinate-flag-detail"] = {}
    for r in rows:
        if flags.get(r["lake_id"]) != "ok":
            k = flags.get(r["lake_id"]) or "(blank/not assessed)"
            ex["coordinate-flag-detail"][k] = ex["coordinate-flag-detail"].get(k, 0) + 1
    ex["tested-set"] = len(keep)
    return keep, ex


def candidate_files(r: dict, hist_label: str) -> list:
    """Every history file that could hold this lake's daily series: [(label, path)]."""
    out = []
    lake = r["lake_id"]
    if lake in TVA_PILOTS:
        return [("tva_pilots", os.path.join(DATA, "history", "tva_pilots", f"{TVA_PILOTS[lake]}_daily.csv"))]
    hdir = os.path.join(DATA, "binding", "history")
    h2 = os.path.join(DATA, "binding2", "history")
    norm = {f[:-7]: os.path.join(hdir, f) for f in os.listdir(hdir) if f.endswith(".csv.gz")}
    norm2 = {f[:-7]: os.path.join(h2, f) for f in os.listdir(h2) if f.endswith(".csv.gz")}
    if hist_label:
        kind, _, rest = hist_label.partition(":")
        if kind == "b2":
            out.append((hist_label, os.path.join(h2, rest)))
        elif kind == "hads":
            out.append((hist_label, os.path.join(h2, "hads_" + rest.replace(":", "_") + ".csv.gz")))
        elif kind == "usgsiv":
            out.append((hist_label, os.path.join(h2, "usgsiv_" + rest.replace(":", "_") + ".csv.gz")))
        else:
            s0 = hist_label[:-3] if hist_label.endswith((":dv", ":iv")) else hist_label
            p = norm.get(_norm(s0)) or norm2.get(_norm(s0))
            if p:
                out.append((hist_label, p))
    # wave-1 per-binding history results for this lake
    res = _history_results()
    for k, v in res.items():
        parts = k.split("|")
        if len(parts) >= 2 and parts[0] + "|" + parts[1] == lake and (v or {}).get("best"):
            s = v["best"]["series"]
            s0 = s[:-3] if s.endswith((":dv", ":iv")) else s
            p = norm.get(_norm(s0))
            if p:
                out.append((s, p))
    comp = os.path.join(DATA, "plan", "history", "composite", slug(lake) + ".csv.gz")
    if os.path.exists(comp):
        out.append(("plan-composite", comp))
    seen, uniq = set(), []
    for lab, p in out:
        if p not in seen and os.path.exists(p):
            seen.add(p); uniq.append((lab, p))
    return uniq


_HR = None


def _history_results() -> dict:
    global _HR
    if _HR is None:
        _HR = json.load(open(os.path.join(DATA, "binding", "history_results.json")))
    return _HR


def load_lake_series(r: dict, hist_label: str) -> tuple:
    """-> (label, path, daily, alternatives[{label, completeYears}]); the candidate with the most complete years wins (ties: first listed)."""
    best, alts = None, []
    for lab, p in candidate_files(r, hist_label):
        d = read_daily(p)
        cy = len(complete_years(d))
        alts.append({"label": lab, "completeYears": cy})
        if best is None or cy > best[3]:
            best = (lab, p, d, cy)
    if best is None:
        return None, None, {}, alts
    return best[0], best[1], best[2], alts
