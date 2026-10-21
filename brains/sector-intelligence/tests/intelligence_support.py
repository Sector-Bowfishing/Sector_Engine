"""Shared support for the Sector Intelligence certification tests: one REAL publisher run (unchanged `build_updates` + pilot `evaluation`) on the suite's
synthetic upstream registrations and pilot-lake states, and the pinned artifact build context. Synthetic and offline."""
import copy
import datetime as dt
import os
import uuid

import brain_platform as bp
import evaluation as ev
import orchestration as orch
import publish_artifact as pa
import sector_intelligence_brain as sib
import test_evaluation as TE
import test_sector_intelligence_brain as T

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NOW = T.NOW


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(now=NOW, published=None, mutate_upstream=None):
    """The flat update dictionary one `run.py --write` would send (pilot lake Guntersville evaluated, one inventory-only lake)."""
    cat, ups, _ = TE.deps_all_present()
    if mutate_upstream:
        ups = copy.deepcopy(ups)
        mutate_upstream(ups)
    deps = {b: sib.dependency_status(b, cat["dependencies"][b], ups[b]["registry"], ups[b]["health"], ups[b]["validationStatus"], cat, now)
            for b in sib.DEPENDENCY_ORDER}
    serving = sib.engine_serving(T.SERVICE, T.LINEAGE, now)
    e = ev.evaluate("Guntersville|AL", snapshot=TE.snapshot(), fleet_row=None, presence=TE.PRESENCE, species=TE.SPECIES, deps=deps, cat=cat,
                    serving=serving, now=now)
    evs = {"Guntersville|AL": e}
    return sib.build_updates(cat=cat, cat_sha="sha", lakes=["Guntersville|AL", "Beta Reservoir|TN"], fleet={}, upstream=ups, serving=serving, now=now,
                             deployment="test@1", descriptor=orch.DESCRIPTOR, duration_ms=5, published=published,
                             event_id=bp.event_id(now, sib.BRAIN_ID, 0), evaluations=evs, inputs_fp=ev.inputs_fingerprint(evs))


RELEASE = None


def release():
    """The verified packaged knowledge release, exactly as run.load_knowledge reads it."""
    global RELEASE
    if RELEASE is None:
        from sector_brain_platform.knowledge_release import load_release
        RELEASE = load_release(os.path.join(REPO, "brains", "sector-intelligence", "runtime"), sib.BRAIN_ID)
    return RELEASE


def build(updates, *, n=1, generated_at="2026-10-12T23:00:00Z", consumed=None):
    return pa.build_artifact(updates, pa.BuildContext(generated_at, uid(n), "test@1"), consumed=consumed, release=release())
