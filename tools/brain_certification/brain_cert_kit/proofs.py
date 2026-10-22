"""The structural-certification proofs (Brain Factory V1 §7), parametrised by a BrainCertSpec. Each proof raises AssertionError with a precise message.

Rules for this module: no Brain is named, no domain value is encoded; everything Brain-specific comes from the spec, the Brain's own files, or the Publisher
registry. A proof that cannot apply to a Brain is declared in `spec.not_applicable` with a reason (it is skipped visibly, never silently)."""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys

from .env import Env, GEN, normalise_family, uid, walk_files, write_sites, imported_roots

HEAD_RE = re.compile(r"^## (\d+)\. (.+)$", re.M)


def _fail(msg):
    raise AssertionError(msg)


def p01_location_and_shape(E: Env):
    s = E.spec
    missing = [p for p in s.required_files if not os.path.exists(os.path.join(s.brain_dir, p))]
    assert not missing, f"canonical package files missing: {missing}"
    ids = E.load("tools", "architecture", "stable_brain_ids.json")["directoryToBrainId"]
    assert ids.get(s.directory) == s.brain_id, f"stable_brain_ids.json maps {s.directory!r} to {ids.get(s.directory)!r}, expected {s.brain_id!r}"


def p02_one_production_implementation(E: Env):
    s = E.spec
    canon = os.path.join(s.brain_dir, s.runtime_dir) + os.sep
    skip = os.sep + "tests" + os.sep
    for name in s.unique_module_basenames:
        found = [p for p in walk_files(E.root, (name,)) if os.path.basename(p) == name and skip not in p]
        stray = [E.rel(p) for p in found if not p.startswith(canon)]
        assert found and not stray, f"{name}: expected exactly one implementation under {E.rel(canon)}, found outside: {stray}"
    if s.legacy_pointer_dir:
        d = os.path.join(E.root, s.legacy_pointer_dir)
        assert sorted(os.listdir(d)) == ["README.md"], f"{s.legacy_pointer_dir} must contain only the retirement pointer README.md, has {sorted(os.listdir(d))}"
        assert re.search(r"RETIRED|Moved|moved", open(os.path.join(d, "README.md"), encoding="utf-8").read()), "pointer README does not say the directory moved/retired"


def p03_identity_lifecycle_publisher_state(E: Env):
    s, b = E.spec, E.brain_json
    errs = E.jsonschema_lite.validate(b, E.load("contracts", "schemas", "brain.schema.json"))
    assert errs == [], f"brain.json invalid: {errs}"
    assert b["brainId"] == s.brain_id, "brainId changed (machine ids are never renamed)"
    assert b["researchWorkspace"] == {"workspaceId": s.workspace_id}, "researchWorkspace must be a LOGICAL id"
    assert b["lifecycle"] == s.lifecycle, f"brain.json lifecycle {b['lifecycle']} != declared {s.lifecycle}"
    assert b["publisherRequired"] == {"required": True, "cutoverStatus": s.cutover_status}, f"publisherRequired {b['publisherRequired']}"
    assert b["customerIntegrationMode"] == s.customer_integration_mode
    assert b["runtime"]["kind"] == s.runtime_kind
    assert sorted(b.get("authorizedConsumers", [])) == sorted(s.authorized_consumers), f"authorizedConsumers {b.get('authorizedConsumers')}"
    if s.has_score:
        assert (b.get("score") or {}).get("path") == f"/scores/{s.brain_id}", f"score path {(b.get('score') or {}).get('path')}"
    else:
        assert "score" not in b, "a Brain declared without a score (has_score=False) must not declare a score block"
    assert not re.search(s.local_path_regex, json.dumps(b)), "brain.json contains a local/Desktop/research path"
    cm = E.load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")["brains"].get(s.brain_id)
    assert cm is not None, "control manifest has no entry for this Brain"
    assert cm["lifecycle"] == b["lifecycle"], f"lifecycle drift: control manifest {cm['lifecycle']} vs brain.json {b['lifecycle']} (debt D-9: no generic gate yet)"
    lin = E.artifact()["lineage"]
    assert lin["lifecycle"] == b["lifecycle"], f"artifact lineage lifecycle {lin['lifecycle']} != brain.json {b['lifecycle']}"
    declared = {c.get("brainId") for c in b["consumes"] if c["kind"] == "brain"}
    claimed = {d["id"] for d in cm.get("dependencies", [])}
    assert claimed <= declared, f"platform manifest claims edges the Brain does not declare: {sorted(claimed - declared)}"


