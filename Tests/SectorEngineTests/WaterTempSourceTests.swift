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
    }

    /// The field every surface shows is the gauge when there is one, in °F,
    /// and the model otherwise.
    func testTheShownTemperatureIsTheScoredOne() throws {
        let model = WaterTempModel(currentF: 82.1, series: [])
        let gauge = WaterLevelReading(siteCode: "07048600", siteName: "BEAVER LAKE NR ROGERS, AR",
                                      parameterCode: "00010", parameterName: "Temperature, water",
                                      value: 26.0, unit: "deg C", dateTime: Date(timeIntervalSince1970: 0),
                                      latitude: 36.3, longitude: -94.0, trend: .steady, change: 0)
        let measured = try XCTUnwrap(SectorEngineAPI.waterTempDTO(gauge: gauge, model: model))
        XCTAssertEqual(measured.source, "gauge")
        XCTAssertEqual(measured.valueF, 78.8, accuracy: 0.01)
        XCTAssertEqual(measured.siteName, "BEAVER LAKE NR ROGERS, AR")
        let modeled = try XCTUnwrap(SectorEngineAPI.waterTempDTO(gauge: nil, model: model))
        XCTAssertEqual(modeled.source, "model")
        XCTAssertEqual(modeled.valueF, 82.1)
        XCTAssertNil(SectorEngineAPI.waterTempDTO(gauge: nil, model: nil))
    }
}
