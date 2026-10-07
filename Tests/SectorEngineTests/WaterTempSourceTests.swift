//
//  WaterTempSourceTests.swift
//  SectorEngineTests
//
//  The water temperature a lake shows is its own: a lake gauge's surface
//  sensor when it has one, else the model — never a river's, never a sensor
//  at the bottom — and it is the same number the score ran on.
//

import XCTest
@testable import SectorEngine

final class WaterTempSourceTests: XCTestCase {

    /// A buoy's profile has one surface series; the deep and bottom ones are
    /// a different, colder water.
    func testOnlyTheSurfaceSensorCounts() {
        XCTAssertTrue(WaterLevelService.isSurfaceSeries(nil))
        XCTAssertTrue(WaterLevelService.isSurfaceSeries("Temperature at 1.0 ft"))
        XCTAssertTrue(WaterLevelService.isSurfaceSeries("0.5 m below surface"))
        XCTAssertTrue(WaterLevelService.isSurfaceSeries("[Buoy 3]"))
        XCTAssertFalse(WaterLevelService.isSurfaceSeries("20 m depth"))
        XCTAssertFalse(WaterLevelService.isSurfaceSeries("Temperature at 6 ft"))
        XCTAssertFalse(WaterLevelService.isSurfaceSeries("Bottom"))
        // An elevation is not a depth (Lake Champlain's surface sensor).
        XCTAssertTrue(WaterLevelService.isSurfaceSeries("[at 93.0 ft above NGVD of 1929]"))
    }

    /// The field every surface shows is the resolved state: a FRESH lake gauge
    /// (°F), else the model — the same decision the score builder takes.
    /// (Stage 2E: the old version passed a 1970 reading as "gauge"; a reading
    /// that old is not the current water and is no longer shown as such.)
    func testTheShownTemperatureIsTheScoredOne() throws {
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        let model = WaterTempModel(currentF: 82.1, series: [])
        let gauge = WaterLevelReading(siteCode: "07048600", siteName: "BEAVER LAKE NR ROGERS, AR",
                                      parameterCode: "00010", parameterName: "Temperature, water",
                                      value: 26.0, unit: "deg C", dateTime: now.addingTimeInterval(-3600),
                                      latitude: 36.3, longitude: -94.0, trend: .steady, change: 0)
        let measured = try XCTUnwrap(SectorEngineAPI.waterTempDTO(
            state: WaterTemperatureResolver.resolve(measurement: gauge, model: model, at: now)))
        XCTAssertEqual(measured.source, "gauge")
        XCTAssertEqual(measured.valueF, 78.8, accuracy: 0.01)
        XCTAssertEqual(measured.siteName, "BEAVER LAKE NR ROGERS, AR")
        let modeled = try XCTUnwrap(SectorEngineAPI.waterTempDTO(
            state: WaterTemperatureResolver.resolve(measurement: nil, model: model, at: now)))
        XCTAssertEqual(modeled.source, "model")
        XCTAssertEqual(modeled.valueF, 82.1)
        XCTAssertNil(SectorEngineAPI.waterTempDTO(
            state: WaterTemperatureResolver.resolve(measurement: nil, model: nil, at: now)))
    }
}
