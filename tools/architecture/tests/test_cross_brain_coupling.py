"""No cross-Brain source coupling (Cortex BR-03/BR-08, PL boundaries): a Brain reads another Brain only through published state or a published
contract, never through its code. Python: no Brain's runtime or research tooling imports a module that exists only in ANOTHER Brain's package.
Swift: the Brain targets do not depend on each other (Package.swift). Static."""
import ast
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BRAINS = sorted(d for d in os.listdir(os.path.join(ROOT, "brains")) if os.path.isfile(os.path.join(ROOT, "brains", d, "brain.json")))


def _py(root):
    for dp, dns, fs in os.walk(root):
        dns[:] = [d for d in dns if d not in ("__pycache__", ".build")]
        for f in fs:
            if f.endswith(".py"):
                yield os.path.join(dp, f)


def _modules(d):
    """Top-level importable names a Brain package provides (runtime and research tooling)."""
    out = set()
    for sub in ("runtime", os.path.join("research", "tools")):
        base = os.path.join(ROOT, "brains", d, sub)
        if not os.path.isdir(base):
            continue
        for n in os.listdir(base):
            p = os.path.join(base, n)
            if n.endswith(".py"):
                out.add(n[:-3])
            elif os.path.isdir(p) and os.path.exists(os.path.join(p, "__init__.py")):
                out.add(n)
    return out


def test_no_brain_imports_another_brains_code():
    own = {d: _modules(d) for d in BRAINS}
    bad = []
    for d in BRAINS:
        foreign = set().union(*(own[o] for o in BRAINS if o != d)) - own[d]
        for sub in ("runtime", "research", "tests"):
            for p in _py(os.path.join(ROOT, "brains", d, sub)):
                for n in ast.walk(ast.parse(open(p, encoding="utf-8").read())):
                    if isinstance(n, ast.Import):
                        names = [a.name.split(".")[0] for a in n.names]
                    elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                        names = [n.module.split(".")[0]]
                    else:
                        continue
                    bad += [f"{os.path.relpath(p, ROOT)} imports {x}" for x in names if x in foreign]
    assert not bad, "cross-Brain code coupling:\n" + "\n".join(bad)


# Documented duplicate: Fish and Sector Intelligence both ship `orchestration.py` (their own plan() helpers). Safe ONLY because the orchestrator
# starts every in-process Brain as its own subprocess with cwd = that Brain's runtime directory (asserted below), never in a shared interpreter.
ALLOWED_DUPLICATES = {"run", "main", "brain_platform", "publish_artifact", "orchestration"}


def test_brain_python_module_names_are_unambiguous():
    """Two Brains shipping the same top-level module name would let one silently import the other's code on a shared path."""
    seen, dup = {}, []
    for d in BRAINS:
        for m in _modules(d):
            if m in seen and m not in ALLOWED_DUPLICATES:
                dup.append((m, seen[m], d))
            seen.setdefault(m, d)
    assert not dup, dup


def test_in_process_brains_run_isolated_so_shared_module_names_cannot_collide():
    src = open(os.path.join(ROOT, "jobs", "brain-orchestrator", "orchestrate.py"), encoding="utf-8").read()
    assert 'subprocess.run([PYTHON, "run.py", "--plan"], cwd=ex["dir"]' in src
    assert 'subprocess.run([PYTHON, "run.py", "--write"], cwd=ex["dir"]' in src
    assert not re.search(r"^\s*(import|from)\s+orchestration\b", src, re.M)          # the orchestrator imports only the PLATFORM's orchestration


def test_swift_brain_targets_do_not_depend_on_each_other():
    pkg = open(os.path.join(ROOT, "Package.swift"), encoding="utf-8").read()
    for target, other in (("LakeBrain", "WaterTemperatureBrain"), ("WaterTemperatureBrain", "LakeBrain"),
                          ("LakeBrainJob", "WaterTemperatureBrain"), ("WaterTempBrainJob", "LakeBrain")):
        m = re.search(rf'\.(?:executableTarget|target)\(\s*name:\s*"{target}"\s*,\s*dependencies:\s*\[([^\]]*)\]', pkg)
        assert m, target
        assert f'"{other}"' not in m.group(1), f"{target} depends on {other}"
