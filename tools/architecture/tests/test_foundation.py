"""NEW FOUNDATION TESTS (Phase 1A): schemas, templates, and report-only invariants.

All inputs are the committed templates or synthetic fixtures built in tmp dirs.
No existing runtime is touched.
"""
import copy
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
import report  # noqa: E402
from jsonschema_lite import validate  # noqa: E402

SCHEMAS = os.path.join(ROOT, "contracts", "schemas")
TEMPLATE = os.path.join(ROOT, "brains", "_template")


def load(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return json.load(fh)


def schema(name):
    return load(SCHEMAS, name)


# ---- schemas are well-formed -------------------------------------------------
@pytest.mark.parametrize("name", sorted(f for f in os.listdir(SCHEMAS) if f.endswith(".json")))
def test_schema_files_are_well_formed(name):
    s = schema(name)
    assert s["$schema"].endswith("2020-12/schema")
    assert s["$id"].endswith(name)


# ---- templates validate ------------------------------------------------------
def test_brain_template_validates():
    assert validate(load(TEMPLATE, "brain.template.json"), schema("brain.schema.json")) == []


def test_research_templates_validate():
    assert validate(load(TEMPLATE, "research", "GAPS.template.json"), schema("research-gaps.schema.json")) == []
    assert validate(load(TEMPLATE, "research", "MANIFEST.template.json"), schema("research-manifest.schema.json")) == []


def test_providers_catalog_validates():
    assert validate(load(ROOT, "providers", "PROVIDERS.json"), schema("providers.schema.json")) == []


def test_operating_contract_template_has_all_19_sections_in_order():
    import re
    text = open(os.path.join(TEMPLATE, "BRAIN_OPERATING_CONTRACT.template.md"), encoding="utf-8").read()
    heads = [re.sub(r"^\d+\.\s*", "", h) for h in re.findall(r"^##\s+(.+)$", text, re.M)]
    assert heads == report.CONTRACT_HEADINGS
    assert "angler" not in text.lower()


# ---- brain.json rejection ----------------------------------------------------
def brain():
    return copy.deepcopy(load(TEMPLATE, "brain.template.json"))


@pytest.mark.parametrize("mutate,needle", [
    (lambda b: b.pop("brainId"), "brainId"),
    (lambda b: b.update(brainId="Bad_ID"), "brainId"),
    (lambda b: b.update(customerIntegrationMode="customerDirect"), "customerIntegrationMode"),
    (lambda b: b.update(customerIntegrationMode="direct"), "customerIntegrationMode"),
    (lambda b: b.update(lifecycle="BETA"), "lifecycle"),
    (lambda b: b.update(surprise=1), "surprise"),
    (lambda b: b.update(researchWorkspace={"workspaceId": "/Users/x/Desktop/Sector Research"}), "workspaceId"),
    (lambda b: b["runtime"].update(entrypoint="/Users/x/main.py"), None),
    (lambda b: b.update(tests=["/abs/tests"]), "tests"),
    (lambda b: b.update(publishesReason=None) or b.pop("publishesReason"), "publishesReason"),
    (lambda b: b["consumes"].append({"kind": "brain", "contractId": "x.y", "minVersion": "1.0.0"}), "brainId"),
    (lambda b: b.update(contractVersion="1.0"), "contractVersion"),
])
def test_malformed_brain_json_rejected(mutate, needle):
    b = brain()
    mutate(b)
    errs = validate(b, schema("brain.schema.json"))
    if needle is None:
        # entrypoint absolute-path guard is enforced by the architecture report (inv 6/9), not the schema
        return
    assert errs and any(needle in e for e in errs), errs


@pytest.mark.parametrize("mode", ["none", "embedded", "published"])
def test_customer_integration_mode_accepts_enum(mode):
    b = brain()
    b["customerIntegrationMode"] = mode
    assert validate(b, schema("brain.schema.json")) == []


def test_nonempty_publishes_needs_no_reason():
    b = brain()
    b.pop("publishesReason")
    b["publishes"] = [{"contractId": "wind.state", "version": "1.0.0", "pathFamilies": ["/wind"]}]
    assert validate(b, schema("brain.schema.json")) == []


# ---- providers rejection -----------------------------------------------------
def provider(**kw):
    p = {"providerId": "open-meteo", "acquisitionOwner": "platform", "healthOwner": "platform",
         "authorizedConsumers": ["engine", "wind"], "costClass": "free", "licenseRef": "LICENSE-REF"}
    p.update(kw)
    return {"schemaVersion": "1.0.0", "providers": [p]}


def test_provider_valid_and_separate_owner_fields_required():
    assert validate(provider(), schema("providers.schema.json")) == []
    for field in ("acquisitionOwner", "healthOwner", "authorizedConsumers", "costClass", "licenseRef"):
        cat = provider()
        cat["providers"][0].pop(field)
        assert validate(cat, schema("providers.schema.json")), field
    cat = provider()
    cat["providers"][0]["owner"] = "platform"  # vague single owner field is not allowed
    assert validate(cat, schema("providers.schema.json"))


def test_provider_rejects_bad_consumer_and_cost_class():
    assert validate(provider(authorizedConsumers=["Wind Brain"]), schema("providers.schema.json"))
    assert validate(provider(authorizedConsumers=[]), schema("providers.schema.json"))
    assert validate(provider(costClass="gratis"), schema("providers.schema.json"))


# ---- registries / research ---------------------------------------------------
def test_registry_schemas_accept_and_reject():
    lakes = {"schemaVersion": "1.0.0", "lakes": [{"lakeId": "L1", "displayName": "Test Lake", "state": "AL", "waterbodyClass": "reservoir"}]}
    assert validate(lakes, schema("registry-lakes.schema.json")) == []
    lakes["lakes"][0]["speciesPresence"] = ["bass"]  # per-lake species presence is not registry identity
    assert validate(lakes, schema("registry-lakes.schema.json"))
    sp = {"schemaVersion": "1.0.0", "species": [{"speciesId": "gar", "commonName": "Gar", "scientificName": "Lepisosteus"}]}
    assert validate(sp, schema("registry-species.schema.json")) == []
    sp["species"][0]["legality"] = "open"
    assert validate(sp, schema("registry-species.schema.json"))
    reg = {"schemaVersion": "1.0.0", "generatedFrom": ["brains/x/brain.json"], "edges": [],
           "brains": [{"brainId": "x", "directory": "brains/x", "lifecycle": "RESEARCH", "contractVersion": "1.0.0", "customerIntegrationMode": "none"}]}
    assert validate(reg, schema("registry-brains.schema.json")) == []


def test_gap_needs_stop_condition_and_valid_type():
    g = load(TEMPLATE, "research", "GAPS.template.json")
    g["gaps"][0].pop("stopCondition")
    assert validate(g, schema("research-gaps.schema.json"))
    g = load(TEMPLATE, "research", "GAPS.template.json")
    g["gaps"][0]["type"] = "curiosity"
    assert validate(g, schema("research-gaps.schema.json"))


def test_manifest_rejects_physical_path_and_bad_hash():
    m = load(TEMPLATE, "research", "MANIFEST.template.json")
    m["collections"][0]["backupLocationId"] = "/Users/x/Backups"
    assert validate(m, schema("research-manifest.schema.json"))
    m = load(TEMPLATE, "research", "MANIFEST.template.json")
    m["collections"][0]["contentHash"] = "md5:abc"
    assert validate(m, schema("research-manifest.schema.json"))


# ---- report-only architecture invariants on a synthetic repo -----------------
@pytest.fixture
def synth(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(os.path.join(ROOT, "contracts"), root / "contracts")
    (root / "providers").mkdir()
    shutil.copy(os.path.join(ROOT, "providers", "PROVIDERS.json"), root / "providers" / "PROVIDERS.json")
    (root / "brains").mkdir()
    return root


def make_brain(root, dirname, **over):
    d = root / "brains" / dirname
    (d / "runtime").mkdir(parents=True)
    (d / "tests").mkdir()
    b = brain()
    b.update(brainId=dirname, runtime={"kind": "job", "language": "python", "entrypoint": f"brains/{dirname}/runtime/main.py"},
             researchWorkspace={"workspaceId": f"{dirname}-brain"}, score={"type": "ENGINE_READINESS_SCORE", "path": f"/scores/{dirname}"},
             tests=[f"brains/{dirname}/tests"])
    b.update(over)
    (d / "brain.json").write_text(json.dumps(b))
    (d / "runtime" / "main.py").write_text("print('ok')\n")
    shutil.copy(os.path.join(TEMPLATE, "BRAIN_OPERATING_CONTRACT.template.md"), d / "BRAIN_OPERATING_CONTRACT.md")
    return d


def invs(root, **kw):
    return {(f["invariant"]) for f in report.check(str(root), **kw)}


def test_clean_synthetic_brain_has_no_findings(synth):
    make_brain(synth, "alpha")
    assert report.check(str(synth)) == []


def test_missing_and_malformed_brain_json_reported(synth):
    (synth / "brains" / "nojson").mkdir()
    bad = make_brain(synth, "bad")
    (bad / "brain.json").write_text("{not json")
    assert 1 in invs(synth)


def test_duplicate_brain_id_detected(synth):
    make_brain(synth, "alpha")
    make_brain(synth, "beta", brainId="alpha")
    msgs = [f["message"] for f in report.check(str(synth)) if f["invariant"] == 2]
    assert msgs and "alpha" in msgs[0]


def test_machine_id_rename_detected_for_locked_directory(synth):
    make_brain(synth, "fish", brainId="fish")  # must be biological-state
    assert 3 in invs(synth)
    shutil.rmtree(synth / "brains" / "fish")
    make_brain(synth, "fish", brainId="biological-state")
    assert 3 not in invs(synth)


def test_operating_contract_missing_section_detected(synth):
    d = make_brain(synth, "alpha")
    p = d / "BRAIN_OPERATING_CONTRACT.md"
    p.write_text(p.read_text().replace("## 17. COST RULES", "## 17. MONEY"))
    assert any("COST RULES" in f["message"] for f in report.check(str(synth)) if f["invariant"] == 4)
    (d / "BRAIN_OPERATING_CONTRACT.md").unlink()
    assert 4 in invs(synth)


def test_declared_contract_runtime_and_tests_must_exist(synth):
    make_brain(synth, "alpha", publishes=[{"contractId": "a.state", "version": "1.0.0", "schemaRef": "brains/alpha/contracts/a.json", "pathFamilies": ["/a"]}],
               tests=["brains/alpha/missing_tests"])
    i = invs(synth)
    assert 5 in i and 6 in i


def test_provider_must_be_registered_and_authorized(synth):
    make_brain(synth, "alpha", providers=[{"providerId": "ghost"}])
    assert 12 in invs(synth)
    (synth / "providers" / "PROVIDERS.json").write_text(json.dumps(provider(authorizedConsumers=["engine"])))
    shutil.rmtree(synth / "brains" / "alpha")
    make_brain(synth, "alpha", providers=[{"providerId": "open-meteo", "domainInterpreter": True}])
    msgs = [f["message"] for f in report.check(str(synth)) if f["invariant"] == 12]
    assert msgs and "authorizedConsumer" in msgs[0]
    (synth / "providers" / "PROVIDERS.json").write_text(json.dumps(provider(authorizedConsumers=["alpha"])))
    assert 12 not in invs(synth)


def test_brain_to_brain_private_import_and_undeclared_contract_use(synth):
    make_brain(synth, "alpha")
    make_brain(synth, "beta")
    (synth / "brains/alpha/runtime/main.py").write_text("from brains.beta.runtime import x\n")
    assert 7 in invs(synth)
    (synth / "brains/alpha/runtime/main.py").write_text("from brains.beta.contracts import x\n")
    i = invs(synth)
    assert 13 in i and 7 not in i


def test_consumes_must_target_published_contract(synth):
    make_brain(synth, "alpha", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0"}])
    assert 13 in invs(synth)


def test_platform_importing_brain_implementation(synth):
    make_brain(synth, "alpha")
    (synth / "platform").mkdir()
    (synth / "platform" / "x.py").write_text("import brains.alpha.runtime\n")
    assert 14 in invs(synth)


def test_runtime_docs_and_absolute_path(synth):
    d = make_brain(synth, "alpha")
    (d / "runtime" / "main.py").write_text("p='docs/data/x.json'\nq='/Users/someone/Desktop/x'\n")
    i = invs(synth)
    assert 8 in i and 9 in i


def test_writer_after_cutover_and_customer_dependency(synth):
    d = make_brain(synth, "alpha", publisherRequired={"required": True, "cutoverStatus": "CUTOVER_COMPLETE"})
    (d / "runtime" / "main.py").write_text("store = BrainRTDBStore()\nimport SectorEngine\n")
    i = invs(synth)
    assert 10 in i and 11 in i
    shutil.rmtree(d)
    make_brain(synth, "alpha", customerIntegrationMode="embedded").joinpath("runtime", "main.py").write_text("import SectorEngine\n")
    assert 11 not in invs(synth)


def test_research_dir_rejects_raw_data(synth):
    d = make_brain(synth, "alpha")
    (d / "research").mkdir()
    (d / "research" / "GAPS.json").write_text("{}")
    assert 16 not in invs(synth)
    (d / "research" / "obs.csv").write_text("a,b\n")
    (d / "research" / "notes.md").write_text("x")
    assert 16 in invs(synth)


def test_large_file_policy(synth):
    (synth / "big.bin").write_bytes(b"0" * (1024 * 1024))
    assert any(f["subject"] == "big.bin" for f in report.check(str(synth)) if f["invariant"] == 15)


# ---- G1/G2: dependency declarations, Signal Registry, invariant 17 ------------------------------
def test_signal_registry_validates_and_defines_no_consumers():
    reg = load(ROOT, "platform", "registries", "signals", "signals.json")
    assert validate(reg, schema("registry-signals.schema.json")) == []
    assert reg["signals"] and all(s["status"] == "DECLARED" and "producer" not in s for s in reg["signals"])
    assert "consumer" not in json.dumps(reg["signals"]).lower()
    bad = copy.deepcopy(reg); bad["signals"][0]["consumers"] = ["fish"]
    assert validate(bad, schema("registry-signals.schema.json"))                         # the registry can never say who consumes a signal
    bad = copy.deepcopy(reg); bad["signals"][0]["status"] = "LIVE"
    assert validate(bad, schema("registry-signals.schema.json"))


@pytest.mark.parametrize("entry,ok", [
    ({"kind": "signal", "signalId": "pressure-trend"}, True),
    ({"kind": "signal", "signalId": "pressure-trend", "requirement": "OPTIONAL", "freshness": {"maxAgeHours": 3, "reason": "needs a current trend"}}, True),
    ({"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0", "requirement": "REQUIRED"}, True),
    ({"kind": "signal"}, False),
    ({"kind": "brain", "brainId": "beta"}, False),                                        # a Brain edge still needs contractId + minVersion
    ({"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "requirement": "SOMETIMES"}, False),
    ({"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "freshness": {"maxAgeHours": 3}}, False),
    ({"kind": "registry", "registry": "lakes", "contractId": "registry.lakes", "minVersion": "1.0.0", "freshness": {"maxAgeHours": 0, "reason": "x"}}, False),
])
def test_brain_json_dependency_declaration_fields(entry, ok):
    b = brain(); b["consumes"].append(entry)
    assert (validate(b, schema("brain.schema.json")) == []) is ok


def test_provider_entries_accept_requirement_and_freshness():
    b = brain(); b["providers"] = [{"providerId": "open-meteo", "requirement": "OPTIONAL", "freshness": {"maxAgeHours": 6, "reason": "r"}}]
    assert validate(b, schema("brain.schema.json")) == []
    b["providers"][0]["requirement"] = "NICE_TO_HAVE"
    assert validate(b, schema("brain.schema.json"))


def _with_signals(root):
    (root / "platform" / "registries" / "signals").mkdir(parents=True, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "platform", "registries", "signals", "signals.json"), root / "platform" / "registries" / "signals" / "signals.json")


def test_invariant_17_signal_must_exist_in_the_registry(synth):
    _with_signals(synth)
    make_brain(synth, "alpha", consumes=[{"kind": "signal", "signalId": "pressure-trend"}])
    assert 17 not in invs(synth)
    shutil.rmtree(synth / "brains" / "alpha")
    make_brain(synth, "alpha", consumes=[{"kind": "signal", "signalId": "unicorn-index"}])
    msgs = [f["message"] for f in report.check(str(synth)) if f["invariant"] == 17]
    assert msgs and "not defined in the Signal Registry" in msgs[0]


def test_invariant_17_signal_without_any_registry_is_reported(synth):
    make_brain(synth, "alpha", consumes=[{"kind": "signal", "signalId": "pressure-trend"}])
    assert any("no Signal Registry" in f["message"] for f in report.check(str(synth)) if f["invariant"] == 17)


def test_invariant_17_platform_manifest_cannot_claim_an_undeclared_edge(synth):
    make_brain(synth, "alpha")
    make_brain(synth, "beta", publishes=[{"contractId": "beta.state", "version": "1.0.0", "pathFamilies": ["/b"]}], authorizedConsumers=["ops", "alpha"])
    man = synth / "jobs" / "brain_platform" / "sector_brain_platform"
    man.mkdir(parents=True)
    (man / "control_manifest.json").write_text(json.dumps({"engineMode": "PRE_PRODUCTION", "brains": {"alpha": {"dependencies": [{"id": "beta", "requirement": "OPTIONAL", "onStale": "DEPENDENCY_STALE"}]}}, "jobs": {}}))
    msgs = [f["message"] for f in report.check(str(synth)) if f["invariant"] == 17]
    assert msgs and "claims alpha -> beta" in msgs[0]
    shutil.rmtree(synth / "brains" / "alpha")
    make_brain(synth, "alpha", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0", "requirement": "OPTIONAL"}])
    assert 17 not in invs(synth)                                                            # the Brain declares it itself: the manifest may mirror it


def test_invariant_17_consumer_must_be_authorized_by_the_producer(synth):
    make_brain(synth, "beta", publishes=[{"contractId": "beta.state", "version": "1.0.0", "pathFamilies": ["/b"]}], authorizedConsumers=["ops"])
    make_brain(synth, "alpha", consumes=[{"kind": "brain", "brainId": "beta", "contractId": "beta.state", "minVersion": "1.0.0"}])
    assert any("authorizedConsumers" in f["message"] for f in report.check(str(synth)) if f["invariant"] == 17)


def test_real_repo_has_no_invariant_17_findings():
    assert [f for f in report.check(ROOT) if f["invariant"] == 17] == []


def test_template_directory_is_not_a_registered_brain(synth):
    shutil.copytree(TEMPLATE, synth / "brains" / "_template")
    assert report.check(str(synth)) == []


def test_report_is_report_only_by_default():
    assert report.main(["--root", ROOT]) == 0


def test_real_repo_registers_only_migrated_brains():
    # Wind (Phase 2), Fish (Phase 4, Fish Structural Certification V1) and Water Clarity (Water Clarity Structural Certification V1) are the migrated Brains.
    # No other brain.json may exist until that Brain migrates.
    assert report._brain_dirs(ROOT) == ["fish", "water-clarity", "wind"]


@pytest.mark.parametrize("src,flag", [
    ('u = "/conditions?lat=1&lon=2"', True), ('u = "https://engine.example/lakes"', True), ("u = '/lakes'", True),
    ("import SectorEngine", True), ('p = "/lakes/{k}/states/wind"', False), ('p = f"/lakes/{lk}/validation/{BRAIN}"', False),
    ('t = "production wind is Open-Meteo in /conditions."', False)])
def test_customer_endpoint_pattern_distinguishes_endpoint_from_rtdb_paths(src, flag):
    assert bool(report.CUSTOMER_PATTERN.search(src)) is flag


# ---- Phase 1B: large-file exceptions, baseline comparison --------------------------------------
def test_large_file_exceptions_file_validates_and_has_exact_paths_only():
    doc = load(ROOT, "tools", "architecture", "large_file_exceptions.json")
    assert validate(doc, schema("large-file-exceptions.schema.json")) == []
    assert len(doc["exceptions"]) == 5
    for e in doc["exceptions"]:
        assert e["status"] == "LEGACY_BASELINE" and e["createdBy"] == "Phase 1B baseline"
        assert not any(c in e["path"] for c in "*?[]")


@pytest.mark.parametrize("bad_path", ["docs/data/*.json", "/abs/file.bin", "dir/[ab].csv"])
def test_wildcard_or_absolute_exception_paths_rejected(bad_path):
    doc = {"schemaVersion": "1.0.0", "exceptions": [{"path": bad_path, "component": "c", "reason": "r", "status": "LEGACY_BASELINE", "reviewPhase": "p", "createdBy": "x"}]}
    assert validate(doc, schema("large-file-exceptions.schema.json"))


def test_real_repo_large_files_are_all_covered_by_legacy_exceptions():
    findings = report.check(ROOT)
    assert [f for f in findings if f["invariant"] == 15] == []
    assert len(report.check.last_excepted) == 5
    assert report.check.last_stale == []


def test_new_large_file_is_a_new_violation_known_exception_is_not(synth):
    (synth / "tools" / "architecture").mkdir(parents=True)
    (synth / "known.bin").write_bytes(b"0" * (1024 * 1024))
    exc = load(ROOT, "tools", "architecture", "large_file_exceptions.json")
    exc["exceptions"] = [dict(exc["exceptions"][0], path="known.bin")]
    # check() reads exceptions from the tool dir; emulate by pointing report.HERE-based loader at a temp copy
    orig = report.HERE
    shutil.copytree(os.path.join(ROOT, "tools", "architecture"), synth / "tools" / "architecture", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (synth / "tools" / "architecture" / "large_file_exceptions.json").write_text(json.dumps(exc))
    report.HERE = str(synth / "tools" / "architecture")
    try:
        assert [f for f in report.check(str(synth)) if f["invariant"] == 15] == []
        (synth / "new.bin").write_bytes(b"0" * (1024 * 1024 + 1))
        assert [f["subject"] for f in report.check(str(synth)) if f["invariant"] == 15] == ["new.bin"]
        (synth / "known.bin").write_bytes(b"0")
        report.check(str(synth))
        assert report.check.last_stale == ["known.bin"]
    finally:
        report.HERE = orig


def test_baseline_known_new_resolved():
    base = {"entries": [{"key": "8|a.py|m", "invariant": 8, "path": "a.py"}, {"key": "9|gone.py|m", "invariant": 9, "path": "gone.py"}]}
    findings = [{"invariant": 8, "subject": "a.py", "message": "m"}, {"invariant": 9, "subject": "new.py", "message": "m"}]
    known, new, resolved = report.compare_to_baseline(findings, base)
    assert [f["subject"] for f in known] == ["a.py"]
    assert [f["subject"] for f in new] == ["new.py"]
    assert [e["path"] for e in resolved] == ["gone.py"]


def test_committed_baseline_matches_current_legacy_findings_and_has_owner_phase():
    base = load(ROOT, "tools", "architecture", "baseline", "legacy_violations.json")
    known, new, resolved = report.compare_to_baseline(report.check(ROOT, legacy=True), base)
    assert new == [] and resolved == []
    assert len(known) == len(base["entries"])
    for e in base["entries"]:
        assert e["owner"] != "unassigned" and e["plannedMigrationPhase"] and e["reason"] and e["status"] == "LEGACY_BASELINE"


def test_baseline_cli_is_report_only_and_fail_on_new_is_opt_in(tmp_path, capsys):
    empty = tmp_path / "b.json"
    empty.write_text(json.dumps({"entries": []}))
    n = len(report.check(ROOT, legacy=True))
    assert report.main(["--root", ROOT, "--legacy", "--baseline", str(empty)]) == 0     # NEW findings, still exit 0
    assert f"NEW findings (not in baseline):      {n}" in capsys.readouterr().out
    assert report.main(["--root", ROOT, "--legacy", "--baseline", str(empty), "--fail-on-new"]) == 1


def test_python_scan_ignores_docstrings_and_comments_but_flags_string_literals(tmp_path):
    src = '"""See docs/brains/X.md and /Users/me/Desktop/y"""\n# docs/brains/c.md\nP = "docs/brains/real.json"\n'
    assert "docs/brains/real.json" in report._code_text("m.py", src)
    assert "X.md" not in report._code_text("m.py", src) and "c.md" not in report._code_text("m.py", src)


def test_report_output_contains_paths_not_content(synth, capsys):
    d = make_brain(synth, "alpha")
    (d / "runtime" / "main.py").write_text("SECRET_TOKEN='abc123'\nq='/Users/someone/Desktop/x'\n")
    report.main(["--root", str(synth)])
    out = capsys.readouterr().out
    assert "abc123" not in out and "SECRET_TOKEN" not in out
