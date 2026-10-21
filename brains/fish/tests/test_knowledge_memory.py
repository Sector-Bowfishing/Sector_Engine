"""Approved memory (Cortex 2.1 BR-10, BR-11, BR-18): Fish's approved knowledge is the hash-verified private bundle (latest.json -> manifest sha256 ->
per-file sha256/bytes). Missing, unreadable, corrupt or tampered memory refuses the job (exit 2, nothing published); it never crashes into a partial
run and never falls back to research data, the repo or a default. Uses only a synthetic bundle in a temp dir and --offline (no network, no RTDB)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import biological_brain as bb
import run
from test_biological_brain import not_assessed, synthetic_profile, write_bundle

RUNTIME = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runtime")


class MissingMemoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_bundle(self.dir, [synthetic_profile(), not_assessed()])

    def tearDown(self):
        shutil.rmtree(self.dir)

    def load(self):
        return bb.load_bundle(run.local_reader(self.dir))

    def test_a_missing_pointer_is_a_refusal_not_a_crash(self):
        os.remove(os.path.join(self.dir, "latest.json"))
        with self.assertRaisesRegex(bb.BundleError, "missing or unreadable: latest.json"):
            self.load()

    def test_a_corrupt_pointer_is_refused(self):
        open(os.path.join(self.dir, "latest.json"), "w").write("{not json")
        with self.assertRaisesRegex(bb.BundleError, "not valid JSON"):
            self.load()

    def test_a_pointer_without_a_manifest_is_refused(self):
        p = json.load(open(os.path.join(self.dir, "latest.json")))
        p.pop("manifestSha256")
        json.dump(p, open(os.path.join(self.dir, "latest.json"), "w"))
        with self.assertRaisesRegex(bb.BundleError, "unexpected pointer"):
            self.load()

    def test_a_missing_artifact_named_by_the_manifest_is_refused(self):
        pointer = json.load(open(os.path.join(self.dir, "latest.json")))
        root = os.path.join(self.dir, os.path.dirname(pointer["manifest"]))
        manifest = json.load(open(os.path.join(self.dir, pointer["manifest"])))
        os.remove(os.path.join(root, manifest["files"][0]["path"]))
        with self.assertRaisesRegex(bb.BundleError, "missing or unreadable"):
            self.load()

    def _job(self, *args):
        env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": RUNTIME}          # no HOME, no research workspace, no credentials; --offline reads no RTDB
        return subprocess.run([sys.executable, os.path.join(RUNTIME, "run.py"), *args, "--bundle", self.dir, "--offline", "--out", os.path.join(self.dir, "out")],
                              cwd=self.dir, env=env, capture_output=True, text=True, timeout=120)

    def test_the_job_refuses_with_exit_2_when_memory_is_missing(self):
        os.remove(os.path.join(self.dir, "latest.json"))
        for mode in ("--plan", "--dry-run"):
            out = self._job(mode)
            self.assertEqual(out.returncode, 2, out.stderr)
            self.assertIn("REFUSED (nothing published)", out.stderr)
            self.assertNotIn("Traceback", out.stderr)


if __name__ == "__main__":
    unittest.main()
