"""Blinded field packet for ANY lake with candidate pairs (generalises the four-lake `fieldops packet`).

A packet contains what the observer needs and NOTHING about the prediction:
  OBSERVER-SHEET.csv   neutral labels X/Y per pair (order randomised deterministically), coordinates, map links, blank record fields
  RECORD-TEMPLATE.json one `sector-wind-field-v2` stub per bank (observer fills water/bank/boat control/confidence/wind)
  SESSION-README.txt   the one-minute procedure
  MAP-LINKS.txt
  SEALED-KEY.json      scorer only: which bank is A/B, predicted labels/Hm0/fetch, planning wind (never given to the observer)
Deterministic: same inputs -> same bytes."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime

from . import field_schema as FS

PACKET_SCHEMA = "sector-wind-field-packet-v1"


def _neutral(session_id: str, pair_id: str) -> tuple[str, str]:
    """Which of (A, B) is shown as X. Deterministic coin from the session and pair id."""
    return ("A", "B") if int(hashlib.sha256(f"{session_id}|{pair_id}".encode()).hexdigest(), 16) % 2 == 0 else ("B", "A")


def build(lake_entry: dict, pairs: list[dict], session_date: str, observer: str, out_dir: str, practice: bool = False, planning_wind: dict | None = None) -> dict:
    """lake_entry: one element of data/field_pairs_candidates.json; pairs: the chosen pair dicts from it; returns a summary of what was written."""
    lake = lake_entry["lake"]
    sid = f"{lake}|{session_date}|{observer}"
    os.makedirs(out_dir, exist_ok=True)
    sheet, key, template, links = [], [], [], []
    for n, p in enumerate(pairs, 1):
        pid = f"P{n}"
        first, second = _neutral(sid, pid)
        for neutral, role in (("X", first), ("Y", second)):
            side = p[role]["at12"]
            lat, lon = side["anchor"]
            bid = f"{pid}-{neutral}"
            link = f"https://maps.apple.com/?ll={lat:.5f},{lon:.5f}&q={bid}"
            sheet.append({"pairId": pid, "bank": neutral, "bankRef": side["bankId"], "latitude": f"{lat:.5f}", "longitude": f"{lon:.5f}", "mapLink": link,
                          "waterSurface(calm|light|choppy|rough)": "", "bankExposure(EXPOSED|PROTECTED|UNSURE)": "", "boatControl(easy|noticeable|difficult)": "",
                          "confidence(1-3)": "", "windFromDeg": "", "windSpeedMph": "", "observedAtUtc": "", "photo": ""})
            links.append(f"{bid}: {link}")
            key.append({"pairId": pid, "bank": neutral, "role": role, "bankId": side["bankId"], "predictedLabel": side["label"], "highFetch": side["highFetch"],
                        "effectiveFetchM": side["effectiveFetchM"], "predictedHm0In": side["predictedHm0In"], "type": p["type"], "axis": p["axis"]})
            template.append({"schema": FS.SCHEMA, "id": f"{sid}|{bid}", "lakeId": lake, "bankId": side["bankId"], "observedAtUtc": None, "observer": observer,
                             "roughnessObserved": None, "bankImpactObserved": None, "boatability": None, "observerConfidence": None, "observerSawPrediction": False,
                             "wind": {"source": "visualEstimate", "speedMph": None, "directionFromDeg": None}, "pairId": f"{sid}|{pid}", "pairRole": role, "tags": ["practice"] if practice else []})
    sealed = {"SEALED": "Scorer only. The observer must not open this file before submitting every record.", "schema": PACKET_SCHEMA, "sessionId": sid, "lake": lake,
              "geometryTier": lake_entry["tier"], "geometryConfidence": lake_entry["geometryConfidence"], "planningWind": planning_wind,
              "pairs": [{"pairId": f"P{i}", "type": p["type"], "axis": p["axis"], "windFromDegForAExposed": p["windFromDeg_forAasExposed"], "distanceM": p["distanceM"]} for i, p in enumerate(pairs, 1)],
              "banks": key, "practice": practice}
    json.dump(sealed, open(os.path.join(out_dir, "SEALED-KEY.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(out_dir, "OBSERVER-SHEET.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0])); w.writeheader(); w.writerows(sheet)
    json.dump(template, open(os.path.join(out_dir, "RECORD-TEMPLATE.json"), "w"), indent=1, sort_keys=True)
    open(os.path.join(out_dir, "MAP-LINKS.txt"), "w").write("\n".join(links) + "\n")
    est = lake_entry["tier"] == "ESTIMATED"
    open(os.path.join(out_dir, "SESSION-README.txt"), "w").write(f"""SECTOR WIND BANK-PAIR SESSION - {lake} - {session_date} - {observer}{'  [PRACTICE]' if practice else ''}
{'=' * 72}
Pairs: {len(pairs)}   Banks: {len(sheet)}   Visit X and Y of the same pair within 60 minutes. Same wind device, same height, 60-second average if you have one.
ONE MINUTE PER BANK, 30-100 m off the bank, boat head to the wind:
  1. Water surface: calm / light / choppy / rough
  2. Is the wind reaching this bank?  EXPOSED / PROTECTED / UNSURE{'' if est else '   (optional on audited lakes: DIRECT or CROSS)'}
  3. Boat control: easy / noticeable / difficult
  4. Confidence 1 (guess) - 3 (sure); wind direction FROM and speed if you measured it (note the height above the water)
  5. One photo looking upwind from the boat.
Conditions that count: wind 8-15 mph from the pair's axis (+-25 deg), steady 3 hours. Skip lightning and anything unsafe.
Do NOT open SEALED-KEY.json. Do not look at any Sector wind prediction until every record is submitted.
Export the filled records (RECORD-TEMPLATE.json shape) to the intake folder; records are never edited after export.
""")
    return {"files": sorted(os.listdir(out_dir)), "banks": len(sheet), "sessionId": sid}
