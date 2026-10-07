//
//  USGSWaterDataTests.swift
//  SectorEngineTests
//
//  Legacy WaterServices vs the USGS Water Data OGC API, on responses recorded
//  from both at the same moment (Fixtures/USGS, 2026-10-07; each trimmed to a
//  subset of sites). The OGC path must produce the series the legacy path did
//  — same sites, names, units, coordinates, values, timestamps and therefore
//  the same trend — except where legacy was wrong, and those cases are pinned
//  here by name.
//

import XCTest
@testable import SectorEngine

final class USGSWaterDataTests: XCTestCase {

    // MARK: Helpers

    private static let fixtures = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().appendingPathComponent("Fixtures/USGS")

    private func data(_ name: String) throws -> Data {
        try Data(contentsOf: Self.fixtures.appendingPathComponent(name + ".json"))
    }

    private func legacy(_ tag: String) throws -> [String: USGSSeries] {
        let series = try WaterLevelService.decodeLegacy(try data("\(tag)-legacy"))
        return Dictionary(series.map { ("\($0.siteCode)|\($0.parameterCode)", $0) }) { a, _ in a }
    }

    private func ogc(_ tag: String) throws -> [String: USGSSeries] {
        let page = try USGSWaterData.decodePage(try data("\(tag)-continuous"))
        XCTAssertNil(page.next)
        let series = USGSWaterData.assemble(USGSWaterData.group(page.observations),
                                            names: USGSWaterData.decodeNames(try data("\(tag)-locations")),
                                            metadata: USGSWaterData.decodeMetadata(try data("\(tag)-metadata")))
        return Dictionary(uniqueKeysWithValues: series.map { ("\($0.siteCode)|\($0.parameterCode)", $0) })
    }

    /// Asserts every series both APIs returned is identical, and returns the
    /// keys where they differ so each test can account for them.
    @discardableResult
    private func assertMatches(_ tag: String, allowedDifferent: Set<String> = [],
                               ogcOnly: Set<String> = [], ogcFresher: Set<String> = [],
                               file: StaticString = #filePath, line: UInt = #line) throws -> [String: USGSSeries] {
        let l = try legacy(tag), o = try ogc(tag)
        XCTAssertFalse(l.isEmpty, "empty legacy fixture", file: file, line: line)
        XCTAssertEqual(Set(o.keys).subtracting(l.keys), ogcOnly, "series only the OGC API returned", file: file, line: line)
        XCTAssertEqual(Set(l.keys).subtracting(o.keys), [], "series the OGC API lost", file: file, line: line)

        var different: Set<String> = [], fresher: Set<String> = []
        for (key, a) in l {
            guard let b = o[key] else { continue }
            XCTAssertEqual(a.siteName, b.siteName, key, file: file, line: line)
            XCTAssertEqual(a.parameterName, b.parameterName, key, file: file, line: line)
            XCTAssertEqual(a.unit, b.unit, key, file: file, line: line)
            XCTAssertEqual(a.latitude, b.latitude, accuracy: 1e-4, key, file: file, line: line)
            XCTAssertEqual(a.longitude, b.longitude, accuracy: 1e-4, key, file: file, line: line)
            if a.points.map(\.value) != b.points.map(\.value) || a.points.map(\.at) != b.points.map(\.at) {
                // The new API publishes some sites before legacy does: every
                // legacy point is there, plus newer ones.
                let newer = Set(b.points.map { "\($0.at.timeIntervalSince1970)|\($0.value)" })
                let legacyInNew = a.points.allSatisfy { newer.contains("\($0.at.timeIntervalSince1970)|\($0.value)") }
                if legacyInNew, let la = a.points.last?.at, let lb = b.points.last?.at, lb > la {
                    fresher.insert(key)
                } else {
                    different.insert(key)
                }
                continue
            }
            // Same points → the same reading out of the shared trend math, for
            // both the level thresholds and the discharge/turbidity ones.
            // Coordinates are compared above: legacy rounds to 8 decimals.
            for (abs, pct) in [(0.1, 0.0), (20, 0.08), (1.0, 0.10)] {
                guard let ra = WaterLevelService.reading(from: a, absThreshold: abs, pctThreshold: pct),
                      let rb = WaterLevelService.reading(from: b, absThreshold: abs, pctThreshold: pct) else {
                    XCTFail("no reading for \(key)", file: file, line: line); continue
                }
                XCTAssertEqual(ra.value, rb.value, key, file: file, line: line)
                XCTAssertEqual(ra.dateTime, rb.dateTime, key, file: file, line: line)
                XCTAssertEqual(ra.trend, rb.trend, key, file: file, line: line)
                XCTAssertEqual(ra.change, rb.change, key, file: file, line: line)
                XCTAssertEqual(ra.history, rb.history, key, file: file, line: line)
                XCTAssertEqual(ra.id, rb.id, key, file: file, line: line)
            }
        }
        XCTAssertEqual(different, allowedDifferent, "series whose values differ", file: file, line: line)
        XCTAssertEqual(fresher, ogcFresher, "series the OGC API had newer values for", file: file, line: line)
        return o
    }

