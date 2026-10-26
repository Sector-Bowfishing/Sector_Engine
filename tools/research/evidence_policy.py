#!/usr/bin/env python3
"""Evidence policy of the research automation (owner directive 2026-10-26): owner-collected field data is OPTIONAL, never mandatory.

New field tests, bowfishing trip logs, handheld measurements, sonar transects and field-observation quotas never block research completion, a capability
dimension, candidate scoring or internal app testing. Existing scientific observations (agency surveys, historical measurements, public datasets, literature)
remain evidence, and the Brains advance on those. This module is the single place that recognises owner-collected-data requirements so every layer
(ledger, owner actions, agent briefs, validators, tests) treats them the same way. The policy itself is data: tools/research/evidence_policy.json.
"""
from __future__ import annotations

import json
import os
import re

POLICY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence_policy.json")


def load() -> dict:
    return json.load(open(POLICY_PATH, encoding="utf-8"))


_RX = None


def _rx():
    global _RX
    if _RX is None:
        _RX = re.compile("|".join(load()["ownerCollectedPatterns"]), re.I)
    return _RX


def is_owner_collected(*texts) -> bool:
    """True when the text asks the owner (or a person on the water) to collect NEW data: site-nights, trip logs, handheld readings, sonar transects, a deployed anemometer,
    field campaigns, prospective field trials. Existing agency/public/historical records are not owner-collected."""
    return bool(_rx().search(" ".join(str(t) for t in texts if t)))


def validation_methods() -> list:
    return [m["id"] for m in load()["acceptedValidationMethods"]]
