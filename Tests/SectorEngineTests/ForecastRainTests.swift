import XCTest
@testable import SectorEngine
#if canImport(CoreLocation)
import CoreLocation
#endif

/// Forecast nights run clarity on THEIR OWN rain (Clarity Fusion Stage 1).
///
/// The bug: every future night copied tonight's input and overrode only the
/// Open-Meteo window (`rainLast48hIn`); `ClarityFactor` reads the MRMS
/// watershed total (`rainWatershed72hIn`) first, so whenever MRMS answered,
/// tonight's total stood in for every later night and forecast rain changed
/// nothing. 2" forecast for night +2 read 4.0 ft, as dry as tonight.
final class ForecastRainTests: XCTestCase {

    private static let lat = 34.35, lon = -86.30

    private static func base(now: Date, watershed72hIn: Double?) -> ConditionsInput {
        let sun = Astronomy.sunEvents(on: now, lat: lat, lon: lon)
        return ConditionsInput(
            date: now, latitude: lat, longitude: lon, region: .lowerMid,
            windMph: 2, windDirDeg: 180, airTempF: 75, cloudPct: 5, humidityPct: 60,
            pressureInHg: 30.0, pressureTrend: .steady, pressureChange12hInHg: 0, weatherCode: 0,
            cityGlowFactor: 0.2, waterTempF: 78, rainLast48hIn: 0, rainWatershed72hIn: watershed72hIn,
            sunset: sun.sunset, sunrise: sun.sunrise, civilDusk: sun.civilDusk,
            astronomicalDusk: sun.astronomicalDusk,
            moonIllumPct: Astronomy.moonIllumination(on: now) * 100, moonAltitudeAtWindow: 0.3,
            windowStart: sun.astronomicalDusk, windowEnd: sun.sunrise, hasTurbidityGage: false)
    }

