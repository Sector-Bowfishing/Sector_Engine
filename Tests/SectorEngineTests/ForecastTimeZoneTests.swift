//
//  ForecastTimeZoneTests.swift
//  SectorEngineTests
//
//  Open-Meteo answers `timezone=auto` requests in the LAKE's local wall clock.
//  The engine used to read those strings in the server's zone (UTC on Cloud
//  Run), shifting every hourly sample by the lake's offset: the Tonight window
//  ran 1 PM–1 AM CDT, fog and gusts were scored on the wrong hours, and the
//  headline was formatted in UTC. These tests pin lakes to fixed zones and
//  instants so they fail the same way on a laptop and on a UTC server.
//

import XCTest
#if canImport(CoreLocation)
import CoreLocation
#endif
@testable import SectorEngine

final class ForecastTimeZoneTests: XCTestCase {

    private static let cdt = -5 * 3600   // Central daylight
    private static let pdt = -7 * 3600   // Pacific daylight

    private static func utc(_ s: String) -> Date { ISODate.parse(s)! }

    private static func localHour(_ d: Date, offset: Int) -> Int {
        OpenMeteoTime.calendar(utcOffsetSeconds: offset).component(.hour, from: d)
    }

    private static func localDay(_ d: Date, offset: Int) -> String {
        OpenMeteoTime.localDay(d, utcOffsetSeconds: offset)
    }

    /// An hourly + daily response written in the lake's local clock, the way
    /// Open-Meteo sends it.
    /// `wind`/`gust` take the LOCAL hour, so a sample read in the wrong zone
    /// carries a visibly wrong value instead of passing on a flat series.
    private static func response(localStart: String, hours: Int, days: [String], offset: Int,
                                 wind: (Int) -> Double = { _ in 2 },
                                 gust: ((Int) -> Double)? = nil) -> ForecastResponse {
        let cal = OpenMeteoTime.calendar(utcOffsetSeconds: offset)
        let start = OpenMeteoTime.instant(localStart, utcOffsetSeconds: offset)!
        var times: [String] = []
        var winds: [Double?] = []
        var gusts: [Double?] = []
        for h in 0..<hours {
            let d = start.addingTimeInterval(Double(h) * 3600)
            let c = cal.dateComponents([.year, .month, .day, .hour], from: d)
            times.append(String(format: "%04d-%02d-%02dT%02d:00", c.year!, c.month!, c.day!, c.hour!))
            winds.append(wind(c.hour!))
            gusts.append(gust.map { $0(c.hour!) })
        }
        let n = days.count
        let hourly = ForecastResponse.Hourly(time: times,
                                             wind_speed_10m: winds,
                                             cloud_cover: Array(repeating: 0, count: hours),
                                             precipitation: Array(repeating: 0, count: hours),
                                             weather_code: Array(repeating: 0, count: hours),
                                             wind_gusts_10m: gust == nil ? nil : gusts)
        let daily = ForecastResponse.Daily(time: days,
                                           sunrise: days.map { $0 + "T06:30" }, sunset: days.map { $0 + "T19:00" },
                                           wind_speed_10m_max: Array(repeating: 2, count: n),
                                           weather_code: Array(repeating: 0, count: n),
                                           precipitation_sum: Array(repeating: 0, count: n),
                                           cloud_cover_mean: Array(repeating: 0, count: n))
        return ForecastResponse(hourly: hourly, daily: daily, utc_offset_seconds: offset)
    }

