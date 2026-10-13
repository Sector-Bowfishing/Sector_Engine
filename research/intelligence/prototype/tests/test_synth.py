"""Tests for the research prototype. Scenario inputs are SYNTHETIC and labelled; stub profiles are not evidence."""
import itertools, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import synth as S
from synth import Factor, Gate


def F(fid, v, kind="MEASURED", support="BANK_AREA", age=1.0, stale_after=6.0, src=None, **kw):
    return Factor(fid, src or f"{fid}-brain@t", v, "", kind, support, age, stale_after, **kw)


def good_zone(**over):
    z = {"waterTemp": F("waterTemp", 74, "OBSERVED", "LAKE"), "depth": F("depth", 0.8, "MODELED", "BANK_AREA"),
         "vegetation": F("vegetation", 0.5, "OBSERVED", "BANK_AREA"), "wind": F("wind", 2, "FORECAST", "BANK_AREA", horizon_h=24, lead_h=0),
         "clarity": F("clarity", 3.5, "MEASURED", "LAKE")}
    z.update(over)
    return z


class Properties(unittest.TestCase):
    def test_R1_unknown_never_improves_exhaustive(self):
        p = S.STUB_SHALLOW_VEG_FEEDER
        space = list(itertools.product(("FAVORABLE", "WORKABLE", "LIMITING", None), repeat=len(p.critical)))
        # drive rate() through synthetic factors that map to each state via a probe profile
        pick = {"FAVORABLE": 2, "WORKABLE": 1, "LIMITING": 0, None: None}
        probe = S.SpeciesProfile("probe", p.critical, (), {fid: (lambda v: ("LIMITING", "WORKABLE", "FAVORABLE")[int(v)]) for fid in p.critical})
        def rating(states):
            fs = {fid: F(fid, None if pick[s] is None else float(pick[s]), "OBSERVED") for fid, s in zip(p.critical, states)}
            return S.RATINGS.index(S.rate(probe, fs, [])[0])
        checked = 0
        for states in space:
            for i, s in enumerate(states):
                if s is None:
                    continue
                unk = list(states); unk[i] = None
                lim = list(states); lim[i] = "LIMITING"
                self.assertLessEqual(rating(unk), max(rating(states), rating(lim)), (states, i))
                self.assertLessEqual(rating(unk), rating(lim) if s != "LIMITING" else rating(states) , (states, i))
                checked += 1
        self.assertGreater(checked, 500)

    def test_R2_gate_overrides_species(self):
        g = [Gate("lightning", "Thunderstorm within 10 mi", "weather@x")]
        for p in (S.STUB_SHALLOW_VEG_FEEDER, S.STUB_OPEN_WATER_EDGE):
            self.assertEqual(S.evaluate_zone("z", p, good_zone(), g).rating, "NOT_TONIGHT")

    def test_R3_blocking_cannot_be_offset(self):
        r = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, good_zone(wind=F("wind", 25)))
        self.assertEqual(r.rating, "POOR")

    def test_R4_top_class_needs_all_critical_known(self):
        full = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, good_zone())
        self.assertEqual(full.rating, "START_HERE")
        z = good_zone(); del z["vegetation"]
        r = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, z)
        self.assertNotEqual(r.rating, "START_HERE")
        self.assertTrue(any("unconfirmed" in c for c in r.caveats))

    def test_R5_agreement_never_raises_confidence(self):
        base = good_zone(depth=F("depth", 0.8, "PROXY", "BANK_AREA"))
        c0 = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, base).confidence
        richer = dict(base, clarity=F("clarity", 4.5, "MEASURED", "BANK_AREA"), extra=F("extra", 1, "MEASURED"))
        c1 = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, richer).confidence
        self.assertEqual(S.CONF.index(c0), S.CONF.index(c1))

    def test_R5_five_weak_signals_do_not_make_high(self):
        weak = {k: F(k, v, "PROXY", "LAKE", age=40.0) for k, v in
                (("waterTemp", 74), ("depth", 0.8), ("vegetation", 0.5), ("wind", 2), ("clarity", 3.5))}
        r = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, weak)
        self.assertIn(r.confidence, ("INSUFFICIENT", "LOW"))

    def test_R6_stale_lowers_and_lake_support_caps(self):
        fresh = S.effective_conf(F("a", 1, "MEASURED"))
        stale = S.effective_conf(F("a", 1, "MEASURED", age=9.0))
        lake = S.effective_conf(F("a", 1, "MEASURED", support="LAKE"))
        self.assertEqual((fresh, stale, lake), (3, 2, 2))

    def test_R7_beyond_horizon_is_unknown_not_persisted(self):
        f = F("wind", 3, "FORECAST", lead_h=30, horizon_h=24)
        self.assertFalse(f.known)
        r = S.evaluate_zone("z", S.STUB_OPEN_WATER_EDGE, good_zone(wind=f))
        self.assertTrue(any(u["factor"] == "wind" for u in r.unknown))

    def test_R8_every_explanation_line_traces_to_a_factor_record(self):
        z = good_zone()
        r = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, z)
        for line in r.best + r.limiting + r.freshness:
            self.assertIn(line["factor"], z)
            self.assertEqual(line["source"], z[line["factor"]].source)
        self.assertTrue(all(l.split(":")[0] in ("BEST", "LIMITING", "UNKNOWN", "FRESHNESS", "CONFIDENCE") for l in r.explanation))

    def test_determinism(self):
        a = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, good_zone())
        b = S.evaluate_zone("z", S.STUB_SHALLOW_VEG_FEEDER, good_zone())
        self.assertEqual(a, b)


