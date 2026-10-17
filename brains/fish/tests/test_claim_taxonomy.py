"""Taxonomy invariant: claim level (who made the claim) is independent of validation maturity."""
import os
import re
import unittest

SPEC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "brains", "biological-adoption", "BIOLOGICAL_BRAIN_SPEC.md")


def rows():
    out = {}
    for line in open(SPEC, encoding="utf-8"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(c) >= 3 and re.match(r"\**[123]\b", c[1]):
            out[c[0]] = (c[1].strip("*")[0], c[2])
    return out


class ClaimTaxonomy(unittest.TestCase):
    def test_predictive_is_level3_even_when_not_validated(self):
        r = rows()
        k = next(x for x in r if x.startswith("Species response bands"))
        self.assertEqual(r[k][0], "3")
        self.assertIn("NOT_VALIDATED", r[k][1])

    def test_deterministic_transforms_are_level2(self):
        r = rows()
        for name in ("`waterTempBand`", "`spawnWindow`", "`warmRise`"):
            k = next(x for x in r if x.startswith(name))
            self.assertEqual(r[k][0], "2", k)

    def test_invariant_documented(self):
        self.assertIn("separate axes", open(SPEC, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
