//
//  WaterMLDecodingTests.swift
//  SectorEngineTests
//
//  GaugeSelector can only tell a lake's pool from the release below its dam if
//  the decoder hands it every method block with its site type and method text.
//  These pin that decoding offline (inline WaterML JSON, no network), the
//  timestamp rule that keeps a gage of unknown age out of the render, the
//  parameter codes each input asks USGS for, and the legacy kill-switch pick.
//

import XCTest
@testable import SectorEngine

final class WaterMLDecodingTests: XCTestCase {

    /// One timeSeries in the IV service's JSON shape, extra keys included so the
    /// decoder is shown to ignore what it doesn't use.
    private func waterML(siteCode: String = "07263450",
                         siteName: String = "Arkansas River at Murray Dam near Little Rock, AR",
                         siteProperty: String? = #"[{"value":"ST","name":"siteTypeCd"},{"value":"11110207","name":"hucCd"}]"#,
                         parameterCode: String = "00065",
                         blocks: [String]) -> Data {
        let property = siteProperty.map { #","siteProperty":\#($0)"# } ?? ""
        let json = #"""
        {"name":"ns1:timeSeriesResponseType","value":{"queryInfo":{"note":[]},"timeSeries":[{
          "sourceInfo":{"siteName":"\#(siteName)",
            "siteCode":[{"value":"\#(siteCode)","network":"NWIS","agencyCode":"USGS"}],
            "timeZoneInfo":{"siteUsesDaylightSavingsTime":true},
            "geoLocation":{"geogLocation":{"srs":"EPSG:4326","latitude":34.7931,"longitude":-92.3583},"localSiteXY":[]},
            "note":[]\#(property)},
          "variable":{"variableCode":[{"value":"\#(parameterCode)","network":"NWIS","vocabulary":"NWIS:UnitValues","variableID":45807202,"default":true}],
            "variableName":"Gage height, ft","unit":{"unitCode":"ft"},"noDataValue":-999999.0},
          "values":[\#(blocks.joined(separator: ","))],
          "name":"USGS:\#(siteCode):\#(parameterCode):00000"}]}}
        """#
        return Data(json.utf8)
    }

    private func block(_ points: [(String, String)], method: String?) -> String {
        let values = points
            .map { #"{"value":"\#($0.0)","qualifiers":["P"],"dateTime":"\#($0.1)"}"# }
            .joined(separator: ",")
        let methodJSON = method.map { #","method":[{"methodDescription":"\#($0)","methodID":69928}]"# } ?? ""
        return #"{"value":[\#(values)],"qualifier":[]\#(methodJSON),"source":[],"offset":[],"sample":[]}"#
    }

    // A lock publishes its pool and its release as two blocks of ONE series.
    // The old decoder read only block 0, so a tailwater spot below Murray L&D
    // got the HEADWATER (upper pool) value.
    func testDecodesSiteTypeAndEveryMethodBlock() throws {
        let data = waterML(blocks: [
            block([("249.36", "2026-09-14T17:00:00.000-05:00"),
                   ("249.35", "2026-09-14T17:15:00.000-05:00")], method: "HEADWATER"),
            block([("231.26", "2026-09-14T17:00:00.000-05:00"),
                   ("231.21", "2026-09-14T17:15:00.000-05:00")], method: "TAILWATER"),
        ])

        let readings = try WaterLevelService.parseWaterML(data, absThreshold: 0.1, pctThreshold: 0)

        XCTAssertEqual(readings.count, 2)
        XCTAssertEqual(readings.map(\.blockIndex), [0, 1])
        XCTAssertEqual(readings.map(\.methodDescription), ["HEADWATER", "TAILWATER"])
        XCTAssertEqual(readings.map(\.siteTypeCode), ["ST", "ST"])
        XCTAssertEqual(readings.map(\.value), [249.35, 231.21])
        XCTAssertEqual(readings.map(\.id), ["07263450-00065-0", "07263450-00065-1"])
        XCTAssertNotEqual(readings[0].id, readings[1].id)
        XCTAssertEqual(readings[1].history, [231.26, 231.21])
        XCTAssertEqual(readings[1].change, 231.21 - 231.26, accuracy: 1e-9)
        XCTAssertEqual(readings[1].trend, .steady, "a 0.05 ft move is under the 0.1 ft floor")
        XCTAssertEqual(readings[0].dateTime, Date(timeIntervalSince1970: 1_789_424_100))
        XCTAssertNil(readings[0].distanceMiles, "distance is stamped by the fetch, not the decoder")
        XCTAssertNil(readings[0].acceptance)
    }

    // A point whose timestamp doesn't parse is dropped. The reading must keep the
    // last GOOD point — never adopt the garbage point's value, and never be
    // stamped `Date()`, which would pass every freshness check.
    func testUnparseableTimestampIsDroppedNotStampedNow() throws {
        let data = waterML(blocks: [
            block([("1.0", "2026-09-14T20:00:00.000-05:00"),
                   ("9.0", "garbage")], method: nil),
        ])

        let readings = try WaterLevelService.parseWaterML(data, absThreshold: 0.1, pctThreshold: 0)

        XCTAssertEqual(readings.count, 1)
        XCTAssertEqual(readings.first?.value, 1.0)
        XCTAssertEqual(readings.first?.dateTime, Date(timeIntervalSince1970: 1_789_434_000))
        XCTAssertEqual(readings.first?.history, [1.0])
        XCTAssertEqual(readings.first?.change, 0)
    }

    // Blocks with no usable points emit nothing but don't renumber the rest, and
    // blank or missing metadata decodes as nil rather than failing the response.
    func testEmptyBlockSkippedKeepsIndexAndBlankMetadataIsNil() throws {
        let data = waterML(siteProperty: nil, blocks: [
            block([("-999999", "2026-09-14T20:00:00.000-05:00")], method: "HEADWATER"),
            block([("3.2", "2026-09-14T20:00:00.000-05:00")], method: ""),
        ])

        let readings = try WaterLevelService.parseWaterML(data, absThreshold: 0.1, pctThreshold: 0)

        XCTAssertEqual(readings.count, 1)
        XCTAssertEqual(readings.first?.blockIndex, 1)
        XCTAssertNil(readings.first?.methodDescription)
        XCTAssertNil(readings.first?.siteTypeCode)
        XCTAssertEqual(readings.first?.value, 3.2)
    }

    func testNonWaterMLBodyThrowsDecodingFailed() {
        XCTAssertThrowsError(try WaterLevelService.parseWaterML(Data("<html>".utf8),
                                                                absThreshold: 0.1, pctThreshold: 0)) { error in
            guard case WaterLevelError.decodingFailed = error else {
                return XCTFail("expected decodingFailed, got \(error)")
            }
        }
    }

    // Most lakes publish their pool under 62615 or 00062, not 62614; without
    // them the nearest "level" at Lanier is the tailwater stage below the dam.
    // The other inputs keep the thresholds and search distances they always had.
    func testLevelKindRequestsPoolCodes() {
        XCTAssertEqual(GaugeKind.level.parameterCd, "00065,62614,62615,00062")
        XCTAssertEqual(GaugeKind.level.absThreshold, 0.1)
        XCTAssertEqual(GaugeKind.level.pctThreshold, 0)
        XCTAssertEqual(GaugeKind.level.searchMiles, WaterLevelService.maxUsefulMiles)

        XCTAssertEqual(GaugeKind.discharge.parameterCd, "00060")
        XCTAssertEqual(GaugeKind.discharge.absThreshold, 20)
        XCTAssertEqual(GaugeKind.discharge.pctThreshold, 0.08)
        XCTAssertEqual(GaugeKind.discharge.searchMiles, WaterLevelService.maxUsefulMiles)

        XCTAssertEqual(GaugeKind.waterTemp.parameterCd, "00010")
        XCTAssertEqual(GaugeKind.waterTemp.absThreshold, 0.5)
        XCTAssertEqual(GaugeKind.waterTemp.pctThreshold, 0)
        XCTAssertEqual(GaugeKind.waterTemp.searchMiles, ConditionsInputBuilder.maxWaterTempDistanceMiles)

        XCTAssertEqual(GaugeKind.turbidity.parameterCd, "63680")
        XCTAssertEqual(GaugeKind.turbidity.absThreshold, 1.0)
        XCTAssertEqual(GaugeKind.turbidity.pctThreshold, 0.10)
        XCTAssertEqual(GaugeKind.turbidity.searchMiles, ConditionsInputBuilder.maxTurbidityDistanceMiles)
    }

    // The kill-switch pick is today's: nearest block-0 reading within the cap.
    // A nearer TAILWATER block 1 must not start winning when selection is off.
    func testLegacyNearestIsFirstBlockNearestWithinCap() {
        func reading(_ site: String, block: Int, miles: Double?) -> WaterLevelReading {
            var r = WaterLevelReading(siteCode: site, siteName: site, parameterCode: "00065",
                                      parameterName: "Gage height, ft", value: 1, unit: "ft",
                                      dateTime: Date(), latitude: 0, longitude: 0,
                                      trend: .steady, change: 0, distanceMiles: miles)
            r.blockIndex = block
            return r
        }
        let candidates = [
            reading("A", block: 0, miles: 3.0),
            reading("B", block: 1, miles: 0.5),
            reading("C", block: 0, miles: 2.0),
            reading("D", block: 0, miles: nil),
        ]

        XCTAssertEqual(WaterLevelService.legacyNearest(candidates, maxMiles: 40)?.siteCode, "C")
        XCTAssertNil(WaterLevelService.legacyNearest(candidates, maxMiles: 1.5),
                     "beyond the cap is not your water, and block 1 is never the legacy pick")
    }
}
