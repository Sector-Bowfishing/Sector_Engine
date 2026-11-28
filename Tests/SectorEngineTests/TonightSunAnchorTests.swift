//
//  TonightSunAnchorTests.swift
//
//  Tonight's sun times must be those of the LOCAL evening and morning, not of the UTC day of the
//  window start. No CoreLocation, so this runs on Linux CI as well as on device.
//

import XCTest
@testable import SectorEngine

final class TonightSunAnchorTests: XCTestCase {
    private func utc(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    /// 22:00 CST on Nov 28 is already Nov 29 in UTC. The sun must still be Nov 28's sunset and Nov 29's sunrise.
    func testEveningAfterTheUTCDateRolloverUsesTonightsSun() throws {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let now = utc("2026-11-29T04:00:00Z")
        let end = try XCTUnwrap(ConditionsForecastService.tonightWindowEnd(now: now, cal: cal))
        let start = try XCTUnwrap(cal.date(byAdding: .hour, value: -12, to: end))
        let sun = ConditionsForecastService.tonightSun(windowStart: start, windowEnd: end, cal: cal, lat: 34.0, lon: -86.0)

        // At 34 N, 86 W: sunset about 22:50Z on Nov 28, sunrise about 12:36Z on Nov 29.
        let sunset = try XCTUnwrap(sun.sunset)
        let sunrise = try XCTUnwrap(sun.sunrise)
        let dusk = try XCTUnwrap(sun.astronomicalDusk)
        XCTAssertEqual(sunset.timeIntervalSince(utc("2026-11-28T22:50:00Z")), 0, accuracy: 20 * 60, "sunset must be tonight's, not tomorrow's")
        XCTAssertEqual(sunrise.timeIntervalSince(utc("2026-11-29T12:36:00Z")), 0, accuracy: 20 * 60)
        XCTAssertGreaterThan(dusk, sunset)
        XCTAssertLessThan(sunset, start.addingTimeInterval(24 * 3600))
        XCTAssertTrue(start < dusk.addingTimeInterval(3 * 3600) && dusk < end, "full dark falls inside tonight's window")
    }

    /// In the daytime the window is the same one it always was.
    func testMiddayUsesTodaysSunsetAndTomorrowsSunrise() throws {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let now = utc("2026-11-28T18:00:00Z")   // noon CST
        let end = try XCTUnwrap(ConditionsForecastService.tonightWindowEnd(now: now, cal: cal))
        let start = try XCTUnwrap(cal.date(byAdding: .hour, value: -12, to: end))
        let sun = ConditionsForecastService.tonightSun(windowStart: start, windowEnd: end, cal: cal, lat: 34.0, lon: -86.0)
        XCTAssertEqual(try XCTUnwrap(sun.sunset).timeIntervalSince(utc("2026-11-28T22:50:00Z")), 0, accuracy: 20 * 60)
        XCTAssertEqual(try XCTUnwrap(sun.sunrise).timeIntervalSince(utc("2026-11-29T12:36:00Z")), 0, accuracy: 20 * 60)
    }
}
