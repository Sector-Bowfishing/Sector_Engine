#!/usr/bin/env python3
"""Deploy guard for SI_ARTIFACT_JOB (Sector_Ops #51, owner approval 2026-11-16 18:09Z). Standard library only; never calls gcloud.

While the deployed commit's publication-cutover.json says sector-intelligence is CENTRAL, Sector Intelligence must run only as the lease-only
artifact job, so the brain-orchestrator deploy must carry SI_ARTIFACT_JOB=1. A deploy without it would quietly put Sector Intelligence back
in-process, writing directly and bypassing the Publisher. jobs/brain-orchestrator/deploy-job.sh calls this before it deploys:

  python3 tools/deploy/si_artifact_guard.py --cutover publication-cutover.json --switch on|off     # explicit-env deploy (CARRY_ENV=0)
  python3 tools/deploy/si_artifact_guard.py --cutover publication-cutover.json --env-yaml env.yaml # carried-env deploy (CARRY_ENV=1)

Exit 0 = allowed, 1 = refused (the reason on stderr), 2 = unreadable input (also refused: fail closed).
"""
from __future__ import annotations

import argparse
import json
import sys

BRAIN = "sector-intelligence"


def si_is_central(cutover: dict) -> bool:
    """True when the cutover document lists sector-intelligence as CENTRAL (absent = direct writer = not central)."""
    if not isinstance(cutover, dict) or not isinstance(cutover.get("brains"), dict):
        raise ValueError("publication-cutover.json has no 'brains' map")
    entry = cutover["brains"].get(BRAIN)
    return isinstance(entry, dict) and entry.get("state") == "CENTRAL"


def carried_switch(env_yaml: str) -> bool:
    """True when the job_env.py env-vars file (one `"KEY": "value"` JSON pair per line) sets SI_ARTIFACT_JOB to 1."""
    for line in env_yaml.splitlines():
        if not line.strip():
            continue
        k, _, v = line.partition(": ")
        if json.loads(k) == "SI_ARTIFACT_JOB":
            return json.loads(v) == "1"
    return False


def check(cutover: dict, switch: str | None = None, env_yaml: str | None = None) -> str | None:
    """None if the deploy may go ahead, otherwise the refusal reason."""
    if (switch is None) == (env_yaml is None):
        raise ValueError("give exactly one of --switch or --env-yaml")
    if switch is not None and switch not in ("on", "off"):
        raise ValueError("--switch must be on or off")
    if not si_is_central(cutover):
        return None
    on = switch == "on" if switch is not None else carried_switch(env_yaml)
    if on:
        return None
    how = "SI_ARTIFACT_JOB is off" if switch is not None else "the carried job env has no SI_ARTIFACT_JOB=1"
    return (f"REFUSED: publication-cutover.json says {BRAIN} is CENTRAL but {how}. This deploy would put Sector Intelligence back in-process, "
            f"bypassing the Publisher. Deploy with SI_ARTIFACT_JOB=on (or, with CARRY_ENV=1, from a job that already has it).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cutover", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--switch", choices=("on", "off"))
    g.add_argument("--env-yaml")
    a = ap.parse_args(argv)
    try:
        with open(a.cutover) as fh:
            cutover = json.load(fh)
        env_yaml = None
        if a.env_yaml is not None:
            with open(a.env_yaml) as fh:
                env_yaml = fh.read()
        reason = check(cutover, a.switch, env_yaml)
    except (OSError, ValueError) as e:
        print(f"REFUSED: SI_ARTIFACT_JOB guard could not read its inputs: {e}", file=sys.stderr)
        return 2
    if reason:
        print(reason, file=sys.stderr)
        return 1
    print(f"SI_ARTIFACT_JOB guard: OK ({BRAIN} {'CENTRAL' if si_is_central(cutover) else 'not CENTRAL'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
