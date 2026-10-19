"""The kit encodes HOW a Brain is certified, never WHAT a Brain knows. These guards fail the build if a Brain name, a domain term or a per-Brain conditional
creeps into the shared code."""
import os
import re

KIT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brain_cert_kit")
SOURCES = {f: open(os.path.join(KIT, f), encoding="utf-8").read() for f in sorted(os.listdir(KIT)) if f.endswith(".py")}

BRAIN_NAMES = re.compile(r"\b(fish|wind|clarity|biological|lake[- ]brain|water[- ]temp(erature)?|depth|vegetation|sector[- ]intelligence)\b", re.I)
DOMAIN_TERMS = re.compile(r"\b(secchi|turbidity|sentinel|rtma|nbm|metar|species|spawn|gust|forecast|rainfall|bathymetry|chlorophyll|ndci|nws)\b", re.I)
PER_BRAIN_CONDITIONAL = re.compile(r"(brain_id|directory|\.brain)\s*(==|!=|in|not in)\s*[\(\[\{]?\s*['\"]|if\s+['\"][a-z-]+['\"]\s+in\s+.*brain")


def test_no_brain_names_in_shared_code():
    hits = [(f, m.group(0)) for f, s in SOURCES.items() for m in BRAIN_NAMES.finditer(s)]
    assert not hits, f"Brain names in the shared kit (parametrise through the spec instead): {hits}"


def test_no_domain_terms_in_shared_code():
    hits = [(f, m.group(0)) for f, s in SOURCES.items() for m in DOMAIN_TERMS.finditer(s)]
    assert not hits, f"domain science terms in the shared kit: {hits}"


def test_no_per_brain_conditionals_in_shared_code():
    hits = [(f, i + 1, line.strip()[:100]) for f, s in SOURCES.items() for i, line in enumerate(s.splitlines()) if PER_BRAIN_CONDITIONAL.search(line)]
    assert not hits, f"per-Brain conditionals in the shared kit: {hits}"


def test_kit_imports_only_stdlib_platform_and_pytest():
    allowed = {"__future__", "ast", "copy", "dataclasses", "datetime", "importlib", "itertools", "json", "os", "random", "re", "subprocess", "sys", "typing", "uuid", "pytest",
               "sector_brain_platform", "jsonschema_lite", "report", "brain_cert_kit"}
    for f, s in SOURCES.items():
        for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z_][\w]*)", s, re.M):
            assert m.group(1) in allowed, f"{f} imports {m.group(1)}"


def test_no_hardcoded_absolute_or_private_paths_in_the_kit():
    for f, s in SOURCES.items():
        assert not re.search(r"/Users/[A-Za-z0-9_.-]+/|~/Desktop/[A-Za-z]|gs://[a-z]", s), f