    // MARK: Recorded comparisons

    func testDischargeMatchesLegacy() throws {
        let o = try assertMatches("northalabama-discharge")
        XCTAssertEqual(Set(o.values.map(\.unit)), ["ft3/s"])
        XCTAssertEqual(Set(o.values.map(\.parameterName)), ["Streamflow, ft&#179;/s"])
    }

    /// 05595000 (Kaskaskia River at New Athens, IL) has a turbidity sensor
    /// discontinued in 2021 listed ahead of the live one. Legacy kept the first
    /// — empty — block and dropped the site; the OGC API returns the live one.
    func testTurbidityMatchesLegacyPlusTheGaugeLegacyDropped() throws {
        let o = try assertMatches("illinois-turbidity", ogcOnly: ["05595000|63680"])
        XCTAssertEqual(o["05595000|63680"]?.unit, "FNU")
    }

    /// Fort Worth has six sites reporting gage height from two sensors.
    /// Legacy took whichever block USGS listed first; for three of them that
    /// was the sensor USGS describes as the secondary one, reading 5–14 ft off the
    /// primary. The OGC path takes the Primary one.
    func testLevelMatchesLegacyExceptSecondarySensors() throws {
        let legacySecondary: Set<String> = ["07332605|00065", "08048890|00065", "08062095|00065"]
        // 08044500 published four 15-minute values to the new API before legacy.
        let o = try assertMatches("fortworth-level", allowedDifferent: legacySecondary,
                                  ogcFresher: ["08044500|00065"])
        let meta = USGSWaterData.decodeMetadata(try data("fortworth-level-metadata"))
        XCTAssertFalse(meta.isEmpty)
        for key in legacySecondary { XCTAssertNotNil(o[key]) }
    }

    // MARK: Assembly rules

    func testSentinelAndUnparseableValuesAreDropped() throws {
        let json = """
        {"type":"FeatureCollection","features":[
         {"type":"Feature","id":"a","geometry":{"type":"Point","coordinates":[-86.3,34.6]},
          "properties":{"time_series_id":"t1","monitoring_location_id":"USGS-1","parameter_code":"00065","time":"2026-10-07T08:00:00+00:00","value":"-999999","unit_of_measure":"ft"}},
         {"type":"Feature","id":"b","geometry":{"type":"Point","coordinates":[-86.3,34.6]},
          "properties":{"time_series_id":"t1","monitoring_location_id":"USGS-1","parameter_code":"00065","time":"2026-10-07T08:15:00+00:00","value":null,"unit_of_measure":"ft"}},
         {"type":"Feature","id":"c","geometry":{"type":"Point","coordinates":[-86.3,34.6]},
          "properties":{"time_series_id":"t1","monitoring_location_id":"USGS-1","parameter_code":"00065","time":"2026-10-07T08:30:00+00:00","value":"2.50","unit_of_measure":"ft"}}
        ],"links":[{"rel":"next","href":"https://example.test/next"}]}
        """
        let page = try USGSWaterData.decodePage(Data(json.utf8))
        XCTAssertEqual(page.observations.map(\.value), [2.5])
        XCTAssertEqual(page.next?.absoluteString, "https://example.test/next")
    }

