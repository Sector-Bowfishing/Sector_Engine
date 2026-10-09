//
//  ConservationGateTests.swift
//  Sector — Sector Intelligence, Phase 5A (guardrails)
//
//  The L7 gate on Conditions Score spawn naming: gated species never lead,
//  so they never reach naming, regime, boost, reasons, cards or nights.
//

import XCTest
@testable import SectorEngine

final class ConservationGateTests: XCTestCase {


    // Every hour of a warm-season sweep, south + lower-mid, rising and flat water.
    private func sweep(jurisdictions: [String] = [], lat: Double = 30, lon: Double = -91,
                       body: (ConditionsInput, SpawnResult) -> Void) {
        for month in 3...9 {
            for day in [1, 10, 20] {
                for temp in stride(from: 56.0, through: 86.0, by: 2.0) {
                    for trend in [0.0, 1.0] {
                        let i = CE.input(date: CE.utc(2024, month, day, 2), lat: lat, lon: lon,
                                         waterTemp: temp, stageTrend: trend,
                                         jurisdictions: jurisdictions)
                        body(i, SpawnFactor.score(i))
                    }
                }
            }
        }
    }

    private let globallyWithheld = ["Alligator gar", "Black buffalo", "Bigmouth buffalo",
                                    "Smallmouth buffalo", "Shortnose gar"]

    func testStancesMatchRatifiedPolicy() {
        func outcome(_ id: String, _ j: [String] = []) -> GateOutcome {
            ConservationGate.evaluate(speciesId: id, purpose: .spawnTiming, jurisdictions: j).outcome
        }
        XCTAssertEqual(outcome("common_carp"), .allow)
        XCTAssertEqual(outcome("grass_carp"), .conditional)
        XCTAssertEqual(outcome("grass_carp", ["FL"]), .suppress)
        XCTAssertEqual(outcome("silver_carp"), .allow)
        XCTAssertEqual(outcome("smallmouth_buffalo"), .suppress)   // no public spawn timing
        XCTAssertEqual(outcome("bigmouth_buffalo"), .suppress)
        XCTAssertEqual(outcome("black_buffalo"), .refuse)
        XCTAssertEqual(outcome("spotted_gar"), .conditional)
        XCTAssertEqual(outcome("spotted_gar", ["OH"]), .suppress)
        XCTAssertEqual(outcome("shortnose_gar"), .suppress)
        XCTAssertEqual(outcome("alligator_gar"), .refuse)
        XCTAssertEqual(outcome("alligator_gar", ["TX", "LA"]), .refuse)
    }

    func testDeterministic() {
        for p in SpeciesPolicyRegistry.all {
            let a = ConservationGate.evaluate(speciesId: p.speciesId, purpose: .spawnTiming, jurisdictions: ["AL", "OH"])
            let b = ConservationGate.evaluate(speciesId: p.speciesId, purpose: .spawnTiming, jurisdictions: ["AL", "OH"])
            XCTAssertEqual(a, b)
        }
    }

    func testTrophyDeniedByDefault() {
        for p in SpeciesPolicyRegistry.all {
            let d = ConservationGate.evaluate(speciesId: p.speciesId, purpose: .trophyTargeting, jurisdictions: [])
            XCTAssertEqual(d.outcome, .refuse, p.speciesId)
            XCTAssertTrue(d.reasons.contains(.trophyTargetingNotPermitted))
        }
    }

    func testAggregationSuppressedButInternallyKnown() {
        let d = ConservationGate.evaluate(speciesId: "smallmouth_buffalo",
                                          purpose: .aggregationTargeting, jurisdictions: [])
        XCTAssertFalse(d.publicTargetingAllowed)
        XCTAssertTrue(d.internallyKnown)
    }

    func testInformationalPurposesNeverBlocked() {
        let d = ConservationGate.evaluate(speciesId: "alligator_gar", purpose: .regulations, jurisdictions: [])
        XCTAssertEqual(d.outcome, .allow)
    }

    func testSpeciesIdsResolveToPolicies() {
        // Shortnose gar has a policy but no engine spawn row (never modelled).
        XCTAssertFalse(SpeciesDatabase.all.contains { $0.name == "Shortnose gar" })
        for name in globallyWithheld + ["Common carp", "Grass carp", "Spotted gar", "Longnose gar"]
        where name != "Shortnose gar" {
            guard let s = SpeciesDatabase.all.first(where: { $0.name == name }) else {
                return XCTFail("\(name) missing from SpeciesDatabase")
            }
            XCTAssertNotNil(SpeciesPolicyRegistry.policy(s.id), "\(name) → \(s.id)")
        }
    }

