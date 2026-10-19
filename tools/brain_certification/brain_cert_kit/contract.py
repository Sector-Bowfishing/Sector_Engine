"""ONE shared published-contract descriptor. A Brain's `contracts/describe_contract.py` is a thin wrapper that supplies a declarative `ContractSpec`; this module
derives the contract JSON from the Publisher registry (the authority), so a declaration can never drift from what the Publisher enforces.

Nothing here knows any Brain: every Brain-specific value is either a JSON literal in `extras`, a named attribute of the Publisher registry module
(`("registry", ATTR, TRANSFORM)`), or a selection of section fields. Output is stable (sorted keys) and byte-compatible with the pre-kit descriptors."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

SECTION_FIELDS = ("families", "deleteFamilies", "deleteReasons", "volatileContract", "requiresRelease", "requiresFreshness", "allowedLifecycles", "projections")
TRANSFORMS = ("children", "list", "sortedkeys", "callsorted", "projections")


@dataclass(frozen=True)
class ContractSpec:
    contract_dir: str                    # absolute: the Brain's contracts/ directory
    out_file: str                        # e.g. "<id>-publication-v1.json"
    bundle_id: str
    builder: str                         # repo-relative path of the artifact builder (documentation field of the contract)
    derived_from: str
    status: str
    section_fields: tuple = ("families", "deleteFamilies", "deleteReasons", "volatileContract")
    extras: dict = field(default_factory=dict)       # out key -> JSON literal | ("registry", ATTR, TRANSFORM) | ("volatile",)
    version: str = "1.0.0"

    def __post_init__(self):
        bad = [f for f in self.section_fields if f not in SECTION_FIELDS]
        if bad:
            raise ValueError(f"unknown section fields {bad}")
        for k, v in self.extras.items():
            if isinstance(v, tuple) and v and v[0] == "registry" and v[2] not in TRANSFORMS:
                raise ValueError(f"extras[{k!r}]: unknown transform {v[2]!r}")


def _section(spec, s):
    fam = lambda f: {"pattern": f.pattern, "status": f.status}      # noqa: E731
    out = {"schemaId": s.schema_id}
    pick = {
        "families": lambda: [fam(f) for f in s.families],
        "deleteFamilies": lambda: [f.pattern for f in s.delete_families],
        "deleteReasons": lambda: list(s.delete_reasons),
        "volatileContract": lambda: s.volatile.id if s.volatile else None,
        "requiresRelease": lambda: s.require_release,
        "requiresFreshness": lambda: s.require_freshness,
        "allowedLifecycles": lambda: list(s.allowed_lifecycles),
        "projections": lambda: [{"id": p.id, "kind": p.kind, "source": p.source, "target": p.target, "valueFrom": p.value_from, "owner": p.owner} for p in s.projections],
    }
    for f in spec.section_fields:
        out[f] = pick[f]()
    return out


def _transform(R, attr, how):
    v = getattr(R, attr)
    if how == "children":
        return {k: list(x) for k, x in v.items()}
    if how == "list":
        return list(v)
    if how == "sortedkeys":
        return sorted(v)
    if how == "callsorted":
        return sorted(v())
    if how == "projections":
        return [{"id": p.id, "source": p.source, "target": p.target} for p in v]
    raise ValueError(how)


def describe_contract(spec: ContractSpec) -> dict:
    from sector_brain_platform.publisher import registry as R
    reg = R.default_registry()
    bundle = reg.bundle(spec.bundle_id)
    if bundle is None:
        raise ValueError(f"bundle {spec.bundle_id!r} is not registered in the Publisher registry")
    specs = [reg.spec(sid) for sid in bundle.sections]
    d = {"contractId": bundle.bundle_id, "brainId": bundle.brain_id, "version": spec.version, "envelope": "publish-artifact-v2",
         "fingerprint": "sector-semantic-fingerprint-v2", "derivedFrom": spec.derived_from, "builder": spec.builder,
         "sections": sorted((_section(spec, s) for s in specs), key=lambda x: x["schemaId"]), "status": spec.status}
    for key, val in spec.extras.items():
        if isinstance(val, tuple) and val and val[0] == "registry":
            d[key] = _transform(R, val[1], val[2])
        elif isinstance(val, tuple) and val == ("volatile",):
            d[key] = specs[0].volatile.describe()
        else:
            d[key] = val
    return d


def run_describe_cli(spec: ContractSpec, argv) -> int:
    d = describe_contract(spec)
    text = json.dumps(d, indent=2, sort_keys=True) + "\n"
    out = os.path.join(spec.contract_dir, spec.out_file)
    if "--write" in argv:
        open(out, "w").write(text)
        return 0
    if "--check" in argv:
        ok = os.path.exists(out) and open(out).read() == text
        print(f"{spec.out_file} matches the Publisher registry" if ok else f"{spec.out_file} is stale: run --write")
        return 0 if ok else 1
    sys.stdout.write(text)
    return 0
