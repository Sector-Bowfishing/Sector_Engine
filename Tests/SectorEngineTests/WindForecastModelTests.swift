import XCTest
@testable import SectorEngine

/// The forecast wind model switch (APP_WIND_SOURCE_REVIEW_V1 option 1; W1, W1b). Off by default; it only ever changes wind, and (WS-5) only on
/// the outlook's future nights: tonight stays on best_match.
final class WindForecastModelTests: XCTestCase {
    func testOffByDefaultAndOnlyAGradedModelIsAccepted() {
        XCTAssertNil(WindForecastModel.from([:]))
        XCTAssertNil(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "best_match"]))
        XCTAssertNil(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "gfs_seamless"]))
        XCTAssertEqual(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "ncep_nbm_conus"]), "ncep_nbm_conus")
        if ProcessInfo.processInfo.environment["SECTOR_WIND_FORECAST_MODEL"] == nil { XCTAssertNil(WindForecastModel.current) }
    }

    /// Central Standard Time (UTC-6). Hours: tonight (5th 20:00, 6th 02:00, 6th 06:00), the 6th at noon, tomorrow night (6th 21:00, 7th 02:00).
    private let times = ["2026-11-05T20:00", "2026-11-06T02:00", "2026-11-06T06:00", "2026-11-06T12:00", "2026-11-06T21:00", "2026-11-07T02:00"]

    private func base() throws -> ForecastResponse {
        let json = """
        {"utc_offset_seconds": -21600,
         "hourly": {"time": \(times), "wind_speed_10m": [6.0, 8.0, 9.0, 10.0, 11.0, 12.0],
                    "cloud_cover": [10, 20, 30, 40, 50, 60], "precipitation": [0, 0, 0.1, 0, 0, 0], "weather_code": [0, 1, 61, 0, 3, 3]},
         "daily": {"time": ["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07"],
                   "sunrise": ["2026-11-04T06:19", "2026-11-05T06:20", "2026-11-06T06:21", "2026-11-07T06:22"],
                   "sunset": ["2026-11-04T16:51", "2026-11-05T16:50", "2026-11-06T16:49", "2026-11-07T16:48"],
                   "wind_speed_10m_max": [13.0, 12.0, 14.0, 15.0], "weather_code": [0, 61, 3, 3], "precipitation_sum": [0, 0.1, 0, 0], "cloud_cover_mean": [10, 40, 60, 60]}}
        """
        return try JSONDecoder().decode(ForecastResponse.self, from: Data(json.utf8))
    }

    private func wind(_ hourly: [Double?], _ daily: [Double?]) throws -> WindOnlyResponse {
        let h = hourly.map { $0.map { "\($0)" } ?? "null" }.joined(separator: ","), d = daily.map { $0.map { "\($0)" } ?? "null" }.joined(separator: ",")
        return try JSONDecoder().decode(WindOnlyResponse.self, from: Data("""
        {"hourly": {"time": \(times), "wind_speed_10m": [\(h)]},
         "daily": {"time": ["2026-11-04", "2026-11-05", "2026-11-06", "2026-11-07"], "wind_speed_10m_max": [\(d)]}}
        """.utf8))
    }

    private func at(_ iso: String) -> Date { ISO8601DateFormatter().date(from: iso)! }

    func testOutlookStartIsNoonOfTheLocationsTomorrow() {
        // 21:00 CST on the 5th is already the 6th in UTC; the cutoff still follows the location's own date.
        XCTAssertEqual(WindForecastModel.outlookStart(utcOffsetSeconds: -21600, now: at("2026-11-06T03:00:00Z")).hour, "2026-11-06T12:00")
        // 02:00 CST on the 6th (tonight's window is still open): the cutoff moves to the 7th, so the rest of tonight stays best_match.
        XCTAssertEqual(WindForecastModel.outlookStart(utcOffsetSeconds: -21600, now: at("2026-11-06T08:00:00Z")).day, "2026-11-07")
    }

    func testTonightKeepsBestMatchAndOnlyFutureNightsGetTheModel() throws {
        let b = try base()
        let o = WindForecastModel.overlay(b, with: try wind([1, 1, 1, 4.5, 5.5, 6.5], [1, 1, 7.0, 8.0]), now: at("2026-11-06T02:00:00Z"))   // 20:00 CST, the 5th
        XCTAssertEqual(o.hourly.wind_speed_10m, [6.0, 8.0, 9.0, 4.5, 5.5, 6.5])   // tonight's hours unchanged; noon of the 6th onward is NBM
        XCTAssertEqual(o.daily.wind_speed_10m_max, [13.0, 12.0, 7.0, 8.0])        // yesterday and today unchanged
        XCTAssertEqual(o.hourly.cloud_cover, b.hourly.cloud_cover)               // nothing but wind changes
        XCTAssertEqual(o.hourly.precipitation, b.hourly.precipitation)
        XCTAssertEqual(o.hourly.weather_code, b.hourly.weather_code)
        XCTAssertEqual(o.daily.weather_code, b.daily.weather_code)
        XCTAssertEqual(o.hourly.time, b.hourly.time)
    }

    func testAfterMidnightTheRestOfTonightStillKeepsBestMatch() throws {
        let o = WindForecastModel.overlay(try base(), with: try wind([1, 1, 1, 1, 5.5, 6.5], [1, 1, 1, 8.0]), now: at("2026-11-06T08:00:00Z"))  // 02:00 CST, the 6th
        XCTAssertEqual(o.hourly.wind_speed_10m, [6.0, 8.0, 9.0, 10.0, 11.0, 12.0])  // everything before noon on the 7th stays best_match
        XCTAssertEqual(o.daily.wind_speed_10m_max, [13.0, 12.0, 14.0, 8.0])
    }

    func testANullOrMissingModelValueKeepsBestMatch() throws {
        let b = try base()
        let o = WindForecastModel.overlay(b, with: try wind([nil, nil, nil, nil, 5.5, nil], [nil, nil, nil, nil]), now: at("2026-11-06T02:00:00Z"))
        XCTAssertEqual(o.hourly.wind_speed_10m, [6.0, 8.0, 9.0, 10.0, 5.5, 12.0])
        XCTAssertEqual(o.daily.wind_speed_10m_max, b.daily.wind_speed_10m_max)
    }
}
