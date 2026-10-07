//
//  WaterTempStage2EReproTests.swift
//  SectorEngineTests
//
//  Stage 2E: the two production correctness defects, reproduced against the
//  pre-fix code. Written to FAIL before the fix and pass after it.
//

import XCTest
@testable import SectorEngine

final class WaterTempStage2EReproTests: XCTestCase {

    private let now = ISO8601DateFormatter().date(from: "2026-07-15T03:00:00Z")!   // 22:00 CDT Jul 14

    private func gauge(ageHours: Double) -> WaterLevelReading {
        WaterLevelReading(siteCode: "02171000", siteName: "LAKE MARION", parameterCode: "00010",
                          parameterName: "Temperature, water", value: 30.0, unit: "deg C",
                          dateTime: now.addingTimeInterval(-ageHours * 3600),
                          latitude: 33.5, longitude: -80.4, trend: .steady, change: 0)
    }

    /// Defect 1 — shown ≠ scored. A 10-hour-old lake reading (inside the
    /// sensor's 72 h window, outside the builder's 6 h window) is SHOWN as the
    /// gauge while the score runs on the model.
    func testIntermediateAgeMeasurementIsShownAndScoredTheSame() throws {
        let model = WaterTempModel(currentF: 80.0, series: [])
        let g = gauge(ageHours: 10)
        let input = ConditionsInputBuilder.build(
            coordinate: .init(latitude: 33.5, longitude: -80.4), date: now,
            weather: nil, water: nil, discharge: nil,
            waterTempC: g, modeledWaterTempF: model.currentF, turbidity: nil)
        // Post-fix path: the response's DTO is built from the one resolved state.
        let shown = try XCTUnwrap(SectorEngineAPI.waterTempDTO(
            state: WaterTemperatureResolver.resolve(measurement: g, model: model, at: now)))
        XCTAssertEqual(shown.valueF, try XCTUnwrap(input.waterTempF), accuracy: 0.001,
                       "shown \(shown.source) \(shown.valueF) but scored \(input.waterTempF ?? .nan)")
    }

    /// Defect 2 — UTC "today". At 23:30 CDT on Oct 7 it is already Oct 8 in UTC
    /// (Cloud Run's zone). The model's current day must be the LAKE's Oct 7.
    /// Run with TZ=UTC to reproduce the server.
    func testLakeEveningAfterUTCRolloverStaysOnLakeToday() throws {
        let days = ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"]
        let series = days.enumerated().map { i, d in
            WaterTempDay(date: WaterTemperatureService.parseDay(d)!, waterF: 70 + Double(i), airF: 60)
        }
        let lakeEvening = ISO8601DateFormatter().date(from: "2026-10-08T04:30:00Z")!  // 23:30 CDT Oct 7
        let current = try XCTUnwrap(WaterTemperatureService.currentDay(
            in: series, now: lakeEvening, lakeTimeZone: TimeZone(identifier: "America/Chicago")))
        XCTAssertEqual(current.waterF, 71, "picked \(current.waterF) — Oct 7 is 71, Oct 8 is 72")
    }
}
