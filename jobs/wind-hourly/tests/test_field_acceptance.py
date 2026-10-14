from sector_wind.brain import field_acceptance as A


def test_clopper_pearson_upper_known_values():
    assert abs(A.cp_upper(0, 20) - 0.1391) < 0.002 and abs(A.cp_upper(1, 40) - 0.1131) < 0.003 and A.cp_upper(5, 5) == 1.0 and A.cp_upper(0, 0) == 1.0


def test_small_lucky_sample_cannot_pass_but_adequate_clean_sample_can():
    good_exp = {"exact": 0.7, "withinOne": 0.95, "protectedCalls": 25, "dangerousMiss": 0}
    good_surf = {"exact": 0.65, "withinOne": 0.95, "roughCalledCalm": 0, "confusion(pred->obs)": {"CALM": {"CALM": 25, "MODERATE": 3, "ROUGH": 0}}}
    vol = {"observations": 80, "nights": 9, "lakes": 2, "quadrants": 3, "windGe8": 20}
    assert A.evaluate(good_exp, good_surf, vol)["pass"]["all"] is True
    assert A.evaluate({**good_exp, "protectedCalls": 8}, good_surf, vol)["pass"]["exposure"] is False          # too few calls
    assert A.evaluate({**good_exp, "dangerousMiss": 1}, good_surf, vol)["pass"]["exposure"] is False         # 1/25 = 4% but upper bound > 15%
    assert A.evaluate(good_exp, {**good_surf, "roughCalledCalm": 1}, vol)["pass"]["surface"] is False
    assert A.evaluate(good_exp, good_surf, {**vol, "nights": 3})["pass"]["volume"] is False
    assert A.evaluate(good_exp, good_surf, vol)["status"] == "PROPOSED_NOT_FROZEN"