    private static func base(lat: Double, lon: Double, now: Date, offset: Int? = nil,
                             alertWindFloorMph: Double? = nil,
                             severeWarningLabel: String? = nil) -> ConditionsInput {
        ConditionsInputBuilder.build(
            coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon), date: now,
            weather: offset.map { weather(at: now, offset: $0) },
            water: nil, discharge: nil, waterTempC: nil,
            modeledWaterTempF: 75, turbidity: nil,
            alertWindFloorMph: alertWindFloorMph, severeWarningLabel: severeWarningLabel)
    }

    /// A calm, clear live reading carrying the lake's offset, as WeatherService
    /// produces it.
    private static func weather(at now: Date, offset: Int) -> WeatherReading {
        WeatherReading(temperature: 75, conditionDescription: "Clear", conditionSymbol: "moon.stars",
                       windSpeed: 3, windDirection: 180, precipitation: 0, recentRainfall: 0,
                       humidity: 60, pressure: 1016, pressureTrend: .steady, pressureChange: 0,
                       cloudCover: 0, weatherCode: 0, time: now, utcOffsetSeconds: offset)
    }

    // MARK: - Tonight window

    func testCentralLakeTonightRunsSixPMToSixAMLocal() {
        let offset = Self.cdt
        let now = Self.utc("2026-09-15T01:00:00Z")          // 8 PM CDT, Sep 14
        let lat = 34.35, lon = -86.30                      // Guntersville
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 96,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset)
        let fc = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now),
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        let tonight = try! XCTUnwrap(fc.tonight)

        XCTAssertEqual(tonight.displayStart, Self.utc("2026-09-14T23:00:00Z"), "display starts 6 PM CDT")
        XCTAssertEqual(tonight.displayEnd, Self.utc("2026-09-15T11:00:00Z"), "display ends 6 AM CDT")
        XCTAssertTrue(tonight.hours.allSatisfy { $0.date >= tonight.displayStart && $0.date <= tonight.displayEnd })
        XCTAssertTrue(tonight.hours.allSatisfy { [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6]
            .contains(Self.localHour($0.date, offset: offset)) }, "every point is a night hour at the lake")

        // Real sun times for mid-September in north Alabama.
        let sunset = try! XCTUnwrap(tonight.sunset)
        let sunrise = try! XCTUnwrap(tonight.sunrise)
        XCTAssertEqual(Self.localDay(sunset, offset: offset), "2026-09-14", "tonight's sunset, not tomorrow's")
        XCTAssertTrue((18...19).contains(Self.localHour(sunset, offset: offset)))
        XCTAssertEqual(Self.localDay(sunrise, offset: offset), "2026-09-15")
        XCTAssertTrue((6...7).contains(Self.localHour(sunrise, offset: offset)))

        if tonight.headline.hasPrefix("Peak "), !tonight.headline.contains("on now"), let peak = tonight.peak {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.dateFormat = "h:mm a"
            f.timeZone = OpenMeteoTime.zone(utcOffsetSeconds: offset)
            XCTAssertEqual(tonight.headline, "Peak \(f.string(from: peak))", "headline in the lake's clock")
        }
    }

    func testPacificLakeGetsTonightsSunsetNotTomorrows() {
        // 6 PM Pacific is already tomorrow in UTC; Astronomy keys its day on the UTC
        // date, so a naive lookup would return tomorrow's sunset.
        let offset = Self.pdt
        let now = Self.utc("2026-09-15T02:00:00Z")          // 7 PM PDT, Sep 14
        let lat = 39.05, lon = -122.80                     // Clear Lake, CA
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 96,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset)
        let fc = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now),
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        let tonight = try! XCTUnwrap(fc.tonight)
        XCTAssertEqual(tonight.displayEnd, Self.utc("2026-09-15T13:00:00Z"), "ends 6 AM PDT")
        let sunset = try! XCTUnwrap(tonight.sunset)
        XCTAssertEqual(Self.localDay(sunset, offset: offset), "2026-09-14")
        XCTAssertTrue((18...19).contains(Self.localHour(sunset, offset: offset)))
    }

    func testAfterMidnightStillShowsTheCurrentNight() {
        // 2 AM CDT is 07:00Z — past 06:00Z. The UTC-based math jumped "tonight" to
        // the NEXT evening while the user was still on the water.
        let offset = Self.cdt
        let now = Self.utc("2026-09-15T07:00:00Z")          // 2 AM CDT, Sep 15
        let lat = 34.35, lon = -86.30
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 96,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset)
        let fc = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now),
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        let tonight = try! XCTUnwrap(fc.tonight)
        XCTAssertEqual(tonight.displayEnd, Self.utc("2026-09-15T11:00:00Z"), "still ends at THIS morning's 6 AM")
    }

    func testNightDatesAreLocalNoonAndLabelTheRightDayOnAnyUSPhone() {
        let offset = Self.pdt
        let now = Self.utc("2026-09-15T03:00:00Z")          // 8 PM PDT, Sep 14
        let lat = 39.05, lon = -122.80                     // Clear Lake, CA
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 96,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset)
        let fc = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now, offset: offset),
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        XCTAssertEqual(fc.nights.count, 7)
        let first = try! XCTUnwrap(fc.nights.first)
        XCTAssertEqual(first.date, Self.utc("2026-09-14T19:00:00Z"), "tonight = noon PDT on Sep 14")
        XCTAssertTrue(fc.nights.allSatisfy { Self.localHour($0.date, offset: offset) == 12 })

        // Apps label a night by the PHONE's calendar day. A 9 PM Pacific instant is
        // already tomorrow in New York; noon is the same day from Hawaii to Maine.
        let expected = (14...20).map { String(format: "2026-09-%02d", $0) }
        for zone in ["America/New_York", "America/Chicago", "America/Los_Angeles", "Pacific/Honolulu"] {
            var phone = Calendar(identifier: .gregorian)
            phone.timeZone = TimeZone(identifier: zone)!
            let labels = fc.nights.map { d -> String in
                let c = phone.dateComponents([.year, .month, .day], from: d.date)
                return String(format: "%04d-%02d-%02d", c.year!, c.month!, c.day!)
            }
            XCTAssertEqual(labels, expected, "night day labels on a phone in \(zone)")
        }

        // Ribbon points still run 8 PM → 5 AM at the lake.
        let ribbonHours = first.hourly.map { Self.localHour($0.hour, offset: offset) }
        XCTAssertEqual(ribbonHours, [20, 21, 22, 23, 0, 1, 2, 3, 4, 5])
    }

    func testFutureNightWeatherIsReadFromThatNightsLocalHours() {
        // Wind equals the lake's local hour. Night hours 18:00→06:00 average
        // 144/13; the same samples read five hours off would average very
        // differently, which a flat fixture could never reveal.
        let offset = Self.cdt
        let now = Self.utc("2026-09-14T17:00:00Z")          // noon CDT
        let lat = 34.35, lon = -86.30
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 24 * 9,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset,
                              wind: { Double($0) })
        let fc = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now, offset: offset),
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        XCTAssertEqual(fc.nights.count, 7)
        XCTAssertEqual(fc.nights[1].windMax, 144.0 / 13.0, accuracy: 0.001)
        XCTAssertEqual(fc.nights[3].windMax, 144.0 / 13.0, accuracy: 0.001)
        // Tonight's ribbon hours carry their own local-hour wind.
        let ribbon = fc.nights[1].hourly
        XCTAssertEqual(ribbon.map(\.windMph), [20, 21, 22, 23, 0, 1, 2, 3, 4, 5])
    }

    // MARK: - The gauge scores the night in progress

    func testEveningGaugeScoresTonightNotTomorrowNight() {
        // 8 PM CDT is 01:00Z tomorrow. Astronomy keyed on that UTC day handed the
        // gauge TOMORROW night's dusk, moon and fishing window.
        let offset = Self.cdt
        let now = Self.utc("2026-09-15T01:00:00Z")          // 8 PM CDT, Sep 14
        let base = Self.base(lat: 34.35, lon: -86.30, now: now, offset: offset)
        let dusk = try! XCTUnwrap(base.astronomicalDusk)
        let start = try! XCTUnwrap(base.windowStart)
        let end = try! XCTUnwrap(base.windowEnd)
        XCTAssertEqual(Self.localDay(dusk, offset: offset), "2026-09-14", "tonight's dusk")
        XCTAssertEqual(Self.localDay(start, offset: offset), "2026-09-14")
        XCTAssertEqual(Self.localDay(end, offset: offset), "2026-09-15", "window ends tomorrow morning")
        XCTAssertTrue((6...7).contains(Self.localHour(end, offset: offset)))
        XCTAssertLessThan(start.timeIntervalSince(now), 3 * 3600, "the window is hours away, not a day")
    }

    func testAfterMidnightGaugeAndNights0AreTheNightStillUnderway() {
        let offset = Self.cdt
        let now = Self.utc("2026-09-15T07:00:00Z")          // 2 AM CDT, Sep 15
        let lat = 34.35, lon = -86.30
        let base = Self.base(lat: lat, lon: lon, now: now, offset: offset)
        let start = try! XCTUnwrap(base.windowStart)
        let end = try! XCTUnwrap(base.windowEnd)
        XCTAssertTrue(start <= now && now <= end, "2 AM sits inside the gauge's window")
        XCTAssertEqual(Self.localDay(start, offset: offset), "2026-09-14")

        let r = Self.response(localStart: "2026-09-13T00:00", hours: 24 * 9,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset)
        let fc = ConditionsForecastService.compute(r: r, base: base,
                                                   coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                   now: now)
        XCTAssertEqual(Self.localDay(try! XCTUnwrap(fc.nights.first).date, offset: offset), "2026-09-14",
                       "nights[0] is the same night the gauge and the Tonight chart show")

        // At 7 AM the night is over and "tonight" is this evening.
        let morning = Self.utc("2026-09-15T12:00:00Z")      // 7 AM CDT
        let fcMorning = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: morning, offset: offset),
                                                          coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon),
                                                          now: morning)
        XCTAssertEqual(Self.localDay(try! XCTUnwrap(fcMorning.nights.first).date, offset: offset), "2026-09-15")
    }

    func testLiveWarningCapsTonightButNotFutureNights() {
        let offset = Self.cdt
        let now = Self.utc("2026-09-15T01:00:00Z")          // 8 PM CDT
        let lat = 34.35, lon = -86.30
        let coord = CLLocationCoordinate2D(latitude: lat, longitude: lon)
        let r = Self.response(localStart: "2026-09-13T00:00", hours: 24 * 9,
                              days: (13...21).map { String(format: "2026-09-%02d", $0) }, offset: offset,
                              gust: { _ in 6 })
        let calm = ConditionsForecastService.compute(r: r, base: Self.base(lat: lat, lon: lon, now: now, offset: offset),
                                                     coordinate: coord, now: now)
        let warned = ConditionsForecastService.compute(
            r: r, base: Self.base(lat: lat, lon: lon, now: now, offset: offset,
                                  alertWindFloorMph: 45, severeWarningLabel: "Severe Thunderstorm Warning"),
            coordinate: coord, now: now)

        XCTAssertEqual(calm.nights.count, 7)
        XCTAssertLessThan(warned.nights[0].score, calm.nights[0].score, "the warning caps tonight")
        XCTAssertEqual(warned.nights.dropFirst().map(\.score), calm.nights.dropFirst().map(\.score),
                       "a warning in effect now says nothing about the rest of the week")
    }

    // MARK: - Weather reading

    func testWeatherReadingTimesAreRealInstantsAndRainUsesLocalDays() throws {
        // 8 PM CDT on Sep 14 = 01:00Z Sep 15 — UTC has rolled to "tomorrow".
        let offset = Self.cdt
        var hourlyTimes: [String] = []
        var pressures: [String] = []
        let cal = OpenMeteoTime.calendar(utcOffsetSeconds: offset)
        let start = OpenMeteoTime.instant("2026-09-13T00:00", utcOffsetSeconds: offset)!
        for h in 0..<72 {
            let c = cal.dateComponents([.year, .month, .day, .hour], from: start.addingTimeInterval(Double(h) * 3600))
            hourlyTimes.append("\"" + String(format: "%04d-%02d-%02dT%02d:00", c.year!, c.month!, c.day!, c.hour!) + "\"")
            pressures.append("1015.0")
        }
        let json = """
        {"utc_offset_seconds": \(offset),
         "current": {"time": "2026-09-14T20:00", "temperature_2m": 78, "relative_humidity_2m": 60,
                     "precipitation": 0, "weather_code": 0, "cloud_cover": 10, "pressure_msl": 1015,
                     "wind_speed_10m": 5, "wind_direction_10m": 180},
         "hourly": {"time": [\(hourlyTimes.joined(separator: ","))],
                    "pressure_msl": [\(pressures.joined(separator: ","))]},
         "daily": {"time": ["2026-09-12","2026-09-13","2026-09-14","2026-09-15"],
                   "precipitation_sum": [8.0, 0.25, 0.5, 4.0]}}
        """
        let reading = try WeatherService.reading(from: Data(json.utf8))

        XCTAssertEqual(reading.time, Self.utc("2026-09-15T01:00:00Z"), "current time is 8 PM CDT as a real instant")
        XCTAssertEqual(reading.recentRainfall, 0.75, accuracy: 0.0001,
                       "today (Sep 14) + yesterday (Sep 13) at the lake — not tomorrow's forecast (4.0) or Sep 12 (8.0)")
        let first = try XCTUnwrap(reading.pressureHistory.first?.date)
        XCTAssertEqual(Self.localHour(first, offset: offset) , 0, "hourly samples land on local hours")
    }

    func testOpenMeteoTimeParsesLocalWallClock() {
        XCTAssertEqual(OpenMeteoTime.instant("2026-09-14T21:00", utcOffsetSeconds: Self.cdt),
                       Self.utc("2026-09-15T02:00:00Z"))
        XCTAssertEqual(OpenMeteoTime.instant("2026-09-14", utcOffsetSeconds: 0),
                       Self.utc("2026-09-14T00:00:00Z"))
        XCTAssertNil(OpenMeteoTime.instant("garbage", utcOffsetSeconds: 0))
        XCTAssertEqual(OpenMeteoTime.localDay(Self.utc("2026-09-15T01:00:00Z"), utcOffsetSeconds: Self.cdt), "2026-09-14")
    }
}
