//
//  WaterTemperaturePublicationFixtureTests.swift
//  Water Temperature Brain — the runner's real write set on deterministic inputs, as one flat {path: value} JSON object.
//
//  brains/water-temperature/tests/golden/water_temp_run_updates.json is the input of the Python Publisher artifact builder
//  (brains/water-temperature/runtime/publish_artifact.py) and of the Brain Certification Kit adapter. It is produced ONLY by this test,
//  from the unchanged runner (full-fleet run, injected offline inputs and a fixed generation clock):
//      SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter WaterTemperaturePublicationFixtureTests
//  The fixture keeps every fleet-level path (registry, validation, health, sources, activity) and the per-lake paths of three lakes
//  (a full fleet is 621 lakes); every kept value is exactly what the runner wrote. Without the variable the test fails on any drift.
//

import XCTest
@testable import SectorEngine
@testable import WaterTemperatureBrain

final class WaterTemperaturePublicationFixtureTests: XCTestCase {
    static let fixtureURL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent()      // brains/water-temperature/tests
        .appendingPathComponent("golden/water_temp_run_updates.json")
    static let now = ISO8601DateFormatter().date(from: "2026-07-15T03:00:00Z")!
    static let keptLakes = ["Guntersville_AL", "Wheeler_AL", "Lake_Hartwell_SC"]

    static func day(_ d: String, _ f: Double) -> WaterTempDay {
        WaterTempDay(date: ISO8601DateFormatter().date(from: d + "T12:00:00Z")!, waterF: f, airF: f - 5, localDate: d)
    }

    /// Deterministic offline inputs: every lake gets the same modelled series; Guntersville also has a fresh lake-sensor reading.
    static func inputs(_ lake: DirectoryLake) async -> WaterTemperatureBrain.LakeInputs {
        var m = WaterTempModel(currentF: 80.0, series: [day("2026-07-13", 79.4), day("2026-07-14", 80.0), day("2026-07-15", 80.5), day("2026-07-16", 81.0)])
        m.currentLocalDate = "2026-07-14"; m.timeZoneIdentifier = "America/Chicago"
        var measurement: WaterLevelReading? = nil
        if lake.id == "Guntersville|AL" {
            var r = WaterLevelReading(siteCode: "03573500", siteName: "GUNTERSVILLE", parameterCode: "00010", parameterName: "Temperature, water",
                                      value: 27.0, unit: "deg C", dateTime: now.addingTimeInterval(-2 * 3600), latitude: 34.42, longitude: -86.25,
                                      trend: .rising, change: 0.3)
            r.provider = "USGS"
            measurement = r
        }
        return WaterTemperatureBrain.LakeInputs(lake: lake, measurement: measurement, measurementOrigin: measurement == nil ? nil : "lakeSensor",
                                                model: m, modelFetchFailed: false)
    }

    static func runUpdates() async throws -> Data {
        let store = InMemoryBrainStore(brainId: WaterTemperatureBrain.brainId)
        let r = await WaterTemperatureBrainRunner.run(store: store, options: .init(), now: now, fetchInputs: { await inputs($0) }, generationClock: { now })
        XCTAssertTrue(r.ok, r.writeError ?? "")
        var flat: [String: Any] = [:]
        for patch in store.patches {
            for (path, data) in patch {
                let parts = path.split(separator: "/")
                if ["lakes", "lakeFleet", "snapshots"].contains(String(parts.first ?? "")), parts.count > 1, !keptLakes.contains(String(parts[1])) { continue }
                flat[path] = try JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
            }
        }
        return try JSONSerialization.data(withJSONObject: flat, options: [.sortedKeys, .prettyPrinted, .withoutEscapingSlashes])
    }

    /// PROCESS facts stamped with the wall clock (run/fetch/success times, durations, activity event id and time) are masked to `now`.
    static let maskedNow = "2026-07-15T03:00:00Z", maskedMs = "1784084400000"
    static func stable(_ data: Data) throws -> String {
        var s = String(data: data, encoding: .utf8)!
        s = s.replacingOccurrences(of: #""durationMs" : [0-9]+"#, with: #""durationMs" : 0"#, options: .regularExpression)
        for key in ["lastFetchAt", "lastRun", "lastRunAt", "lastSuccess", "lastSuccessfulRun", "checkedAt"] {
            s = s.replacingOccurrences(of: "\"\(key)\" : \"[0-9T:.-]+Z\"", with: "\"\(key)\" : \"\(maskedNow)\"", options: .regularExpression)
        }
        s = s.replacingOccurrences(of: #"[0-9]{13}-water-temp-"#, with: "\(maskedMs)-water-temp-", options: .regularExpression)
        s = s.replacingOccurrences(of: #""at" : "[0-9T:.-]+Z""#, with: "\"at\" : \"\(maskedNow)\"", options: .regularExpression)
        return s
    }

    func testFixtureIsTheRunnersCurrentWriteSet() async throws {
        let fresh = try await Self.runUpdates()
        if ProcessInfo.processInfo.environment["SECTOR_WRITE_BRAIN_FIXTURES"] == "1" {
            try FileManager.default.createDirectory(at: Self.fixtureURL.deletingLastPathComponent(), withIntermediateDirectories: true)
            try (try Self.stable(fresh) + "\n").write(to: Self.fixtureURL, atomically: true, encoding: .utf8)
            return
        }
        let committed = try String(contentsOf: Self.fixtureURL, encoding: .utf8)
        XCTAssertEqual(numbersByValue(try Self.stable(fresh) + "\n"), numbersByValue(committed),
                       "the Water Temperature runner's write set changed: review the change, then regenerate with SECTOR_WRITE_BRAIN_FIXTURES=1")
    }
}

/// Platform-independent fixture text: every JSON NUMBER token (outside string literals) is rewritten as Swift's shortest exact representation
/// of its Double value, so Darwin's 17-digit `23.100000000000001` and Linux's `23.1` (the same Double) compare equal, while any change of value,
/// key, string, order or structure still fails. Everything else is compared character for character.
func numbersByValue(_ s: String) -> String {
    var out = "", token = "", inString = false, escaped = false
    func flush() {
        if !token.isEmpty { out += Double(token).map { "\($0)" } ?? token; token = "" }
    }
    for c in s {
        if inString {
            out.append(c)
            if escaped { escaped = false } else if c == "\\" { escaped = true } else if c == "\"" { inString = false }
            continue
        }
        if c == "\"" { flush(); inString = true; out.append(c); continue }
        if c.isNumber || c == "-" || c == "+" || c == "." || c == "e" || c == "E" { token.append(c); continue }
        flush(); out.append(c)
    }
    flush()
    return out
}
