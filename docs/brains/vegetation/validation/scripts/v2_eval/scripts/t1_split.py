"""Writes the DEV/TEST split (A4: sha256(lakeId) first byte even=DEV) and the declared interpretive choices BEFORE any scoring."""
from v2jobs import *
c = nla_split()
c.to_csv(OUT2 / "nla_split.csv", index=False)
decl = dict(written=dt.datetime.now().isoformat(timespec="seconds"), note="written before any v0.2 scoring",
  split=dict(snoco_dev=DEV_SNOCO, snoco_test=TEST_SNOCO, nla_rule="sha256(lakeId).digest()[0] % 2 == 0 -> DEV else TEST; lakeId from registry/lakes.v1.json; eligible = nla_lake_classes.csv rows with n_stations>0 (48; Lake Mead is skipped as in notes 07/11)",
             nla_dev=c[c.split == "DEV"].lakeKey.tolist(), nla_test=c[c.split == "TEST"].lakeKey.tolist()),
  interpretations_fixed_now=[
   "Tuning observer = A. DEV F1 = pooled over Roesiger+Serene, interior cells, raw prevalence, strict-none negatives (<5% of any mapped class, interior), unknown positives count as misses (same as note 11).",
   "Constraint 1: DEV open-water FPR on KNOWN cells = FP/(FP+TN) pooled over dev strict-none interior negatives <= 0.02; if FP+TN == 0 the constraint is UNEVIDENCED and the setting is INADMISSIBLE.",
   "Constraint 2: DEV-NLA negative control = EACH scored dev negative lake (belt_share, observer A, >=10 read belt cells) <= 0.02 (literal per-lake reading used for gate d in note 11); mean reading shown but not used. If zero dev negatives are scored the constraint is UNEVIDENCED and the setting is INADMISSIBLE.",
   "Tie-breaks in order: fewer UNKNOWN interior cells (dev Snohomish, observer A, fraction of interior cells with state UNKNOWN), larger haze_swir, smaller haze_standoff_px. F1 ties = equal to 1e-9.",
   "F1 undefined (no TP and no FP) is treated as 0.",
   "If no setting is admissible: verdict 'no admissible setting', defaults (0.02, 10) are carried to TEST.",
   "TEST NLA gates computed on odd-hash lakes only (gate c needs >=15 scored lakes in >=3 regions; reported NOT_TESTABLE otherwise). Dev lakes are never mixed into a gate verdict.",
   "Gate (a)/(e) on Snohomish TEST lakes use INTERIOR positives (A1.5); lakes with <30 interior positives cannot support (a): NOT_TESTABLE.",
   "SFWMD/UMN use substitute-year scenes (gap years); per prereg metric 5 they are labelled supplementary and cannot be headline gate evidence.",
   "UMR Pool 5: scenes were fetched live in note 09 (no cache): NOT_RUN."])
json.dump(decl, open(OUT2 / "protocol_declared.json", "w"), indent=1)
print(c.groupby(["split", "cls"]).size().unstack())
