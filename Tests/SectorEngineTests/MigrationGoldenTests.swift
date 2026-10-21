//
//  MigrationGoldenTests.swift
//  SectorEngineTests
//
//  Repository Foundation V1, Phase 1B: customer-behavior MIGRATION GATES. They answer "if files move,
//  did customer-facing behavior change?" without freezing live values.
//
//  /conditions  is dynamic (live weather, gauges, timestamps), so the gate is deterministic by construction:
//    1. the scoring core (ConditionsAggregator.evaluate) over FROZEN synthetic inputs, default config
//       (no Remote Config, no network, no clock) -> canonical JSON, compared to a committed golden;
//    2. the response CONTRACT: a fully populated golden ConditionsResponse must decode and re-encode
//       (server encoder settings) to the same JSON, which pins every key name and type of every nested DTO.
//  /lakes       is static: version, count, ordered ids, field set, body size and body hash are pinned.
//
//  Intentional changes: regenerate with  SECTOR_UPDATE_GOLDEN=1 swift test --filter MigrationGoldenTests
//  and commit the diff with the reason. Goldens live in verification/fixtures/.
//

import XCTest
@testable import SectorEngine

final class MigrationGoldenTests: XCTestCase {

    private static let root = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    private static let fixtures = root.appendingPathComponent("verification/fixtures")
    private static var updating: Bool { ProcessInfo.processInfo.environment["SECTOR_UPDATE_GOLDEN"] == "1" }

    // MARK: helpers

    /// Doubles rounded to 6 places so the golden is stable across platforms' last-bit differences.
    private func normalize(_ v: Any) -> Any {
        if let d = v as? Double { return (d * 1_000_000).rounded() / 1_000_000 }
        if let a = v as? [Any] { return a.map(normalize) }
        if let m = v as? [String: Any] { return m.mapValues(normalize) }
        return v
    }

    private func canonicalData(_ obj: Any) throws -> Data {
        try JSONSerialization.data(withJSONObject: normalize(obj), options: [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes])
    }

    /// Exact deep equality of two parsed JSON values, portable to Linux (Foundation there has no Objective-C `isEqual` bridge):
    /// both sides re-serialized with sorted keys, no normalization, compared byte for byte.
    private func sameJSON(_ a: Any, _ b: Any) throws -> Bool {
        try JSONSerialization.data(withJSONObject: a, options: [.sortedKeys, .fragmentsAllowed])
            == JSONSerialization.data(withJSONObject: b, options: [.sortedKeys, .fragmentsAllowed])
    }

    private func assertGolden(_ obj: Any, _ relativePath: String, file: StaticString = #filePath, line: UInt = #line) throws {
        let url = Self.fixtures.appendingPathComponent(relativePath)
        if Self.updating {
            try (canonicalData(obj) + Data("\n".utf8)).write(to: url)
            return
        }
        let golden = try JSONSerialization.jsonObject(with: Data(contentsOf: url))
        let actual = try JSONSerialization.jsonObject(with: canonicalData(obj))
        XCTAssertTrue(try sameJSON(golden, actual),
                      "\(relativePath) differs from current behavior. If intentional, regenerate with SECTOR_UPDATE_GOLDEN=1 and record why.",
                      file: file, line: line)
    }

    // MARK: /conditions - scoring core over frozen inputs

    private static let scenarios: [(String, ConditionsInput)] = [
        ("01_clear_calm_baseline", CE.input()),
        ("02_blown_out_gate", CE.input(turbidity: 120)),
        ("03_spawn_night", CE.input(waterTemp: 65)),
        ("04_cold_march_no_spawn", CE.input(date: CE.utc(2024, 3, 15, 2), waterTemp: 55)),
        ("05_full_moon_in_spawn", CE.input(waterTemp: 65, moonIllum: 100, moonAlt: 0.9, cloud: 0)),
        ("06_tailwater_high_generation", CE.input(lat: 35.10, lon: -85.23, isTail: true, genLevel: .high, hasGenFc: true)),
        ("07_tailwater_low_generation", CE.input(lat: 35.10, lon: -85.23, isTail: true, genLevel: .low, hasGenFc: true)),
        ("08_severe_warning", CE.input(severeWarning: "Severe Thunderstorm Warning")),
        ("09_water_temp_unknown", CE.input(waterTemp: nil)),
        ("10_no_turbidity_gauge", CE.input(turbidity: nil)),
        ("11_high_wind", CE.input(wind: 22, gust: 34)),
        ("12_recent_heavy_rain", CE.input(turbidity: 40, rain48: 3.0)),
        ("13_storm_code_falling_pressure", CE.input(weatherCode: 95, precipNow: 0.3, pressure: 29.5, pTrend: .falling)),
        ("14_no_discharge_no_stage_trend", CE.input(stageTrend: nil, dischargeCfs: nil, dischargeTrend: nil)),
    ]

