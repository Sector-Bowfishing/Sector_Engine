//
//  PressureConsistencyTests.swift
//  SectorEngineTests
//
//  The barometric label, the detail chart, and the score all read pressure from
//  ONE source — the hourly series. Open-Meteo's `current` block is a sub-hour
//  nowcast that can sit a couple hPa off its own hourly series during a front;
//  when it did, the 3-hour tendency (current − the hourly reading 3h ago) read
//  "Falling" on a chart that was plainly rising. The reported current pressure is
//  now anchored to the hourly series at `now`, so they can't disagree.
//

import XCTest
@testable import SectorEngine

final class PressureConsistencyTests: XCTestCase {

    private static let cdt = -5 * 3600

    /// An hourly pressure series that rises steadily through the day, paired with
    /// a `current.pressure_msl` nowcast set well BELOW the series at `now` — the
    /// exact shape that used to read "Falling" over a rising chart.
    private func risingSeriesWithLowNowcast() -> Data {
        let offset = Self.cdt
        let cal = OpenMeteoTime.calendar(utcOffsetSeconds: offset)
        // "now" = 4 PM CDT.
        let nowLocal = "2026-09-15T16:00"
        let start = OpenMeteoTime.instant("2026-09-15T04:00", utcOffsetSeconds: offset)!
        var times: [String] = []
        var pressures: [String] = []
        for h in 0..<13 {                                  // 04:00 → 16:00 local
            let d = start.addingTimeInterval(Double(h) * 3600)
            let c = cal.dateComponents([.year, .month, .day, .hour], from: d)
            times.append("\"" + String(format: "%04d-%02d-%02dT%02d:00", c.year!, c.month!, c.day!, c.hour!) + "\"")
            // Rising: 1015.0 → 1021.0 hPa over the window (+0.5/hr).
            pressures.append(String(format: "%.1f", 1015.0 + Double(h) * 0.5))
        }
        // Series value at now (16:00) is 1021.0 hPa. The nowcast is 2 hPa lower.
        let json = """
        {"utc_offset_seconds": \(offset),
         "current": {"time": "\(nowLocal)", "temperature_2m": 78, "relative_humidity_2m": 60,
                     "precipitation": 0, "weather_code": 0, "cloud_cover": 10, "pressure_msl": 1019.0,
                     "wind_speed_10m": 5, "wind_direction_10m": 180},
         "hourly": {"time": [\(times.joined(separator: ","))],
                    "pressure_msl": [\(pressures.joined(separator: ","))]}}
        """
        return Data(json.utf8)
    }

    func testCurrentPressureIsAnchoredToTheHourlySeries() throws {
        let reading = try WeatherService.reading(from: risingSeriesWithLowNowcast())
        // Not the 1019.0 nowcast — the 1021.0 hourly value at now.
        XCTAssertEqual(reading.pressure, 1021.0, accuracy: 0.01,
                       "current pressure comes from the hourly series at now, not the nowcast")
    }

    func testTendencyMatchesARisingChart() throws {
        let reading = try WeatherService.reading(from: risingSeriesWithLowNowcast())
        // The 3-hour change the label is built from must be positive (rising),
        // matching the series — never negative because of a low nowcast.
        let delta3 = try XCTUnwrap(reading.recentPressureChangeInHg(hours: 3))
        XCTAssertGreaterThan(delta3, 0, "3-hour tendency rises with the series")
        XCTAssertEqual(reading.displayPressureTrend, .rising,
                       "label agrees with the rising chart, not the low nowcast")
    }

    func testFallsBackToNowcastWhenNoHourlyNearNow() throws {
        // Hourly series ends 6 hours before now → no sample within 90 min, so the
        // nowcast is used rather than inventing a value.
        let offset = Self.cdt
        let json = """
        {"utc_offset_seconds": \(offset),
         "current": {"time": "2026-09-15T16:00", "temperature_2m": 70, "relative_humidity_2m": 55,
                     "precipitation": 0, "weather_code": 0, "cloud_cover": 0, "pressure_msl": 1012.0,
                     "wind_speed_10m": 4, "wind_direction_10m": 90},
         "hourly": {"time": ["2026-09-15T06:00","2026-09-15T07:00","2026-09-15T08:00"],
                    "pressure_msl": [1018.0, 1018.0, 1018.0]}}
        """
        let reading = try WeatherService.reading(from: Data(json.utf8))
        XCTAssertEqual(reading.pressure, 1012.0, accuracy: 0.01,
                       "no hourly sample near now → keep the nowcast")
    }
}