    private static let dayFormat: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"; f.timeZone = .current; return f
    }()

    /// Day offset (-1…6, relative to `now`) → that day's forecast/archive
    /// precipitation_sum, inches. Local dates, with the local UTC offset, so
    /// buildNights' "today" is the test machine's today.
    private static func forecast(around now: Date, rain: [Int: Double] = [:]) -> ForecastResponse {
        let cal = Calendar.current
        let hf = DateFormatter(); hf.locale = Locale(identifier: "en_US_POSIX")
        hf.dateFormat = "yyyy-MM-dd'T'HH:mm"; hf.timeZone = .current
        var times: [String] = [], winds: [Double?] = [], clouds: [Double?] = [], precs: [Double?] = [], codes: [Int?] = []
        for h in -6...30 {
            guard let d = cal.date(byAdding: .hour, value: h, to: now) else { continue }
            times.append(hf.string(from: cal.date(bySetting: .minute, value: 0, of: d) ?? d))
            winds.append(2); clouds.append(0); precs.append(0); codes.append(0)
        }
        var days: [String] = [], dayRain: [Double?] = []
        for day in -1...6 {
            if let d = cal.date(byAdding: .day, value: day, to: now) {
                days.append(dayFormat.string(from: d)); dayRain.append(rain[day] ?? 0)
            }
        }
        let n = days.count
        var r = ForecastResponse(
            hourly: .init(time: times, wind_speed_10m: winds, cloud_cover: clouds, precipitation: precs, weather_code: codes),
            daily: .init(time: days, sunrise: days.map { $0 + "T06:00" }, sunset: days.map { $0 + "T20:00" },
                         wind_speed_10m_max: Array(repeating: 2, count: n), weather_code: Array(repeating: 0, count: n),
                         precipitation_sum: dayRain, cloud_cover_mean: Array(repeating: 0, count: n)))
        r.utc_offset_seconds = TimeZone.current.secondsFromGMT(for: now)
        return r
    }

    private static func dayKey(_ offset: Int, from now: Date) -> String {
        dayFormat.string(from: Calendar.current.date(byAdding: .day, value: offset, to: now)!)
    }

    private static func clarity(_ n: NightScore) -> Int {
        n.factors.first { $0.key == FactorKey.clarity.rawValue }?.sub ?? -1
    }

    @MainActor
    private func outlook(rain: [Int: Double], watershed: Double?, mrms: MrmsPrecip?,
                         now: Date = Date()) -> ConditionsForecast {
        let b = Self.base(now: now, watershed72hIn: watershed)
        return ConditionsForecastService.compute(
            r: Self.forecast(around: now, rain: rain), base: b,
            coordinate: CLLocationCoordinate2D(latitude: Self.lat, longitude: Self.lon),
            now: now, mrms: mrms)
    }

    private let dryMRMS = MrmsPrecip(watershed72hIn: 0, point72hIn: 0, daily: [], todayIn: 0, watershedByDay: [:])

    /// Dry tonight (MRMS answered 0.0"), 2.5" forecast for tomorrow: night +1
    /// must muddy. Before the fix it read exactly as dry as tonight.
    @MainActor
    func testDryTonightHeavyRainPlus24hMuddiesNightPlus1() {
        let dry = outlook(rain: [:], watershed: 0, mrms: dryMRMS)
        let wet = outlook(rain: [1: 2.5], watershed: 0, mrms: dryMRMS)
        guard dry.nights.count > 3, wet.nights.count > 3 else { return XCTFail("outlook too short") }
        XCTAssertLessThan(Self.clarity(wet.nights[1]), Self.clarity(dry.nights[1]),
                          "2.5\" forecast for tomorrow must lower tomorrow night's clarity with MRMS present")
        XCTAssertEqual(Self.clarity(wet.nights[0]), Self.clarity(dry.nights[0]),
                       "tonight's clarity must not change")
    }

    /// Dry tonight, 2.5" forecast for day +2: night +2 muddies, night +1 does not.
    @MainActor
    func testDryTonightHeavyRainPlus48hMuddiesNightPlus2Only() {
        let dry = outlook(rain: [:], watershed: 0, mrms: dryMRMS)
        let wet = outlook(rain: [2: 2.5], watershed: 0, mrms: dryMRMS)
        guard dry.nights.count > 4, wet.nights.count > 4 else { return XCTFail("outlook too short") }
        XCTAssertEqual(Self.clarity(wet.nights[1]), Self.clarity(dry.nights[1]), "night +1 is before the rain")
        XCTAssertLessThan(Self.clarity(wet.nights[2]), Self.clarity(dry.nights[2]), "night +2 has the rain")
        XCTAssertLessThan(Self.clarity(wet.nights[3]), Self.clarity(dry.nights[3]),
                          "the rain is still inside night +3's 72 h window")
        XCTAssertEqual(Self.clarity(wet.nights[5]), Self.clarity(dry.nights[5]),
                       "by night +5 the rain has left the window")
    }

    /// Tonight is the live gauge, rain or no rain in the forecast.
    @MainActor
    func testTonightStillEqualsTheGauge() {
        let now = Date()
        let b = Self.base(now: now, watershed72hIn: 0)
        let fc = outlook(rain: [1: 3.0, 2: 3.0], watershed: 0, mrms: dryMRMS, now: now)
        XCTAssertEqual(fc.nights.first?.score, ConditionsAggregator.evaluate(b).score)
    }

    /// Rain MRMS observed yesterday stays in night +1's window (days -1…+1)
    /// and has left night +2's (days 0…+2).
    @MainActor
    func testObservedRainYesterdayCarriesOneNightThenLeaves() {
        let now = Date()
        let wetYesterday = MrmsPrecip(watershed72hIn: 2.0, point72hIn: 2.0, daily: [], todayIn: 0,
                                      watershedByDay: [Self.dayKey(-1, from: now): 2.0])
        let fc = outlook(rain: [:], watershed: 2.0, mrms: wetYesterday, now: now)
        let dry = outlook(rain: [:], watershed: 0, mrms: dryMRMS, now: now)
        guard fc.nights.count > 3 else { return XCTFail("outlook too short") }
        XCTAssertLessThan(Self.clarity(fc.nights[1]), Self.clarity(dry.nights[1]),
                          "yesterday's observed rain is still in night +1's window")
        XCTAssertEqual(Self.clarity(fc.nights[2]), Self.clarity(dry.nights[2]),
                       "and has left night +2's")
    }

    /// No MRMS: the Open-Meteo window path, unchanged.
    @MainActor
    func testWithoutMRMSTheForecastWindowStillDrives() {
        let dry = outlook(rain: [:], watershed: nil, mrms: nil)
        let wet = outlook(rain: [2: 2.5], watershed: nil, mrms: nil)
        guard dry.nights.count > 2, wet.nights.count > 2 else { return XCTFail("outlook too short") }
        XCTAssertLessThan(Self.clarity(wet.nights[2]), Self.clarity(dry.nights[2]))
    }
}
