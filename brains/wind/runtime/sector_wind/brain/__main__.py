"""WindBrain CLI.

  python -m sector_wind.brain publish --store local:/path --dry-run OUT.json      # build everything, write nothing remote
  python -m sector_wind.brain publish --store gs://sector-wind-candidate/wind/v1 --rtdb https://sector-brain.firebaseio.com

A live --rtdb write needs explicit operator intent (the flag) and only ever targets the dedicated Brain RTDB."""
import argparse, json, sys

from ..ingest import load_config
from ..store import open_store
from .publish import safe_publish
from .writer import DryRunWriter, RtdbWriter


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["publish"])
    ap.add_argument("--store", required=True); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", metavar="OUT.json"); g.add_argument("--rtdb", metavar="URL")
    a = ap.parse_args(argv)
    store, cfg = open_store(a.store), load_config()
    writer = DryRunWriter() if a.dry_run else RtdbWriter(a.rtdb)
    rep = safe_publish(store, cfg, writer, mode="manual")
    if a.dry_run:
        writer.dump(a.dry_run); rep["dryRunFile"] = a.dry_run; rep["patches"] = len(writer.patches)
    print(json.dumps(rep, indent=1, default=str)[:6000])
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
