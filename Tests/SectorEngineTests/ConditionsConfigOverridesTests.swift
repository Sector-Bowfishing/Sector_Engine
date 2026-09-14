//
//  ConditionsConfigOverridesTests.swift
//  SectorEngineTests
//
//  Phase 6 Stage 4: prove a Remote Config `conditions_config` JSON blob decodes and
//  applies onto the compiled defaults — the offline validation of the tuning path
//  (the live Remote Config fetch itself only runs on Cloud Run).
//

import XCTest
@testable import SectorEngine

final class ConditionsConfigOverridesTests: XCTestCase {

    func testDecodesAndApplies() throws {
        let json = """
        {
          "weightsNormal": { "wind": 0.30, "clarity": 0.10 },
          "spawnRegimeThreshold": 55,
          "clarityEstimatedScoreCap": 85,
          "darknessAstroDarkBonus": 8,
          "seeabilityEnabled": false
        }
        """
        let ov = try JSONDecoder().decode(ConditionsConfigOverrides.self, from: Data(json.utf8))
        let c = ov.apply(to: .default)

        // Overridden knobs take the new values...
        XCTAssertEqual(c.weights.normal.wind, 0.30)
        XCTAssertEqual(c.weights.normal.clarity, 0.10)
        XCTAssertEqual(c.spawn.regimeThreshold, 55)
        XCTAssertEqual(c.clarity.estimatedScoreCap, 85)
        XCTAssertEqual(c.darkness.astroDarkBonus, 8)
        XCTAssertFalse(c.seeability.enabled)

        // ...and factors NOT named in the override keep their defaults.
        XCTAssertEqual(c.weights.normal.darkness, ConditionsConfig.default.weights.normal.darkness)
        XCTAssertEqual(c.weights.spawn.spawn, ConditionsConfig.default.weights.spawn.spawn)
    }

    func testDefaultsAndTheExistingTuningAreValid() throws {
        XCTAssertEqual(ConditionsConfigOverrides().problems(), [], "compiled defaults must pass")
        let json = #"{"weightsNormal":{"wind":0.30,"clarity":0.10},"spawnRegimeThreshold":55}"#
        let ov = try JSONDecoder().decode(ConditionsConfigOverrides.self, from: Data(json.utf8))
        XCTAssertEqual(ov.problems(), [], "a realistic console edit must pass")
    }

    func testRejectsConsoleTypos() throws {
        // Zeroed-out regime: every tailwater lake would score 0 "Poor".
        let zeroed = #"{"weightsTailwater":{"clarity":0,"spawn":0,"darkness":0,"wind":0,"waterTemp":0,"level":0,"current":0,"pressure":0,"sky":0,"humidity":0}}"#
        XCTAssertFalse(try decode(zeroed).problems().isEmpty)
        // Negative and out-of-range weights.
        XCTAssertFalse(try decode(#"{"weightsNormal":{"wind":-0.2}}"#).problems().isEmpty)
        XCTAssertFalse(try decode(#"{"weightsNormal":{"clarity":30}}"#).problems().isEmpty)
        // Thresholds outside their scale.
        XCTAssertFalse(try decode(#"{"spawnRegimeThreshold":600}"#).problems().isEmpty)
        XCTAssertFalse(try decode(#"{"clarityEstimatedScoreCap":-1}"#).problems().isEmpty)
    }

    private func decode(_ json: String) throws -> ConditionsConfigOverrides {
        try JSONDecoder().decode(ConditionsConfigOverrides.self, from: Data(json.utf8))
    }

    func testEmptyOverridesAreIdentity() throws {
        let ov = try JSONDecoder().decode(ConditionsConfigOverrides.self, from: Data("{}".utf8))
        let c = ov.apply(to: .default)
        XCTAssertEqual(c.spawn.regimeThreshold, ConditionsConfig.default.spawn.regimeThreshold)
        XCTAssertEqual(c.weights.normal.wind, ConditionsConfig.default.weights.normal.wind)
        XCTAssertEqual(c.clarity.estimatedScoreCap, ConditionsConfig.default.clarity.estimatedScoreCap)
    }
}
