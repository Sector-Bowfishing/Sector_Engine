"""scripts/generate-lake-bindings.py reads the real accepted batch by default; LAKE_ACCEPTED_BATCH is the only staged-rollout override."""
import importlib.util
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GEN = os.path.join(ROOT, "scripts", "generate-lake-bindings.py")


def load(env):
    old = os.environ.get("LAKE_ACCEPTED_BATCH")
    try:
        if env is None:
            os.environ.pop("LAKE_ACCEPTED_BATCH", None)
        else:
            os.environ["LAKE_ACCEPTED_BATCH"] = env
        spec = importlib.util.spec_from_file_location("gen_lake_bindings_under_test", GEN)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if old is None:
            os.environ.pop("LAKE_ACCEPTED_BATCH", None)
        else:
            os.environ["LAKE_ACCEPTED_BATCH"] = old


def test_default_is_the_real_accepted_batch_path():
    assert load(None).ACCEPTED.endswith(os.path.join("jobs", "lake-brain", "data", "accepted_batch.json"))


def test_env_override_for_staged_rollout():
    assert load("/tmp/stage_a.json").ACCEPTED == "/tmp/stage_a.json"


def test_empty_env_falls_back_to_the_real_path():
    assert load("").ACCEPTED.endswith("accepted_batch.json")