    private func canonical(_ r: ConditionsResult) -> [String: Any] {
        [
            "score": r.score, "band": r.band.rawValue, "regime": r.regime.rawValue,
            "confidence": r.confidence, "confidenceBand": r.confidenceBand.rawValue,
            "baseline": r.baseline, "closingLine": r.closingLine,
            "spawnSpeciesName": r.spawnSpeciesName ?? NSNull(), "spawnNeedsDisclaimer": r.spawnNeedsDisclaimer,
            "topReasons": r.topReasons,
            "factors": r.factors.map { ["key": $0.key.rawValue, "score": $0.score, "weightPct": $0.weightPct,
                                        "label": $0.label, "why": $0.why, "contribution": $0.contribution] as [String: Any] },
            "dormantFactors": r.dormantFactors.map { ["key": $0.key.rawValue, "label": $0.label, "reason": $0.reason] },
            "gates": r.gates.map { ["reason": $0.reason, "cap": $0.cap] as [String: Any] },
            "whereToLook": r.whereToLook.map { ["kind": $0.kind.rawValue, "title": $0.title, "body": $0.body] },
        ]
    }

    func testConditionsScoringCoreMatchesGoldenOnFrozenInputs() throws {
        var out: [String: Any] = [:]
        for (name, input) in Self.scenarios {
            let r = ConditionsAggregator.evaluate(input, config: .default)
            XCTAssertEqual(ConditionsAggregator.evaluate(input, config: .default), r, "\(name): not deterministic under frozen input")
            out[name] = canonical(r)
        }
        out["_meta"] = ["scoreVersion": ConditionsScoreVersion.current, "config": "ConditionsConfig.default",
                        "scenarioCount": Self.scenarios.count]
        try assertGolden(out, "conditions/aggregator_scenarios.golden.json")
    }

    // MARK: /conditions - response contract

    func testConditionsResponseContractRoundTripsExactly() throws {
        let url = Self.fixtures.appendingPathComponent("conditions/response_contract.golden.json")
        let raw = try Data(contentsOf: url)
        let decoder = JSONDecoder(); decoder.dateDecodingStrategy = .iso8601
        let response = try decoder.decode(ConditionsResponse.self, from: raw)
        // The server's encoder (Sources/SectorEngineServer/main.swift jsonResponse).
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        let reencoded = try JSONSerialization.jsonObject(with: encoder.encode(response))
        let golden = try JSONSerialization.jsonObject(with: raw)
        XCTAssertTrue(try sameJSON(golden, reencoded),
                      "ConditionsResponse key names/types changed (a rename or removed field drops out of the round trip).")
        // Every top-level property of the type is present in the golden (no field added without updating the contract).
        let goldenKeys = Set((golden as! [String: Any]).keys)
        let typeKeys = Set(Mirror(reflecting: response).children.compactMap(\.label))
        XCTAssertEqual(typeKeys, goldenKeys, "ConditionsResponse fields vs the contract golden")
    }

    // MARK: /lakes

    func testLakesDirectoryMatchesGolden() throws {
        let d = SectorEngineAPI.lakeDirectory
        let body = try XCTUnwrap(try JSONSerialization.jsonObject(with: d.body) as? [String: Any])
        let lakeObjects = try XCTUnwrap(body["lakes"] as? [[String: Any]])
        var fieldKeys = Set<String>()
        for l in lakeObjects { fieldKeys.formUnion(l.keys) }
        let golden: [String: Any] = [
            "version": d.response.version,
            "etag": "\"\(d.response.version)\"",
            "count": d.response.count,
            "bodyBytes": d.body.count,
            "bodyHashFnv1a64": SectorEngineAPI.fnv1a64Hex(d.body),
            "topLevelKeys": body.keys.sorted(),
            "lakeFieldKeys": fieldKeys.sorted(),
            "orderedLakeIds": d.response.lakes.map(\.id),
            "orderingRule": "as served: the order of LakeDirectory.all (part of the contract; apps read it positionally)",
        ]
        try assertGolden(golden, "lakes/lakes_directory.golden.json")
        XCTAssertEqual(d.response.lakes.count, d.response.count)
        XCTAssertEqual(Set(d.response.lakes.map(\.id)).count, d.response.count)
    }
}
