# Next Implementation Plan

Research-only campaign; nothing below is started. Ordered by value per effort.

## 0. Michael decisions (this week)
1. Adopt the conservative species scores into the **private** bundle (a new `researchVersion`), or ask for a review first.
2. Decide the 7 zero ASSESSED rows (assess narrowly vs mark NOT_ASSESSED) and the tilapia row split.
3. Decide whether to amend `knowledgeDepth` to an importance-weighted statistic.
4. Approve (or not) starting Biological State on one lake (Guntersville, since presence and several packets are tied to it).

## 1. Convert research to rules (highest value, private bundle only)
Write engine-format rules for the eight principal non-carp targets from the packets, following the common-carp template (conditions, location implication, mechanism, exceptions, evidence, transfer, input dependency). Priority order by customer impact × evidence: silver carp (flow), grass carp (vegetation/runs), alligator gar (flood spawn), spotted gar (vegetated shallows/night), longnose gar (tailwater), smallmouth buffalo (tributary/tailrace staging), bigmouth buffalo (level + temp spawn), bighead. Tag each rule with transfer and independence count.

## 2. Rule-consumption pathway
Expose rule metadata (not rule text) to Intelligence; define `conditionFeatures` jointly with Intelligence (see cross-brain doc). Wire a "species-supported; local transfer untested" confidence label.

## 3. Prototype Biological State (needs approval)
IN_PROGRESS on Guntersville: for each present species, output archetype-based "favoured habitat classes" for the night given temperature, stage trend, clarity band, season. No coordinates. Log predictions for validation.

## 4. Validation pipeline
Implement the observation schema and prediction log from the validation strategy; start collecting structured Sector observations; freeze rules before comparison.

## 5. Targeted desk gaps (limited remaining value)
Retrieve the blocked primary sources (blocker 7) via library access, plus agency data requests: TVA/TWRA/ADCNR electrofishing seasonal catch by habitat, Kentucky Lake paupier trawl data, Lake Guntersville fisheries reports, Pickwick/Wheeler tailwater surveys. Desk research beyond these is now giving diminishing returns: the principal-species gaps are empirical, not literature gaps.

## 6. Production hygiene (separate approvals)
Review `SpeciesDatabase.swift` strings flagged in the spawn doc (longnose temperature, smallmouth vegetation claim, silver/bighead/grass habitat text). Not changed here.