    func testPointsAreSortedOldestFirst() {
        let t0 = Date(timeIntervalSince1970: 1_000_000)
        func obs(_ dt: TimeInterval, _ v: Double) -> USGSWaterData.Observation {
            .init(seriesId: "t", siteCode: "1", parameterCode: "00065", unit: "ft",
                  at: t0.addingTimeInterval(dt), value: v, latitude: 34, longitude: -86)
        }
        let s = USGSWaterData.assemble(USGSWaterData.group([obs(1800, 3), obs(0, 1), obs(900, 2)]),
                                       names: ["1": "SITE"], metadata: [:])
        XCTAssertEqual(s.first?.points.map(\.value), [1, 2, 3])
        let r = WaterLevelService.reading(from: s[0], absThreshold: 0.1, pctThreshold: 0)
        XCTAssertEqual(r?.trend, .rising)
        XCTAssertEqual(r?.change, 2)
        XCTAssertEqual(r?.dateTime, t0.addingTimeInterval(1800))
    }

    func testSensorPickPrefersPrimaryThenSiteThenOldest() {
        let t = Date()
        func raw(_ id: String, _ v: Double) -> USGSWaterData.RawSeries {
            .init(seriesId: id, siteCode: "1", parameterCode: "00065", unit: "ft",
                  latitude: 0, longitude: 0, points: [(v, t)])
        }
        func meta(_ p: String?, _ sub: String?, _ begin: String) -> USGSWaterData.SeriesMeta {
            .init(primary: p, sublocation_identifier: sub, begin: begin)
        }
        let pick = { (m: [String: USGSWaterData.SeriesMeta]) in
            USGSWaterData.assemble([raw("a", 1), raw("b", 2)], names: [:], metadata: m).first?.points.first?.value
        }
        XCTAssertEqual(pick(["a": meta(nil, nil, "2000"), "b": meta("Primary", nil, "2020")]), 2)
        XCTAssertEqual(pick(["a": meta("Primary", "Flood Side", "2000"), "b": meta("Primary", nil, "2020")]), 2)
        XCTAssertEqual(pick(["a": meta("Primary", nil, "2007"), "b": meta("Primary", nil, "2014")]), 1)
        XCTAssertEqual(pick([:]), 1, "no metadata → stable by id")
    }

    func testLegacyUnitAndNameSpellings() {
        XCTAssertEqual(USGSWaterData.legacyUnit("ft^3/s"), "ft3/s")
        XCTAssertEqual(USGSWaterData.legacyUnit("degC"), "deg C")
        XCTAssertEqual(USGSWaterData.legacyUnit("_FNU"), "FNU")
        XCTAssertEqual(USGSWaterData.legacyUnit("ft"), "ft")
        XCTAssertEqual(USGSWaterData.legacyParameterName("00065", unit: "ft"), "Gage height, ft")
    }

    func testContinuousURLAsksForTheLookbackWindow() throws {
        let url = try XCTUnwrap(USGSWaterData.continuousURL(west: -86.5, south: 34.2, east: -86.0, north: 34.7,
                                                            parameterCodes: "00065,62614", lookback: "PT12H"))
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let q = Dictionary(uniqueKeysWithValues: items.map { ($0.name, $0.value ?? "") })
        XCTAssertEqual(url.path, "/ogcapi/v1/collections/continuous/items")
        XCTAssertEqual(q["bbox"], "-86.50000,34.20000,-86.00000,34.70000")
        XCTAssertEqual(q["parameter_code"], "00065,62614")
        XCTAssertEqual(q["time"], "PT12H")
    }
}