def p04_operating_contract(E: Env):
    s = E.spec
    text = E.read("brains", s.directory, "BRAIN_OPERATING_CONTRACT.md")
    heads = [h for _, h in HEAD_RE.findall(text)]
    assert heads == E.report.CONTRACT_HEADINGS, f"operating contract headings differ from the 19-section standard: {heads}"
    missing = [t for t in s.contract_tokens + s.contract_required_terms if t not in text]
    assert not missing, f"operating contract does not state: {missing}"
    present = [t for t in s.contract_forbidden_terms if t.lower() in text.lower()]
    assert not present, f"operating contract contains forbidden terms: {present}"
    assert not re.search(r"/Users/|/home/[a-z]|~/Desktop|Desktop/Development", text), "operating contract contains an absolute local path"


def p05_published_contract_derived_from_registry(E: Env):
    s = E.spec
    describe = os.path.join(s.brain_dir, s.describe_module)
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([os.path.join(E.root, "jobs", "brain_platform"), os.path.join(E.root, "tools", "brain_certification")])}
    r = subprocess.run([sys.executable, describe, "--check"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, f"published contract is stale or undescribable: {r.stdout}{r.stderr}"
    contract = json.load(open(os.path.join(s.brain_dir, s.contract_file), encoding="utf-8"))
    assert contract["contractId"] == s.bundle_id and contract["brainId"] == s.brain_id and contract["envelope"] == "publish-artifact-v2"
    b = E.brain_json
    assert [p["contractId"] for p in b["publishes"]] == [s.bundle_id]
    declared = sorted(b["publishes"][0]["pathFamilies"])
    from_registry = sorted(f["pattern"] for sec in contract["sections"] for f in sec["families"])
    assert declared == from_registry, f"brain.json pathFamilies drifted from the Publisher registry: {sorted(set(declared) ^ set(from_registry))}"
    assert [sec["schemaId"] for sec in contract["sections"]] == sorted(E.registry.bundle(s.bundle_id).sections), "contract sections differ from the registered bundle"
    assert contract["status"].startswith("SHADOW"), "a contract may only be described as SHADOW until cutover"
    if s.providers_match_registry_sources:
        assert sorted(p["providerId"] for p in b["providers"]) == contract["sourcesAcquired"], "providers != sources the registration says this Brain acquires"


def p06_declared_dependencies_exact(E: Env):
    s, b = E.spec, E.brain_json
    assert b["consumes"] == list(s.consumes), f"declared consumes {b['consumes']} != expected {list(s.consumes)}"
    assert sorted(p["providerId"] for p in b["providers"]) == sorted(s.providers), f"declared providers {b['providers']}"
    catalog = {p["providerId"]: p for p in E.load("providers", "PROVIDERS.json")["providers"]}
    for pid in s.providers:
        assert pid in catalog and s.brain_id in (catalog[pid].get("authorizedConsumers") or []), f"provider {pid} not registered for this Brain"
    owned_undeclared = [pid for pid, p in catalog.items() if p.get("acquisitionOwner") == s.brain_id and pid not in s.providers]
    assert not owned_undeclared, f"providers this Brain owns but does not declare: {owned_undeclared}"
    assert not [c for c in b["consumes"] if c["kind"] == "signal" and c not in s.consumes], "undeclared signal edge"
    from sector_brain_platform import dependency_declarations as DD
    brains = DD.load_registered_brains(E.root)
    assert s.brain_id in brains, "Brain is not a registered Brain (brains/*/brain.json)"
    signals = {x["signalId"]: x for x in E.load("platform", "registries", "signals", "signals.json")["signals"]}
    rows = DD.resolve(DD.declared_dependencies(brains[s.brain_id]), brains=brains, signals=signals, providers=DD.load_providers(E.root))
    unresolved = [r for r in rows if r.get("resolved") is not True]
    assert not unresolved, f"declared dependencies do not resolve: {unresolved}"
    g = DD.dependency_graph(brains, manifest=E.load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json"), signals=signals, providers=DD.load_providers(E.root))
    assert g["brains"][s.brain_id]["source"] == "brain.json" and g["brains"][s.brain_id]["declarationsKnown"] is True, "the dependency graph does not read this Brain from brain.json"
    assert not [w for w in g["warnings"] if s.brain_id in w], f"dependency graph warnings for this Brain: {[w for w in g['warnings'] if s.brain_id in w]}"
    manifest = E.load("jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")
    assert DD.drift(brains, manifest) == [], "the platform manifest claims an edge a registered Brain does not declare"
    declared_signals = {c.get("signalId") for c in s.consumes if c.get("kind") == "signal"}
    blob = json.dumps(b)
    src = "\n".join(open(p, encoding="utf-8").read() for p in walk_files(E.runtime, (".py",)))
    leaked = [sid for sid in signals if sid not in declared_signals and (sid in blob or f'"{sid}"' in src or f"'{sid}'" in src)]
    assert not leaked, f"Signal Registry signals referenced but not declared (fabricated edge): {leaked}"


def p07_artifact_publisher_valid_and_deterministic(E: Env):
    s = E.spec
    a1 = E.artifact(1)
    assert a1["envelope"] == "publish-artifact-v2" and a1["lineage"]["artifactSchema"] == s.bundle_id
    from sector_brain_platform.publisher import PublisherMode, Result
    st, publish = E.rig()
    res = publish(a1)
    assert res.result is Result.SHADOW_READY and res.codes == [] and res.mode is PublisherMode.SHADOW, f"{res.result} {res.codes}"
    a2 = E.artifact(1)
    assert json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True), "artifact is not deterministic (clock/randomness leaked)"


def p08_fingerprint_stability_and_skip(E: Env):
    from sector_brain_platform.publisher import Result
    base = E.artifact(1)
    fp = base["lineage"]["outputFingerprint"]
    other = E.artifact(2, "2026-10-13T03:00:00Z")
    assert other["lineage"]["outputFingerprint"] == fp, "semantic fingerprint changed with a new executionId/generatedAt"
    assert other["lineage"]["inputFingerprint"] == base["lineage"]["inputFingerprint"], "inputFingerprint changed with execution identity"
    assert E.artifact(3, consumed=[])["lineage"]["outputFingerprint"] == fp, "lineage (consumed) entered the fingerprint"
    later = E.artifact(4, "2026-10-14T18:00:00Z", rerun=True)
    assert later["lineage"]["outputFingerprint"] == fp, "a later run on unchanged inputs changed the fingerprint"
    st, publish = E.rig()
    assert publish(base).result is Result.SHADOW_READY
    assert publish(later).result is Result.SKIP, "an unchanged re-publish must SKIP"
    if E.spec.changed_artifact_factory is not None:
        ch = E.spec.changed_artifact_factory(5, "2026-10-14T20:00:00Z")
        assert ch["lineage"]["outputFingerprint"] != fp, "a real domain change did not change the fingerprint"
        assert publish(ch).result is Result.SHADOW_READY
    elif "FINGERPRINT_CHANGE" not in E.spec.not_applicable:
        _fail("changed_artifact_factory missing (declare not_applicable['FINGERPRINT_CHANGE'] with a reason)")


def p09_lineage_truthful_never_optimistic(E: Env):
    s = E.spec
    art = E.artifact(1)
    lin = art["lineage"]
    assert lin["brainId"] == s.brain_id and lin["lifecycle"] == s.lifecycle
    assert (lin["reviewStatus"], lin["validationStatus"]) == (s.expected_review_status, s.expected_validation_status), "review/validation status must never be optimistic"
    for k in ("codeVersion", "executionId", "inputFingerprint", "outputFingerprint", "generatedAt"):
        assert lin.get(k), f"lineage.{k} missing"
    triple = (lin["knowledgeRelease"], lin["manifestRef"], lin["manifestSha256"])
    if s.release_lineage is None:
        assert all(x != "NONE" for x in triple), "this Brain declares a real release: knowledgeRelease/manifestRef/manifestSha256 must all be declared"
    else:
        assert triple == tuple(s.release_lineage), f"release lineage {triple} != declared {tuple(s.release_lineage)} (never invent a release)"
    if s.consumed_absent_when_unknown:
        assert E.artifact(1, consumed=[])["consumed"] == [], "[] must be carried only when a recorder recorded 'nothing'"
        assert "consumed" not in art, "consumed present although nothing was recorded: unknown must be an ABSENT key, never []"
    src = "".join(open(p, encoding="utf-8").read() for p in walk_files(E.runtime, (".py",)))
    assert "dependencyType" not in src or not s.consumed_absent_when_unknown, "the runtime constructs consumption entries by hand (never fabricate lineage)"


def p10_health_v1_from_engine_truth(E: Env):
    import datetime as dt
    from sector_brain_platform import brain_health as BH, dependency_declarations as DD
    s = E.spec
    brains = DD.load_registered_brains(E.root)
    assert s.brain_id in brains, "Brain is not discoverable as a registered Brain (brains/*/brain.json)"
    declared = DD.declared_dependencies(brains[s.brain_id])
    expected = len(E.brain_json["consumes"]) + len(E.brain_json["providers"])
    assert len(declared) == expected, f"healthV1 sees {len(declared)} declared dependencies, brain.json declares {expected}"
    now = dt.datetime(2026, 10, 12, 6, 30, tzinfo=dt.timezone.utc)
    ok = [{"executionId": uid(1), "brainId": s.brain_id, "status": "SUCCEEDED", "startedAt": "2026-10-12T06:00:00Z", "finishedAt": "2026-10-12T06:01:00Z"}]
    h = BH.brain_health(s.brain_id, declared=declared, declarations_known=True, executions=ok, observations={}, now=now)
    assert h["brainId"] == s.brain_id and h["dependencies"]["declared"] == len(declared)
    assert h["freshness"]["status"] == "UNKNOWN", "a recent successful run must NOT make evidence FRESH (lastSuccessfulRun is not evidence freshness)"
    assert h["dependencies"]["declaredVsActual"]["consumptionRecorded"] is False
    ex = dict(ok[0], consumed=[{"dependencyId": "brain:undeclared-probe", "dependencyType": "BRAIN", "consumedAt": "2026-10-12T06:00:30Z"}])
    h2 = BH.brain_health(s.brain_id, declared=declared, declarations_known=True, executions=[ex], observations={}, now=now)
    assert h2["dependencies"]["declaredVsActual"]["consumedNotDeclared"] == ["brain:undeclared-probe"], "undeclared consumption must surface as drift"
    for p in walk_files(E.runtime, (".py",)):
        for m in re.finditer(r"freshness[^\n]*lastSuccess|lastSuccess[^\n]*(freshUntil|staleAfter|expiresAt|freshnessStatus)", open(p, encoding="utf-8").read()):
            if "never" in m.group(0) or "NOT" in m.group(0):
                continue
            _fail(f"{E.rel(p)}: evidence freshness derived from lastSuccess: {m.group(0)[:90]}")


def p11_publisher_shadow_only_end_to_end(E: Env):
    from sector_brain_platform.publisher import PublisherMode
    from sector_brain_platform.publisher.api import AllowlistAuthorizer, Caller, OrchestratorApi
    s = E.spec
    assert {m.name for m in PublisherMode} == {"SHADOW", "DRY_RUN"}, "a live Publisher mode exists"

    class Authn:
        def authenticate(self, cred):
            return Caller("brain-identity") if cred == "tok" else None
    st, _ = E.rig()
    api = OrchestratorApi(Authn(), AllowlistAuthorizer({"brain-identity": {"ARTIFACT": {f"SUBMIT_ARTIFACT@{s.brain_id}"}}}), st.dispatcher)
    ref = st.writer(s.brain_id).write(E.artifact(1))
    body = {"apiVersion": "orchestrator-api-v1", "requestId": uid(700), "requestKind": "ARTIFACT", "brainId": s.brain_id, "action": "SUBMIT_ARTIFACT",
            "params": {"artifactId": ref.artifact_id, "artifactRef": ref.location, "artifactSha256": ref.sha256, "executionId": ref.execution_id, "expectedSchema": ref.expected_schema}}
    r = api.handle("tok", body)
    assert r.status == 200 and r.result["result"] == "SHADOW_READY" and r.result["live"] is False, r.result
    assert st.sink.live_mutations == 0
    plan = st.sink.submitted[-1][0]
    assert f"brains/{s.brain_id}/publication" in plan.updates, "the Publisher's own publication record is not in the single plan"
    stray = [k for k in plan.updates if not k.startswith(tuple(s.plan_root_prefixes))]
    assert not stray, f"plan writes outside the Brain's declared roots: {stray[:5]}"


def p12_publisher_rejections(E: Env):
    from sector_brain_platform.publisher import Result
    from .spec import Rejection
    s = E.spec
    others = E.other_registered_brains()
    assert others, "no other registered Brain to test cross-Brain rejection against"
    probe = {"op": "SET", "path": f"/brains/{s.brain_id}/{s.registry_probe_child}", "value": "KIT_PROBE"}
    cases = [Rejection(f"/brains/{others[0]}/status", "CROSS_DOMAIN_PATH"), Rejection(f"/scores/{s.brain_id}", "CROSS_DOMAIN_PATH"),
             Rejection(f"/brains/{s.brain_id}/publication", "RESERVED_PATH"), Rejection(f"/brains/{s.brain_id}/certification", "RESERVED_PATH"),
             Rejection(f"/brains/{s.brain_id}", "BRAIN_NODE_REPLACEMENT"), Rejection("/control/orchestratorV1", "CROSS_DOMAIN_PATH")]
    if s.job_id:
        cases.append(Rejection(f"/health/jobs/{s.job_id}", "CROSS_DOMAIN_PATH"))
    cases += list(s.extra_rejections)
    bad = []
    for c in cases:
        st, publish = E.rig()
        res = publish(E.sealed([probe, {"op": "SET", "path": c.path, "value": {"x": 1}}]))
        if not (res.result is Result.REJECTED and c.code in res.codes) or st.sink.submitted:
            bad.append((c.path, c.code, res.result.name, res.codes))
    assert not bad, f"Publisher did not reject as declared: {bad}"
    art = E.artifact(1)
    st, publish = E.rig()                                                              # a Brain's artifact under another Brain's identity
    ref = st.writer(others[0]).write(copy.deepcopy(dict(art, lineage=dict(art["lineage"], brainId=others[0]))))
    r = st.publisher.evaluate_reference(ref)
    assert r.result is Result.REJECTED and ("SCHEMA_BRAIN_MISMATCH" in r.codes or "UNKNOWN_SCHEMA" in r.codes), r.codes
    wrong = copy.deepcopy(art)
    foreign_schema = next(sid for sid in E.registry.schemas_for(others[0]))
    wrong["lineage"]["artifactSchema"] = foreign_schema
    st, publish = E.rig()
    assert publish(wrong).result is Result.REJECTED, "an artifact claiming another Brain's schema was not rejected"
    secs = [sp for sp in E.bundle_specs() if sp.schema_id != s.registry_schema_id]
    if secs:                                                                           # a path of ANOTHER section of this Brain placed in the registry section
        fam = secs[0].families[0].pattern.replace("{k}", "Probe_AL").replace("{id}", "probe").replace("{child}", "probe").replace("{event}", "probe")
        st, publish = E.rig()
        res = publish(E.sealed([probe, {"op": "SET", "path": fam, "value": {"x": 1}}]))
        assert res.result is Result.REJECTED and {"PATH_NOT_AUTHORIZED", "CROSS_DOMAIN_PATH"} & set(res.codes), f"section-crossing path {fam}: {res.result.name} {res.codes}"
    mine = next(f for sp in E.bundle_specs() for f in sp.families).pattern.replace("{k}", "Probe_AL").replace("{id}", "probe").replace("{child}", "status").replace("{event}", "probe")
    foreign_schema = next(iter(E.registry.schemas_for(others[0])))
    st, publish = E.rig()                                                              # another Brain, with its own valid bundle, writing THIS Brain's path
    foreign = E.sealed([{"op": "SET", "path": mine, "value": {"x": 1}}], schema=foreign_schema, brain_id=others[0], bundle_id=E.bundle_id_of(others[0]), freshness={"freshnessStatus": "UNKNOWN"})
    res = publish(foreign, brain=others[0])
    assert res.result is Result.REJECTED and {"PATH_NOT_AUTHORIZED", "CROSS_DOMAIN_PATH"} & set(res.codes), f"{others[0]} writing {mine}: {res.result.name} {res.codes} (must be a path-ownership rejection)"
    prod = copy.deepcopy(art)
    prod["lineage"]["lifecycle"] = "PRODUCTION"
    st, publish = E.rig()
    r = publish(prod)
    assert r.result is Result.REJECTED and "LIFECYCLE_NOT_AUTHORIZED" in r.codes, f"production lifecycle without approval: {r.result} {r.codes}"
    reqs = E.bundle_specs()
    if any(sp.require_release for sp in reqs):
        none_rel = copy.deepcopy(art)
        none_rel["lineage"].update(knowledgeRelease="NONE", manifestRef="NONE", manifestSha256="NONE")
        st, publish = E.rig()
        assert publish(none_rel).result is Result.FAILED_VALIDATION, "a release-required schema accepted release NONE"
    if any(sp.require_freshness for sp in reqs):
        nf = copy.deepcopy(art)
        for sec in nf["sections"]:
            sec.pop("freshness", None)
        st, publish = E.rig()
        assert publish(nf).result is not Result.SHADOW_READY, "a freshness-required schema accepted a missing freshness block"


def p13_typed_deletes_and_null_is_not_delete(E: Env):
    from sector_brain_platform.publisher import Result
    s = E.spec
    art = E.artifact(1)
    specs = {sp.schema_id: sp for sp in E.bundle_specs()}
    for sec in art["sections"]:
        sp = specs[sec["artifactSchema"]]
        for m in sec["mutations"]:
            if m["op"] == "DELETE":
                assert m.get("reason") in sp.delete_reasons, f"DELETE {m['path']} carries reason {m.get('reason')!r} outside the closed vocabulary {list(sp.delete_reasons)}"
    st, publish = E.rig()
    nul = E.sealed([{"op": "SET", "path": f"/brains/{s.brain_id}/{s.registry_probe_child}", "value": None}])
    assert publish(nul).result is Result.FAILED_VALIDATION, "a null SET was accepted (null must never mean delete)"
    no_delete = [sp for sp in specs.values() if not sp.delete_families]
    for sp in no_delete[:1]:
        fam = sp.families[0]
        path = fam.pattern.replace("{k}", "Probe_AL").replace("{id}", "probe").replace("{child}", "probe")
        st, publish = E.rig()
        res = publish(E.sealed([{"op": "DELETE", "path": path, "reason": "ANY"}], schema=sp.schema_id, freshness={"freshnessStatus": "UNKNOWN"}))
        assert res.result is Result.REJECTED, f"a schema with no delete family accepted a DELETE ({sp.schema_id})"


def p14_direct_write_sites_pinned(E: Env):
    s = E.spec
    sites = set()
    for p in walk_files(E.runtime, (".py",)):
        src = open(p, encoding="utf-8").read()
        bad = [m for m in s.forbidden_imports if re.search(rf"^\s*(import|from)\s+{re.escape(m)}", src, re.M)]
        assert not bad, f"{E.rel(p)} imports a direct database/cloud client: {bad}"
        assert not re.search(r"method\s*=\s*['\"](PATCH|PUT|POST|DELETE)['\"]", src), f"{E.rel(p)}: direct REST write"
        sites |= write_sites(p, s.write_call_suffixes)
    assert sites == set(s.allowed_write_sites), f"database write sites differ from the audit table: {sorted(sites ^ set(s.allowed_write_sites))}"


def p15_artifact_path_cannot_write(E: Env):
    import ast
    s = E.spec
    path = os.path.join(s.brain_dir, s.builder_module)
    imported = imported_roots(path)
    bad = imported & set(s.builder_forbidden_imports)
    assert not bad, f"the artifact builder imports I/O or non-determinism: {sorted(bad)}"
    src = ast.unparse(ast.parse(open(path, encoding="utf-8").read()))
    for token in s.builder_forbidden_tokens:
        assert token not in src, f"the artifact builder uses {token!r}"


def p16_runtime_isolation_paths(E: Env):
    s = E.spec
    rx = re.compile(s.local_path_regex)
    bad = []
    for p in walk_files(E.runtime, (".py", ".json", ".sh", ".txt")):
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if rx.search(line) and not any(m in line for m in s.local_path_exempt_markers):
                bad.append(f"{E.rel(p)}:{i}")
    assert not bad, f"local/Desktop/research paths in the runtime: {bad}"


def p17_research_separate_from_runtime(E: Env):
    s, b = E.spec, E.brain_json
    odd = [E.rel(p) for p in walk_files(E.runtime) if os.path.splitext(p)[1] not in set(s.allowed_runtime_ext) and os.path.basename(p) not in ("requirements.txt", "Dockerfile")]
    assert not odd, f"non-code files in the production runtime: {odd}"
    rd = os.path.join(s.brain_dir, "research")
    if s.research_files is not None:
        assert sorted(n for n in os.listdir(rd) if n != "__pycache__") == sorted(s.research_files), f"research dir listing {sorted(os.listdir(rd))}"
    gaps = os.path.join(rd, "GAPS.json")
    if os.path.exists(gaps):
        assert E.jsonschema_lite.validate(json.load(open(gaps, encoding="utf-8")), E.load("contracts", "schemas", "research-gaps.schema.json")) == []
        assert json.load(open(gaps, encoding="utf-8"))["brainId"] == s.brain_id
    budget = b["dataBudget"]["maxTrackedFileBytes"]
    big = [E.rel(p) for p in walk_files(s.brain_dir) if os.path.getsize(p) >= budget]
    assert not big, f"files over the Brain's data budget ({budget} B): {big}"


def p18_architecture_gates_no_new_violations(E: Env):
    s, report = E.spec, E.report
    own = [f for f in report.check(E.root, legacy=False) if f["subject"].startswith(f"brains/{s.directory}/")]
    allowed = {(os.path.basename(f), inv) for f, inv in s.arch_findings}
    bad = [f for f in own if (os.path.basename(f["subject"]), f["invariant"]) not in allowed]
    assert not bad, f"registered-Brain architecture findings that are not carried baseline entries: {bad}"
    legacy = report.check(E.root, legacy=True)
    baseline = E.load("tools", "architecture", "baseline", "legacy_violations.json")
    known, new, resolved = report.compare_to_baseline(legacy, baseline)
    assert new == [] and resolved == [], f"architecture baseline drift: NEW={new} RESOLVED={resolved}"
    carried = [e for e in baseline["entries"] if e["path"].startswith(f"brains/{s.directory}/")]
    assert sorted(os.path.basename(e["path"]) for e in carried) == sorted(s.baseline_entry_basenames), f"carried baseline entries {[e['path'] for e in carried]}"
    if s.baseline_carried_from_required:
        assert all(e.get("carriedFrom") for e in carried), "a carried baseline entry lacks its carriedFrom origin"


def p19_score_and_lifecycle_unchanged(E: Env):
    s = E.spec
    if s.has_score:
        assert (E.brain_json.get("score") or {}).get("path") == f"/scores/{s.brain_id}", "score block missing or wrong"
    else:
        assert "score" not in E.brain_json, "a Brain without a score declares a score block"
    art = E.artifact(1)
    paths = [m["path"] for sec in art["sections"] for m in sec["mutations"]]
    assert not [p for p in paths if p.lstrip("/").startswith("scores")], "the Brain's artifact writes a score"
    if s.score_baseline_substring is None:
        return
    r = subprocess.run([sys.executable, os.path.join(E.root, "verification", "integration", "score_baseline.py"), "--check"], capture_output=True, text=True, cwd=E.root)
    assert r.returncode == 0 and s.score_baseline_substring in r.stdout, f"score baseline drift or missing entry: {r.stdout}{r.stderr}"


PROOFS = (
    ("P01", "location_and_shape", p01_location_and_shape),
    ("P02", "one_production_implementation", p02_one_production_implementation),
    ("P03", "identity_lifecycle_publisher_state", p03_identity_lifecycle_publisher_state),
    ("P04", "operating_contract", p04_operating_contract),
    ("P05", "published_contract_derived_from_registry", p05_published_contract_derived_from_registry),
    ("P06", "declared_dependencies_exact", p06_declared_dependencies_exact),
    ("P07", "artifact_valid_and_deterministic", p07_artifact_publisher_valid_and_deterministic),
    ("P08", "fingerprint_stability_and_skip", p08_fingerprint_stability_and_skip),
    ("P09", "lineage_truthful", p09_lineage_truthful_never_optimistic),
    ("P10", "health_v1_from_engine_truth", p10_health_v1_from_engine_truth),
    ("P11", "publisher_shadow_only_end_to_end", p11_publisher_shadow_only_end_to_end),
    ("P12", "publisher_rejections", p12_publisher_rejections),
    ("P13", "typed_deletes", p13_typed_deletes_and_null_is_not_delete),
    ("P14", "direct_write_sites_pinned", p14_direct_write_sites_pinned),
    ("P15", "artifact_path_cannot_write", p15_artifact_path_cannot_write),
    ("P16", "runtime_isolation_paths", p16_runtime_isolation_paths),
    ("P17", "research_separate", p17_research_separate_from_runtime),
    ("P18", "architecture_gates", p18_architecture_gates_no_new_violations),
    ("P19", "score_and_lifecycle", p19_score_and_lifecycle_unchanged),
)
