#!/usr/bin/env python3
"""Cloud Run job state for the orchestrator deploy (DEPLOY_WORKFLOWS_V1.md §2). Standard library only; never calls gcloud itself.

  python3 tools/deploy/job_env.py snapshot --describe job.json --out snap.json
        image, env, `commit` label, service account and args of `gcloud run jobs describe <job> --format=json`.
  python3 tools/deploy/job_env.py carry --snapshot snap.json --projection 0|1 [--deployment-version V] --out env.yaml
        the env-vars file for `--env-vars-file`: EVERY current value carried forward, only CONDITIONS_SOURCES_PROJECTION
        (and DEPLOYMENT_VERSION when a new image is deployed, because it names the deployed commit) changed.
  python3 tools/deploy/job_env.py restore --snapshot snap.json --out env.yaml
        the env-vars file that puts back exactly the snapshot's env (rollback).
  python3 tools/deploy/job_env.py compare --snapshot after.json --env env.yaml [--image REF]
        exit 1 unless the job's env equals the file (and its image equals REF).

Refuses (exit 1) a job whose env holds a secret reference (`valueFrom`): an env-vars file cannot carry it, and dropping it silently is
exactly the kind of reset CARRY_ENV exists to prevent.
"""
from __future__ import annotations

import argparse
import json
import sys

PROJECTION = "CONDITIONS_SOURCES_PROJECTION"
DEPLOYMENT_VERSION = "DEPLOYMENT_VERSION"


class Refused(Exception):
    pass


def _container(describe: dict) -> dict:
    try:
        cs = describe["spec"]["template"]["spec"]["template"]["spec"]["containers"]
    except (KeyError, TypeError):
        raise Refused("describe output has no spec.template.spec.template.spec.containers") from None
    if not isinstance(cs, list) or len(cs) != 1:
        raise Refused(f"expected exactly one container, found {len(cs) if isinstance(cs, list) else 'none'}")
    return cs[0]


def snapshot(describe: dict) -> dict:
    c = _container(describe)
    env, secret = {}, []
    for e in c.get("env") or []:
        name = e.get("name")
        if not name:
            raise Refused("env entry without a name")
        if "valueFrom" in e:
            secret.append(name)
            continue
        env[name] = str(e.get("value", ""))
    if secret:
        raise Refused(f"env holds secret references ({', '.join(sorted(secret))}): an env-vars file cannot carry them; deploy by hand")
    image = c.get("image") or ""
    if not image:
        raise Refused("the job has no image")
    tspec = describe["spec"]["template"]["spec"]["template"]["spec"]
    return {
        "image": image,
        "env": env,
        "commit": ((describe.get("metadata") or {}).get("labels") or {}).get("commit", ""),
        "serviceAccount": tspec.get("serviceAccountName", ""),
        "args": list(c.get("args") or []),
    }


def short_image(ref: str) -> str:
    """The image without its registry path (run logs of this public repository are public): the digest, else name:tag."""
    return ref.rsplit("@", 1)[1] if "@" in ref else ref.rsplit("/", 1)[-1]


def carried(snap: dict, projection: str, deployment_version: str | None = None) -> dict:
    if projection not in ("0", "1"):
        raise Refused("projection must be 0 or 1")
    env = dict(snap["env"])
    env[PROJECTION] = projection
    if deployment_version:
        env[DEPLOYMENT_VERSION] = deployment_version
    return env


def env_yaml(env: dict) -> str:
    """A YAML map of strings. Each key and value is a JSON string, which is a valid YAML double-quoted scalar."""
    for k in env:
        if not k or any(ch in k for ch in "=\n\r"):
            raise Refused(f"bad env name {k!r}")
    return "".join(f"{json.dumps(k)}: {json.dumps(str(v))}\n" for k, v in sorted(env.items()))


def read_env_yaml(text: str) -> dict:
    """The inverse of env_yaml (only the subset it writes)."""
    out = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        k, sep, v = line.partition('": ')
        if not sep or not k.startswith('"'):
            raise Refused(f"unexpected env file line: {line[:60]!r}")
        out[json.loads(k + '"')] = json.loads(v)
    return out


def diff(a: dict, b: dict) -> list[str]:
    keys = sorted(set(a) | set(b))
    return [f"{k}: {a.get(k, '<unset>')!r} -> {b.get(k, '<unset>')!r}" for k in keys if a.get(k) != b.get(k)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--describe", required=True)
    s.add_argument("--out", required=True)
    c = sub.add_parser("carry")
    c.add_argument("--snapshot", required=True)
    c.add_argument("--projection", required=True)
    c.add_argument("--deployment-version")
    c.add_argument("--out", required=True)
    r = sub.add_parser("restore")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--out", required=True)
    k = sub.add_parser("compare")
    k.add_argument("--snapshot", required=True)
    k.add_argument("--env", required=True)
    k.add_argument("--image")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "snapshot":
            snap = snapshot(json.load(open(a.describe)))
            json.dump(snap, open(a.out, "w"), indent=1, sort_keys=True)
            print(f"snapshot: image {short_image(snap['image'])}, commit {snap['commit'] or '?'}, {len(snap['env'])} env vars, "
                  f"{PROJECTION}={snap['env'].get(PROJECTION, '<unset>')}")
        elif a.cmd == "carry":
            snap = json.load(open(a.snapshot))
            env = carried(snap, a.projection, a.deployment_version)
            open(a.out, "w").write(env_yaml(env))
            changes = diff(snap["env"], env)
            print("env carried forward; changes: " + ("; ".join(changes) if changes else "none"))
        elif a.cmd == "restore":
            snap = json.load(open(a.snapshot))
            open(a.out, "w").write(env_yaml(snap["env"]))
            print(f"restore file: {len(snap['env'])} env vars")
        else:
            snap = json.load(open(a.snapshot))
            want = read_env_yaml(open(a.env).read())
            problems = diff(want, snap["env"])
            if a.image and snap["image"] != a.image:
                problems.append(f"image: want {a.image}, job has {snap['image']}")
            for p in problems:
                print("MISMATCH", p)
            if problems:
                return 1
            print("job env" + (" and image" if a.image else "") + " match")
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