class Scenarios(unittest.TestCase):
    def zones(self):
        return {
            "NW shallow grass flat (protected)": good_zone(),
            "main-lake point (exposed, deep, bare)": {"waterTemp": F("waterTemp", 74, "OBSERVED", "LAKE"), "depth": F("depth", 8, "MODELED"),
                "vegetation": F("vegetation", 0.02, "OBSERVED"), "wind": F("wind", 11, "FORECAST", horizon_h=24), "clarity": F("clarity", 3.5, "MEASURED", "LAKE")},
            "SE cove (shallow, veg, windward)": good_zone(wind=F("wind", 12, "FORECAST", horizon_h=24)),
        }

    def test_species_differ(self):
        z = self.zones()
        veg = S.rank_zones(S.STUB_SHALLOW_VEG_FEEDER, z)
        edge = S.rank_zones(S.STUB_OPEN_WATER_EDGE, z)
        self.assertEqual(veg[0].zone, "NW shallow grass flat (protected)")
        self.assertNotEqual([r.zone for r in veg], [r.zone for r in edge])

    def test_mission_example_mixed_evidence(self):
        # Depth modeled/low-confidence, vegetation stale, clarity excellent+measured, temp observed, wind reliable
        z = good_zone(depth=F("depth", 0.8, "MODELED", brain_confidence="LOW"),
                      vegetation=F("vegetation", 0.5, "OBSERVED", age=400.0, stale_after=240.0),
                      clarity=F("clarity", 6.0, "MEASURED", "BANK_AREA"))
        r = S.evaluate_zone("NW flat", S.STUB_SHALLOW_VEG_FEEDER, z)
        self.assertEqual(r.rating, "WORTH_A_LOOK")        # all deciding factors favourable, but R9: LOW confidence cannot top-rank
        self.assertEqual(r.confidence, "LOW")             # the weakest deciding factor (modeled depth, brain says LOW) sets it
        self.assertTrue(any("too uncertain" in c for c in r.caveats))
        text = " ".join(r.explanation)
        self.assertIn("STALE", text); self.assertIn("depth", text)

    def test_vs_production_probe_findings(self):
        p = S.STUB_SHALLOW_VEG_FEEDER
        # (a) cool water that production still scored 84: here the temperature band blocks the shallow-feeder
        cold = S.evaluate_zone("z", p, good_zone(waterTemp=F("waterTemp", 45, "OBSERVED", "LAKE")))
        self.assertEqual(cold.rating, "POOR")
        cool = S.evaluate_zone("z", p, good_zone(waterTemp=F("waterTemp", 55, "OBSERVED", "LAKE")))
        self.assertNotEqual(cool.rating, "START_HERE")      # production scored 50-59 F water 84; here it cannot top-rank
        # (b) unknown temp + unknown depth must not outscore known-cool: production gave 96 vs 79
        unk = good_zone(); del unk["waterTemp"]; del unk["depth"]
        r_unk = S.evaluate_zone("z", p, unk)
        r_cool = S.evaluate_zone("z", p, good_zone(waterTemp=F("waterTemp", 62, "OBSERVED", "LAKE")))
        self.assertLessEqual(S.RATINGS.index(r_unk.rating), S.RATINGS.index("LOW_PRIORITY"))
        # (c) one degree must not move the answer by ~46 points: ordinal bands change by at most one rung at an edge
        a = S.RATINGS.index(S.evaluate_zone("z", p, good_zone(waterTemp=F("waterTemp", 49.9, "OBSERVED", "LAKE"))).rating)
        b = S.RATINGS.index(S.evaluate_zone("z", p, good_zone(waterTemp=F("waterTemp", 50.1, "OBSERVED", "LAKE"))).rating)
        self.assertGreaterEqual(a, 0)
        # (d) whole-lake wind vs protected pocket: zone-level exposure changes the answer
        lake = S.evaluate_zone("z", p, good_zone(wind=F("wind", 12, "FORECAST", "LAKE", horizon_h=24)))
        pocket = S.evaluate_zone("z", p, good_zone(wind=F("wind", 2, "FORECAST", "BANK_AREA", horizon_h=24)))
        self.assertGreater(S.RATINGS.index(pocket.rating), S.RATINGS.index(lake.rating))

    def test_species_not_assessed_is_not_guessed(self):
        out = S.species_first([S.STUB_SHALLOW_VEG_FEEDER], {"stub_shallow_veg_feeder", "mystery_fish"}, self.zones())
        self.assertEqual(out["notAssessed"], ["mystery_fish"]); self.assertEqual(list(out["ranked"]), ["stub_shallow_veg_feeder"])

    def test_trend_needs_two_known_checkpoints(self):
        self.assertEqual(S.trend(["WORTH_A_LOOK", "START_HERE"]), "IMPROVING")
        self.assertEqual(S.trend([None, "START_HERE"]), "UNKNOWN")
        self.assertEqual(S.trend(["START_HERE", "LOW_PRIORITY"]), "WORSENING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