    func testGloballyWithheldSpeciesNeverLeadSpawn() {
        for (lat, lon) in [(30.0, -91.0), (29.7, -95.0), (34.4, -86.3), (36.0, -89.5)] {
            sweep(lat: lat, lon: lon) { _, r in
                XCTAssertFalse(globallyWithheld.contains(r.species?.name ?? ""),
                               "gated species led: \(r.species!.name)")
                for name in globallyWithheld {
                    XCTAssertFalse(r.factor.label.contains(name) || r.factor.why.lowercased().contains(name.lowercased()))
                }
            }
        }
    }

    func testAlligatorGarNeverInAnyUserText() {
        sweep(lat: 29.7, lon: -95.0) { i, _ in
            let r = ConditionsAggregator.evaluate(i)
            XCTAssertNotEqual(r.spawnSpeciesName, "Alligator gar")
            let text = (r.topReasons + r.factors.flatMap { [$0.label, $0.why] }
                        + r.whereToLook.flatMap { [$0.title, $0.body] }).joined(separator: " ").lowercased()
            XCTAssertFalse(text.contains("alligator gar"), text)
        }
    }

    func testGatedSpeciesCannotDriveSpawnRegime() {
        // Alligator-gar-only conditions (86°F is above every permitted species'
        // window except tilapia, which is capped south of ~30°N): no spawn regime.
        let i = CE.input(date: CE.utc(2024, 6, 1, 2), lat: 32.5, lon: -93.0, waterTemp: 84, stageTrend: 1.0)
        let r = ConditionsAggregator.evaluate(i)
        if r.regime == ConditionsRegime.spawn {
            XCTAssertNotNil(r.spawnSpeciesName)
            XCTAssertFalse(globallyWithheld.contains(r.spawnSpeciesName ?? ""))
        }
    }

    func testShortnoseCannotRankOnAlabamaWaters() {
        sweep(jurisdictions: ["AL"], lat: 34.4, lon: -86.3) { _, r in
            XCTAssertNotEqual(r.species?.name, "Shortnose gar")
        }
    }

    func testJurisdictionGrassCarpFlorida() {
        sweep(jurisdictions: ["FL"], lat: 28.5, lon: -81.5) { _, r in
            XCTAssertNotEqual(r.species?.name, "Grass carp")
        }
    }

    func testSpottedGarSuppressedInOhio() {
        sweep(jurisdictions: ["OH"], lat: 39.5, lon: -83.0) { _, r in
            XCTAssertNotEqual(r.species?.name, "Spotted gar")
        }
    }

    /// Phase 5A closeout: unassessed freshwater species fail closed.
    private let unassessed = ["Bowfin", "Tilapia", "Freshwater drum", "Gizzard shad",
                              "Striped mullet", "Channel catfish", "Paddlefish", "American shad"]

    func testUnassessedSpeciesFailClosed() {
        for name in unassessed {
            guard let s = SpeciesDatabase.all.first(where: { $0.name == name }) else {
                return XCTFail("\(name) missing")
            }
            XCTAssertNil(SpeciesPolicyRegistry.policy(s.id), name)
            let d = ConservationGate.evaluate(speciesId: s.id, purpose: .spawnTiming, jurisdictions: [])
            XCTAssertEqual(d.outcome, .suppress, name)
            XCTAssertEqual(d.reasons, [.policyNotAssessed], name)
            XCTAssertTrue(d.internallyKnown, name)
            XCTAssertFalse(d.publicTargetingAllowed, name)
        }
    }

    func testUnassessedSpeciesNeverLeadOrAppearInText() {
        // Central Florida (tilapia country), Louisiana, Guntersville, coastal Carolina.
        for (lat, lon) in [(27.5, -81.5), (30.0, -91.0), (34.4, -86.3), (33.8, -78.9)] {
            sweep(lat: lat, lon: lon) { i, r in
                XCTAssertFalse(unassessed.contains(r.species?.name ?? ""),
                               "unassessed species led: \(r.species!.name)")
                let c = ConditionsAggregator.evaluate(i)
                XCTAssertFalse(unassessed.contains(c.spawnSpeciesName ?? ""))
                let text = (c.topReasons + c.factors.flatMap { [$0.label, $0.why] }
                            + c.whereToLook.flatMap { [$0.title, $0.body] }).joined(separator: " ").lowercased()
                for n in unassessed { XCTAssertFalse(text.contains(n.lowercased()), "\(n) in: \(text)") }
            }
        }
    }

    func testCommonCarpStillNamed() {
        let r = SpawnFactor.score(CE.input(date: CE.utc(2024, 5, 15, 2), lat: 34.4, lon: -86.3,
                                           waterTemp: 65, jurisdictions: ["AL"]))
        XCTAssertEqual(r.species?.name, "Common carp")
    }

    func testOutlookNightsCarryJurisdictions() {
        // Nights copy the base input, so the gate sees the same jurisdictions.
        var base = CE.input(jurisdictions: ["AL"])
        base.date = CE.utc(2024, 5, 16, 2)
        XCTAssertEqual(base.jurisdictions, ["AL"])
    }
}
