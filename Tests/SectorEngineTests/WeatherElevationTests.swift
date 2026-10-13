//
//  WeatherElevationTests.swift
//  SectorEngineTests
//
//  The gauge context tells a bluff above a dam's pool from the tailwater below
//  it by ground elevation, and the only elevation the engine has is the one
//  Open-Meteo already sends on every forecast response (meters, top level).
//  These pin that it's decoded and converted to feet, and that a response
//  without it still decodes.
//

import XCTest
@testable import SectorEngine

final class WeatherElevationTests: XCTestCase {

    /// A minimal forecast response, optionally with Open-Meteo's `elevation`.
    private func response(elevation: String?) -> Data {
        let elevationField = elevation.map { "\"elevation\": \($0)," } ?? ""
        return Data("""
        {"utc_offset_seconds": -18000, \(elevationField)
         "current": {"time": "2026-09-14T17:00", "temperature_2m": 88, "relative_humidity_2m": 55,
                     "precipitation": 0, "weather_code": 1, "cloud_cover": 20, "pressure_msl": 1014,
                     "wind_speed_10m": 4, "wind_direction_10m": 200},
         "hourly": {"time": ["2026-09-14T05:00", "2026-09-14T17:00"],
                    "pressure_msl": [1015.0, 1014.0]}}
        """.utf8)
    }

    func testDecodesElevationInFeet() throws {
        // Bull Shoals production coordinate: Open-Meteo reports 239 m (~784 ft),
        // 130 ft above the ~654 ft pool — the bluff, not the tailwater.
        let reading = try WeatherService.reading(from: response(elevation: "239.0"))
        let feet = try XCTUnwrap(reading.elevationFt)
        XCTAssertEqual(feet, 239.0 * 3.28084, accuracy: 1e-9)
        XCTAssertEqual(feet, 784, accuracy: 0.5)
    }

    func testMissingElevationDecodesAsNil() throws {
        let reading = try WeatherService.reading(from: response(elevation: nil))
        XCTAssertNil(reading.elevationFt)
        XCTAssertEqual(reading.temperature, 88, "the rest of the reading is unaffected")
    }
}
