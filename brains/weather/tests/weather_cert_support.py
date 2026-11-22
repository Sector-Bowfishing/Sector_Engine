"""Shared support for the Weather certification tests: one REAL run of the unchanged `publish.run` over the RECORDED NWS fixtures into a flat
write set, and the pinned artifact build context. Offline; nothing is published."""
import uuid

from sector_weather import contract as C, publish_artifact as pa
from sector_weather.client import PointCache
from sector_weather.knowledge import lineage_triple
from sector_weather.publish import run
from weather_support import LAKES, RECORDED_NOW, REPO, FixtureSource  # noqa: F401

LINEAGE = lineage_triple(C.RELEASE)


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(lakes=("Guntersville|AL", "Champlain|VT"), now=RECORDED_NOW) -> dict:
    out = run([LAKES[l] for l in lakes], FixtureSource(), PointCache(None), {}, now)
    assert not out["errors"], out["errors"]
    return out["updates"]


def build(updates, *, n=1, generated_at="2026-11-06T20:51:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, release_lineage=LINEAGE, consumed=consumed)
