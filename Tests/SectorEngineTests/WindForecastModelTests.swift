import XCTest
@testable import SectorEngine

/// The forecast wind model switch (APP_WIND_SOURCE_REVIEW_V1 option 1; W1, W1b). Off by default; it only ever changes wind.
final class WindForecastModelTests: XCTestCase {
    func testOffByDefaultAndOnlyAGradedModelIsAccepted() {
        XCTAssertNil(WindForecastModel.from([:]))
        XCTAssertNil(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "best_match"]))
        XCTAssertNil(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "gfs_seamless"]))
        XCTAssertEqual(WindForecastModel.from(["SECTOR_WIND_FORECAST_MODEL": "ncep_nbm_conus"]), "ncep_nbm_conus")
        if ProcessInfo.processInfo.environment["SECTOR_WIND_FORECAST_MODEL"] == nil { XCTAssertNil(WindForecastModel.current) }
    }

    private func base() throws -> ForecastResponse {
        let json = """
        {"hourly": {"time": ["2026-11-05T20:00", "2026-11-05T21:00", "2026-11-05T22:00"], "wind_speed_10m": [6.0, 8.0, 9.0],
                    "cloud_cover": [10, 20, 30], "precipitation": [0, 0, 0.1], "weather_code": [0, 1, 61]},
         "daily": {"time": ["2026-11-05", "2026-11-06"], "sunrise": ["2026-11-05T06:20", "2026-11-06T06:21"], "sunset": ["2026-11-05T16:50", "2026-11-06T16:49"],
                   "wind_speed_10m_max": [12.0, 14.0], "weather_code": [61, 3], "precipitation_sum": [0.1, 0], "cloud_cover_mean": [40, 60]}}
        """
        return try JSONDecoder().decode(ForecastResponse.self, from: Data(json.utf8))
    }

    func testOverlayReplacesOnlyWindAndOnlyWhereTheModelHasAValue() throws {
        let wind = try JSONDecoder().decode(WindOnlyResponse.self, from: Data("""
        {"hourly": {"time": ["2026-11-05T20:00", "2026-11-05T21:00", "2026-11-05T23:00"], "wind_speed_10m": [4.5, null, 3.0]},
         "daily": {"time": ["2026-11-05", "2026-11-06"], "wind_speed_10m_max": [10.0, null]}}
        """.utf8))
        let b = try base()
        let o = WindForecastModel.overlay(b, with: wind)
        XCTAssertEqual(o.hourly.wind_speed_10m, [4.5, 8.0, 9.0])          // null and absent hours keep best_match
        XCTAssertEqual(o.daily.wind_speed_10m_max, [10.0, 14.0])
        XCTAssertEqual(o.hourly.cloud_cover, b.hourly.cloud_cover)        // nothing but wind changes
        XCTAssertEqual(o.hourly.precipitation, b.hourly.precipitation)
        XCTAssertEqual(o.hourly.weather_code, b.hourly.weather_code)
        XCTAssertEqual(o.daily.weather_code, b.daily.weather_code)
        XCTAssertEqual(o.hourly.time, b.hourly.time)
    }

    func testOutsideTheModelDomainNothingChanges() throws {
        let empty = try JSONDecoder().decode(WindOnlyResponse.self, from: Data("""
        {"hourly": {"time": ["2026-11-05T20:00", "2026-11-05T21:00", "2026-11-05T22:00"], "wind_speed_10m": [null, null, null]},
         "daily": {"time": ["2026-11-05", "2026-11-06"], "wind_speed_10m_max": [null, null]}}
        """.utf8))
        let b = try base()
        let o = WindForecastModel.overlay(b, with: empty)
        XCTAssertEqual(o.hourly.wind_speed_10m, b.hourly.wind_speed_10m)
        XCTAssertEqual(o.daily.wind_speed_10m_max, b.daily.wind_speed_10m_max)
    }
}
