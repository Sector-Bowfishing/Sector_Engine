//
//  NWSWeatherServiceTests.swift
//  SectorEngineTests
//
//  NWS/NBM weather adapter (Sector_Ops #53). Fixtures/NWS holds real
//  api.weather.gov responses recorded 2026-11-06 ~20:51Z with plain GETs for
//  Guntersville (34.42,-86.26), Havasu (34.45,-114.35) and Champlain
//  (44.47,-73.3): points, stations, the three nearest stations' observations
//  (start = now − 50 h) and forecastGridData. Each is trimmed to the fields the
//  adapter reads; values are untouched. icons.json is GET /icons.
//

import XCTest
@testable import SectorEngine

final class NWSWeatherServiceTests: XCTestCase {

    // MARK: Fixtures

    private static let dir = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().appendingPathComponent("Fixtures/NWS")

    private static func data(_ name: String) throws -> Data {
        try Data(contentsOf: dir.appendingPathComponent(name + ".json"))
    }

    private static func date(_ s: String) -> Date { NWSWeatherService.parseDate(s)! }

    /// Recording time.
    private static let recordedAt = date("2026-11-06T20:51:00Z")

    private func reading(_ lake: String, now: Date = recordedAt) throws -> NWSWeatherReading? {
        let point = try XCTUnwrap(NWSWeatherService.decodePoint(try Self.data("\(lake)-points")))
        let stations = Array(NWSWeatherService.decodeStations(try Self.data("\(lake)-stations")).prefix(3))
        var obs: [String: [NWSObservation]] = [:]
        for s in stations { obs[s] = NWSWeatherService.decodeObservations(try Self.data("\(lake)-obs-\(s)")) }
        let grid = NWSWeatherService.decodeGrid(try Self.data("\(lake)-grid"))
        XCTAssertNotNil(grid)
        return NWSWeatherService.assemble(point: point, stations: stations, observations: obs,
                                          grid: grid, now: now)
    }

    /// The codes WeatherService can emit (condition(forCode:) has a real label).
    private static let openMeteoCodes: Set<Int> = Set((0...99).filter {
        WeatherService.condition(forCode: $0).description != "—"
    })

    // MARK: Decoding

    func testDecodesPointsAndStationsInNearestFirstOrder() throws {
        let p = try XCTUnwrap(NWSWeatherService.decodePoint(try Self.data("guntersville-points")))
        XCTAssertEqual(p.gridId, "HUN"); XCTAssertEqual(p.gridX, 76); XCTAssertEqual(p.gridY, 30)
        XCTAssertEqual(p.forecastGridData, "https://api.weather.gov/gridpoints/HUN/76,30")
        XCTAssertEqual(Array(NWSWeatherService.decodeStations(try Self.data("guntersville-stations")).prefix(3)),
                       ["K8A1", "KBFZ", "K4A6"])
        XCTAssertNil(NWSWeatherService.decodePoint(Data("{\"status\":404}".utf8)))
    }

    func testObservationsAreNewestFirstInBuild28Units() throws {
        let obs = NWSWeatherService.decodeObservations(try Self.data("champlain-obs-KBTV"))
        XCTAssertEqual(obs.count, 245)
        XCTAssertEqual(obs, obs.sorted { $0.timestamp > $1.timestamp })
        let o = obs[0]
        XCTAssertEqual(o.stationId, "KBTV")
        XCTAssertEqual(o.timestamp, Self.date("2026-11-06T20:30:00Z"))
        XCTAssertEqual(try XCTUnwrap(o.temperatureF), 62.6, accuracy: 1e-9)        // 17 °C
        XCTAssertEqual(try XCTUnwrap(o.windMph), 9.2162, accuracy: 1e-3)           // 14.832 km/h
        XCTAssertEqual(try XCTUnwrap(o.altimeterHPa), 1010.4984, accuracy: 1e-9)   // 101049.84 Pa
        XCTAssertNil(o.seaLevelHPa)                                                // not yet filled by the API
        XCTAssertEqual(o.layerCoverPct, 43.75)                                     // FEW + SCT
        XCTAssertEqual(NWSWeatherService.decodeObservations(try Self.data("guntersville-obs-K8A1")), [])
    }

    func testGridLayersExpandToHourlyValues() throws {
        let g = try XCTUnwrap(NWSWeatherService.decodeGrid(try Self.data("guntersville-grid")))
        // windSpeed 2026-11-06T14:00/PT2H = 3.704 km/h covers 14Z and 15Z.
        XCTAssertEqual(try XCTUnwrap(g.windMph[Self.date("2026-11-06T14:00:00Z")]), 2.3016, accuracy: 1e-3)
        XCTAssertEqual(g.windMph[Self.date("2026-11-06T14:00:00Z")], g.windMph[Self.date("2026-11-06T15:00:00Z")])
        XCTAssertEqual(try XCTUnwrap(g.temperatureF[Self.date("2026-11-06T15:00:00Z")]), 59, accuracy: 1e-9)
        XCTAssertEqual(g.skyCover[Self.date("2026-11-06T14:00:00Z")], 29)
        // QPF here comes in 4–6 h periods: never split into an invented hourly rate.
        XCTAssertTrue(g.precipIn.isEmpty)
    }

    // MARK: Units

    func testUnitConversions() {
        typealias S = NWSWeatherService
        XCTAssertEqual(S.convert(22, unitCode: "wmoUnit:degC", to: .fahrenheit)!, 71.6, accuracy: 1e-9)
        XCTAssertEqual(S.convert(-40, unitCode: "wmoUnit:degC", to: .fahrenheit)!, -40, accuracy: 1e-9)
        XCTAssertEqual(S.convert(16.09344, unitCode: "wmoUnit:km_h-1", to: .mph)!, 10, accuracy: 1e-9)
        XCTAssertEqual(S.convert(10, unitCode: "wmoUnit:m_s-1", to: .mph)!, 22.3694, accuracy: 1e-4)
        XCTAssertEqual(S.convert(101591.66, unitCode: "wmoUnit:Pa", to: .hPa)!, 1015.9166, accuracy: 1e-9)
        XCTAssertEqual(S.convert(25.4, unitCode: "wmoUnit:mm", to: .inches)!, 1, accuracy: 1e-12)
        XCTAssertEqual(S.convert(270, unitCode: "wmoUnit:degree_(angle)", to: .degrees), 270)
        XCTAssertEqual(S.convert(55, unitCode: "wmoUnit:percent", to: .percent), 55)
        // Unknown or mismatched unit: nil, never a guess.
        XCTAssertNil(S.convert(10, unitCode: nil, to: .mph))
        XCTAssertNil(S.convert(10, unitCode: "wmoUnit:degC", to: .mph))
        XCTAssertNil(S.convert(10, unitCode: "wmoUnit:furlong", to: .inches))
        // QC-rejected values are dropped.
        XCTAssertNil(S.convert(S.Quantity(unitCode: "wmoUnit:degC", value: 20, qualityControl: "X"), to: .fahrenheit))
        XCTAssertNil(S.convert(S.Quantity(unitCode: "wmoUnit:degC", value: nil, qualityControl: "Z"), to: .fahrenheit))
        XCTAssertEqual(S.convert(S.Quantity(unitCode: "wmoUnit:degC", value: 20, qualityControl: "V"), to: .fahrenheit), 68)
    }

    func testValidTimeDurations() {
        let t = Self.date("2026-11-06T14:00:00Z")
        XCTAssertEqual(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/PT1H")?.1, 1)
        XCTAssertEqual(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/PT6H")?.1, 6)
        XCTAssertEqual(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/P1D")?.1, 24)
        XCTAssertEqual(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/P7DT11H")?.1, 179)
        XCTAssertEqual(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/PT1H")?.0, t)
        XCTAssertNil(NWSWeatherService.parseValidTime("2026-11-06T14:00:00+00:00/PT30M"))
        XCTAssertNil(NWSWeatherService.parseValidTime("garbage"))
    }

    func testUserAgentIsTheAlertsServiceOne() {
        XCTAssertEqual(NWSWeatherService.userAgent, "Sector/1.0 (io.sector.co)")
    }

    // MARK: Icon / text → WMO / SF Symbol

    func testIconSetIsTheWholeNWSIconList() throws {
        struct R: Decodable { let icons: [String: [String: String]] }
        let recorded = try JSONDecoder().decode(R.self, from: try Self.data("icons")).icons.keys
        XCTAssertEqual(Set(recorded), Set(NWSCondition.iconSet))
        XCTAssertEqual(NWSCondition.iconSet.count, 34)
    }

    /// Exhaustive: every NWS icon, no intensity word in the text.
    func testEveryIconMapsToAnOpenMeteoCode() {
        let expected: [String: Int?] = [
            "skc": 0, "few": 1, "sct": 2, "bkn": 2, "ovc": 3,
            "wind_skc": 0, "wind_few": 1, "wind_sct": 2, "wind_bkn": 2, "wind_ovc": 3,
            "snow": 73, "rain_snow": 73, "rain_sleet": 66, "snow_sleet": 73,
            "fzra": 66, "rain_fzra": 66, "snow_fzra": 66, "sleet": 66,
            "rain": 63, "rain_showers": 81, "rain_showers_hi": 81,
            "tsra": 95, "tsra_sct": 95, "tsra_hi": 95,
            "tornado": 95, "hurricane": 95, "tropical_storm": 95,
            "dust": nil, "smoke": nil, "haze": nil, "hot": nil, "cold": nil,
            "blizzard": 75, "fog": 45,
        ]
        XCTAssertEqual(Set(expected.keys), Set(NWSCondition.iconSet))
        for icon in NWSCondition.iconSet {
            for tod in ["day", "night"] {
                let url = "https://api.weather.gov/icons/land/\(tod)/\(icon)?size=medium"
                let code = NWSCondition.weatherCode(icon: url, text: nil, skyCoverPct: nil)
                XCTAssertEqual(code, expected[icon]!, "\(icon) \(tod)")
                if let code {
                    XCTAssertTrue(Self.openMeteoCodes.contains(code), "\(icon) → \(code) outside Open-Meteo set")
                }
                // With total cloud known, every icon yields a code in the set.
                let withSky = NWSCondition.weatherCode(icon: url, text: nil, skyCoverPct: 50)
                XCTAssertTrue(Self.openMeteoCodes.contains(withSky ?? -1), icon)
            }
        }
    }

    func testSymbolsAndLabelsAreWeatherServiceVocabulary_NoNightVariant() {
        // WeatherService has no day/night symbol rule; neither does the adapter.
        for tod in ["day", "night"] {
            let code = NWSCondition.weatherCode(icon: "https://api.weather.gov/icons/land/\(tod)/skc", text: "Clear", skyCoverPct: nil)!
            XCTAssertEqual(WeatherService.condition(forCode: code).symbol, "sun.max.fill")
        }
        XCTAssertEqual(WeatherService.condition(forCode: 45).symbol, "cloud.fog.fill")
        XCTAssertEqual(WeatherService.condition(forCode: 95).symbol, "cloud.bolt.fill")
    }

    func testIntensityDrizzleAndHailRefineTheIcon() {
        func c(_ icon: String, _ text: String) -> Int? {
            NWSCondition.weatherCode(icon: "https://api.weather.gov/icons/land/day/\(icon)?size=medium", text: text, skyCoverPct: 10)
        }
        XCTAssertEqual(c("rain", "Light Rain"), 61)
        XCTAssertEqual(c("rain", "Rain"), 63)
        XCTAssertEqual(c("rain", "Heavy Rain and Fog/Mist"), 65)
        XCTAssertEqual(c("rain", "Light Rain and Fog/Mist"), 61)
        XCTAssertEqual(c("rain", "Light Drizzle"), 51)
        XCTAssertEqual(c("rain", "Drizzle"), 53)
        XCTAssertEqual(c("rain", "Light Freezing Drizzle"), 56)
        XCTAssertEqual(c("rain_showers", "Heavy Rain Showers"), 82)
        XCTAssertEqual(c("snow", "Light Snow"), 71)
        XCTAssertEqual(c("snow", "Snow Showers"), 85)
        XCTAssertEqual(c("fzra", "Heavy Freezing Rain"), 67)
        XCTAssertEqual(c("tsra", "Thunderstorms and Rain with Hail"), 96)
        XCTAssertEqual(c("fog", "Fog/Mist"), 45)
        // A sky icon with total cloud known: the cover decides.
        XCTAssertEqual(NWSCondition.weatherCode(icon: "https://api.weather.gov/icons/land/day/skc", text: "Clear", skyCoverPct: 92), 3)
        // "Unknown Precipitation" under an ovc icon stays a sky code.
        XCTAssertEqual(NWSCondition.weatherCode(icon: "https://api.weather.gov/icons/land/day/ovc", text: "Light Unknown Precipitation", skyCoverPct: nil), 3)
    }

    func testTextOnlyObservations() {
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Light Rain", skyCoverPct: nil), 61)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Thunderstorm", skyCoverPct: nil), 95)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Fog", skyCoverPct: nil), 45)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Mostly Cloudy", skyCoverPct: nil), 2)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Cloudy", skyCoverPct: nil), 3)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Clear", skyCoverPct: nil), 0)
        XCTAssertEqual(NWSCondition.weatherCode(icon: nil, text: "Clear", skyCoverPct: 40), 2)
        XCTAssertNil(NWSCondition.weatherCode(icon: nil, text: nil, skyCoverPct: nil))
        XCTAssertNil(NWSCondition.weatherCode(icon: "", text: "Haze", skyCoverPct: nil))
    }

    func testSkyCoverThresholdsAreNWSOctas() {
        XCTAssertEqual(NWSCondition.skyCode(percent: 0), 0)
        XCTAssertEqual(NWSCondition.skyCode(percent: 12.4), 0)
        XCTAssertEqual(NWSCondition.skyCode(percent: 12.5), 1)
        XCTAssertEqual(NWSCondition.skyCode(percent: 37.5), 2)
        XCTAssertEqual(NWSCondition.skyCode(percent: 87.4), 2)
        XCTAssertEqual(NWSCondition.skyCode(percent: 87.5), 3)
        XCTAssertEqual(NWSCondition.skyCode(percent: 100), 3)
    }

    func testIconNameParsing() {
        XCTAssertEqual(NWSCondition.iconName("https://api.weather.gov/icons/land/night/rain,40/tsra,60?size=medium"), "rain")
        XCTAssertEqual(NWSCondition.iconName("https://api.weather.gov/icons/land/day/wind_skc?size=medium"), "wind_skc")
        XCTAssertNil(NWSCondition.iconName(nil))
        XCTAssertNil(NWSCondition.iconName("https://example.com/whatever"))
    }

    // MARK: Recorded points

    func testChamplainFreshObservation() throws {
        let r = try XCTUnwrap(try reading("champlain"))
        XCTAssertEqual(r.gridpoint, "BTV/86,56")
        let t = try XCTUnwrap(r.temperature)
        XCTAssertEqual(t.value, 62.6, accuracy: 1e-9)
        XCTAssertEqual(t.origin, .observation); XCTAssertEqual(t.stationId, "KBTV")
        XCTAssertEqual(t.observedAt, Self.date("2026-11-06T20:30:00Z"))
        XCTAssertEqual(r.humidity?.value, 59)
        XCTAssertEqual(try XCTUnwrap(r.windSpeed?.value), 9.216, accuracy: 1e-3)
        XCTAssertEqual(r.windDirection?.value, 320)
        XCTAssertEqual(r.windDirection?.observedAt, r.windSpeed?.observedAt)
        // Pressure: altimeter 1010.4984 + KBTV's own SLP − altimeter offset at 17:54Z.
        XCTAssertEqual(r.pressureKind, .seaLevel)
        XCTAssertEqual(try XCTUnwrap(r.seaLevelOffset), -0.1, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(r.pressure?.value), 1010.3984, accuracy: 1e-6)
        XCTAssertEqual(r.pressureTrend, .steady)
        XCTAssertEqual(try XCTUnwrap(r.pressureChange), -0.7016, accuracy: 1e-4)
        XCTAssertEqual(r.pressureTrend3h, .falling)
        // Sky: cover from the NBM hour, code from it (obs icon is a sky icon).
        XCTAssertEqual(r.cloudCover?.value, 48)
        XCTAssertEqual(r.cloudCover?.origin, .nbmGrid)
        XCTAssertEqual(r.cloudCover?.observedAt, Self.date("2026-11-06T20:00:00Z"))
        XCTAssertEqual(r.weatherCode?.value, 2)
        XCTAssertEqual(r.conditionSymbol, "cloud.sun.fill")
        XCTAssertEqual(r.conditionDescription, "Partly cloudy")
        XCTAssertEqual(r.nwsTextDescription, "Partly Cloudy")
    }

    func testHavasuSkipsTheStaleNearestStation() throws {
        let r = try XCTUnwrap(try reading("havasu"))
        // KHII (nearest) last reported 18:35Z, 2h16m before the recording.
        XCTAssertEqual(r.temperature?.stationId, "KEED")
        XCTAssertEqual(try XCTUnwrap(r.temperature?.value), 75.2, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(r.windSpeed?.value), 26.463, accuracy: 1e-3)
        XCTAssertEqual(r.windDirection?.value, 10)
        // Needles: altimeter 1015.92 runs 1.9 hPa above SLP — converted.
        XCTAssertEqual(r.pressureKind, .seaLevel)
        XCTAssertEqual(try XCTUnwrap(r.seaLevelOffset), -1.9, accuracy: 1e-9)
        XCTAssertEqual(try XCTUnwrap(r.pressure?.value), 1014.0166, accuracy: 1e-6)
        XCTAssertEqual(r.weatherCode?.value, 0)
        XCTAssertEqual(r.nwsTextDescription, "Clear and Breezy")
    }

    func testGuntersvilleAllStationsStale_GridFallbackAndNoPressure() throws {
        // K8A1 sent nothing in 50 h; KBFZ (18:15Z) and K4A6 (18:35Z) are > 2 h old.
        let r = try XCTUnwrap(try reading("guntersville"))
        XCTAssertEqual(r.temperature?.origin, .nbmGrid)
        XCTAssertEqual(r.temperature?.observedAt, Self.date("2026-11-06T20:00:00Z"))
        XCTAssertEqual(r.temperature?.value, 69)
        XCTAssertEqual(r.humidity?.origin, .nbmGrid)
        XCTAssertEqual(r.windSpeed?.origin, .nbmGrid)
        XCTAssertEqual(r.windDirection?.origin, .nbmGrid)
        XCTAssertNil(r.pressure); XCTAssertNil(r.pressureKind)
        XCTAssertNil(r.pressureTrend); XCTAssertNil(r.pressureChange)
        XCTAssertTrue(r.pressureHistory.isEmpty)
        XCTAssertEqual(r.cloudCover?.value, 15)
        // No fresh observation: the sky code of the grid's own cover (15 % → 1).
        XCTAssertEqual(r.weatherCode?.value, 1)
        XCTAssertEqual(r.weatherCode?.origin, .nbmGrid)
        XCTAssertEqual(r.weatherCode?.observedAt, Self.date("2026-11-06T20:00:00Z"))
        XCTAssertEqual(r.conditionSymbol, "sun.max.fill")
        XCTAssertEqual(r.conditionDescription, "Mainly clear")
        XCTAssertNil(r.nwsTextDescription)
    }

    func testGuntersvilleWhileFresh_AltimeterWithoutSLPStaysLabelled() throws {
        let r = try XCTUnwrap(try reading("guntersville", now: Self.date("2026-11-06T19:00:00Z")))
        // K8A1 is empty; K4A6 (18:35Z) is newer than KBFZ (18:15Z), both within 75 min.
        XCTAssertEqual(r.temperature?.stationId, "K4A6")
        XCTAssertEqual(try XCTUnwrap(r.temperature?.value), 73.4, accuracy: 1e-9)
        XCTAssertEqual(r.humidity?.value, 47)
        // AWOS: no SLP group ever, so no conversion: served as the altimeter.
        XCTAssertEqual(r.pressureKind, .altimeter)
        XCTAssertNil(r.seaLevelOffset)
        XCTAssertEqual(try XCTUnwrap(r.pressure?.value), 1015.6, accuracy: 1e-9)
        XCTAssertEqual(r.pressureTrend, .steady)
        XCTAssertEqual(r.pressureTrend3h, .falling)
        XCTAssertEqual(r.weatherCode?.value, 0)
        XCTAssertEqual(r.conditionSymbol, "sun.max.fill")
    }

    func testHourlySeriesShapes() throws {
        let now = Self.recordedAt
        let r = try XCTUnwrap(try reading("champlain"))
        let past = r.hourlyConditions.filter { $0.date <= now }
        let future = r.hourlyConditions.filter { $0.date > now }
        XCTAssertEqual(r.hourlyConditions.map(\.date), r.hourlyConditions.map(\.date).sorted())
        XCTAssertEqual(future.count, 24)
        XCTAssertTrue(future.allSatisfy { NWSWeatherService.floorToHour($0.date) == $0.date })
        XCTAssertGreaterThanOrEqual(past.count, 40)
        XCTAssertTrue(past.allSatisfy { $0.date >= now.addingTimeInterval(-48 * 3600) })
        // One per clock hour.
        XCTAssertEqual(Set(past.map { NWSWeatherService.floorToHour($0.date) }).count, past.count)
        XCTAssertTrue(r.pressureHistory.allSatisfy { $0.date <= now && $0.date >= now.addingTimeInterval(-48 * 3600) })
        XCTAssertEqual(r.pressureHistory.map(\.date), r.pressureHistory.map(\.date).sorted())
        // The charted series carries the same SLP offset as the current value.
        XCTAssertEqual(try XCTUnwrap(r.pressureHistory.last?.hPa), try XCTUnwrap(r.pressure?.value), accuracy: 1e-9)
    }

    // MARK: Missing values and the stale rule

    private func obs(_ id: String, _ at: Date, temp: Double? = 60, wind: Double? = 5, dir: Double? = 90,
                     alt: Double? = 1015, slp: Double? = nil, icon: String? = nil, text: String? = nil) -> NWSObservation {
        NWSObservation(stationId: id, timestamp: at, textDescription: text, icon: icon,
                       temperatureF: temp, dewPointF: nil, humidity: nil, windMph: wind, windDir: dir,
                       gustMph: nil, seaLevelHPa: slp, altimeterHPa: alt, precipLastHourIn: nil,
                       layerCoverPct: nil)
    }
    private let point = NWSPoint(gridId: "X", gridX: 1, gridY: 2, forecastGridData: "", observationStations: "")

    func testStaleRuleBoundary() {
        let now = Self.recordedAt
        let max = NWSWeatherService.observationMaxAge
        let atLimit = NWSWeatherService.assemble(point: point, stations: ["A"],
            observations: ["A": [obs("A", now.addingTimeInterval(-max))]], grid: nil, now: now)
        XCTAssertEqual(atLimit?.temperature?.value, 60)
        let tooOld = NWSWeatherService.assemble(point: point, stations: ["A"],
            observations: ["A": [obs("A", now.addingTimeInterval(-max - 1))]], grid: nil, now: now)
        XCTAssertNil(tooOld, "nothing fresh and no grid: no reading at all")
    }

    func testMissingFieldsComeFromTheNextStationOrStayNil() {
        let now = Self.recordedAt
        let a = obs("A", now.addingTimeInterval(-600), temp: nil, wind: 7, dir: nil, alt: nil)
        let b = obs("B", now.addingTimeInterval(-1200), temp: 55, wind: 3, dir: 180, alt: 1012)
        let r = NWSWeatherService.assemble(point: point, stations: ["A", "B"],
                                           observations: ["A": [a], "B": [b]], grid: nil, now: now)!
        XCTAssertEqual(r.temperature?.stationId, "B")
        XCTAssertEqual(r.pressure?.stationId, "B")
        // Wind speed and direction come from the same observation: A is calm-
        // variable (no direction), so direction stays nil rather than B's 180.
        XCTAssertEqual(r.windSpeed?.stationId, "A")
        XCTAssertNil(r.windDirection)
        XCTAssertNil(r.humidity)                // nobody reported it, no grid
        XCTAssertNil(r.cloudCover)
        XCTAssertNil(r.weatherCode)
        XCTAssertNil(r.pressureTrend)           // no sample 12 h back
        XCTAssertNil(r.pressureChange)
    }

    func testNewestWithin75MinBeatsTheNearerStation() {
        let now = Self.recordedAt
        let near = obs("A", now.addingTimeInterval(-(115 * 60)), temp: 50, alt: 1010)   // 1h55m
        let far = obs("B", now.addingTimeInterval(-(5 * 60)), temp: 52, alt: 1011)      // 5 min
        let r = NWSWeatherService.assemble(point: point, stations: ["A", "B"],
                                           observations: ["A": [near], "B": [far]], grid: nil, now: now)!
        XCTAssertEqual(r.temperature?.stationId, "B")
        XCTAssertEqual(r.pressure?.stationId, "B")
        XCTAssertEqual(r.windSpeed?.stationId, "B")
        // Nothing within 75 min anywhere: nearest-first up to 2 h.
        let older = obs("B", now.addingTimeInterval(-(100 * 60)), temp: 52)
        let r2 = NWSWeatherService.assemble(point: point, stations: ["A", "B"],
                                            observations: ["A": [near], "B": [older]], grid: nil, now: now)!
        XCTAssertEqual(r2.temperature?.stationId, "A")
        // Equal timestamps: the nearer station.
        let nearFresh = obs("A", now.addingTimeInterval(-600), temp: 50)
        let tieB = obs("B", nearFresh.timestamp, temp: 52)
        let r3 = NWSWeatherService.assemble(point: point, stations: ["A", "B"],
                                            observations: ["A": [nearFresh], "B": [tieB]], grid: nil, now: now)!
        XCTAssertEqual(r3.temperature?.stationId, "A")
    }

    func testCalmWindHasNoDirection() {
        let now = Self.recordedAt
        let calm = obs("A", now.addingTimeInterval(-600), wind: 0, dir: 0)
        let r = NWSWeatherService.assemble(point: point, stations: ["A"],
                                           observations: ["A": [calm]], grid: nil, now: now)!
        XCTAssertEqual(r.windSpeed?.value, 0)
        XCTAssertNil(r.windDirection)
    }

    func testTrendToleranceIsStrict() {
        let at = Self.recordedAt
        let series = [(at, 1010.0), (at.addingTimeInterval(-12 * 3600 - 90 * 60), 1005.0)]
        XCTAssertNil(NWSWeatherService.pressureTendency(current: 1010, at: at, series: series,
                                                        hours: 12, steadyHPa: 1.5))
        let inside = [(at, 1010.0), (at.addingTimeInterval(-12 * 3600 - 89 * 60), 1005.0)]
        XCTAssertEqual(NWSWeatherService.pressureTendency(current: 1010, at: at, series: inside,
                                                          hours: 12, steadyHPa: 1.5)?.0, .rising)
    }

    func testNothingAnywhereIsNil() {
        XCTAssertNil(NWSWeatherService.assemble(point: point, stations: [], observations: [:],
                                                grid: nil, now: Self.recordedAt))
    }

    // MARK: Service (injected fetch)

    private final class Recorder: @unchecked Sendable {
        private let lock = NSLock()
        private var urls: [URL] = []
        func add(_ u: URL) { lock.lock(); urls.append(u); lock.unlock() }
        var all: [URL] { lock.lock(); defer { lock.unlock() }; return urls }
    }

    private static func fixtureFetch(_ lake: String, recorder: Recorder) -> NWSWeatherService.Fetch {
        { url in
            recorder.add(url)
            let path = url.path
            let name: String
            if path.hasPrefix("/points/") { name = "\(lake)-points" }
            else if path.hasPrefix("/gridpoints/") && path.hasSuffix("/stations") { name = "\(lake)-stations" }
            else if path.hasPrefix("/gridpoints/") { name = "\(lake)-grid" }
            else if path.hasPrefix("/stations/") {
                name = "\(lake)-obs-\(url.pathComponents[2])"
            } else { return nil }
            return try? data(name)
        }
    }

    func testServiceUsesFixturesAndCachesPoints() async throws {
        let rec = Recorder()
        let svc = NWSWeatherService(fetch: Self.fixtureFetch("champlain", recorder: rec), now: { Self.recordedAt })
        let r1 = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertEqual(r1?.temperature?.stationId, "KBTV")
        XCTAssertEqual(rec.all.filter { $0.path.hasPrefix("/points/") }.map(\.path), ["/points/44.47,-73.30"])
        // Same 0.01° cell: no second points or stations lookup.
        _ = await svc.reading(near: .init(latitude: 44.4712, longitude: -73.3021))
        XCTAssertEqual(rec.all.filter { $0.path.hasPrefix("/points/") }.count, 1)
        XCTAssertEqual(rec.all.filter { $0.path.hasSuffix("/stations") }.count, 1)
        let cached = await svc.cachedPointsCount
        XCTAssertEqual(cached, 1)
        // Observation requests ask for the 49 h lookback.
        let obsURL = try XCTUnwrap(rec.all.first { $0.path.hasPrefix("/stations/") })
        XCTAssertTrue(obsURL.query?.contains("start=2026-11-04T19:51:00Z") ?? false, obsURL.absoluteString)
    }

    func testServicePointsCacheExpiresAfter24h() async {
        let rec = Recorder()
        final class Clock: @unchecked Sendable { var now = NWSWeatherServiceTests.recordedAt }
        let clock = Clock()
        let svc = NWSWeatherService(fetch: Self.fixtureFetch("champlain", recorder: rec), now: { clock.now })
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        clock.now = Self.recordedAt.addingTimeInterval(NWSWeatherService.pointsTTL - 1)
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertEqual(rec.all.filter { $0.path.hasPrefix("/points/") }.count, 1)
        clock.now = Self.recordedAt.addingTimeInterval(NWSWeatherService.pointsTTL + 1)
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertEqual(rec.all.filter { $0.path.hasPrefix("/points/") }.count, 2)
    }

    func testOutsideCoverageIsNilAndNotCached() async {
        let svc = NWSWeatherService(fetch: { _ in nil }, now: { Self.recordedAt })
        let r = await svc.reading(near: .init(latitude: 51.5, longitude: -0.12))
        XCTAssertNil(r)
        let cached = await svc.cachedPointsCount
        XCTAssertEqual(cached, 0)
    }

    private static func slow(_ base: @escaping NWSWeatherService.Fetch,
                             when match: @escaping @Sendable (URL) -> Bool) -> NWSWeatherService.Fetch {
        { url in
            if match(url) { try? await Task.sleep(nanoseconds: 30_000_000_000); return nil }
            return await base(url)
        }
    }

    func testSlowGridKeepsFreshObservations() async {
        let rec = Recorder()
        let fetch = Self.slow(Self.fixtureFetch("champlain", recorder: rec)) {
            $0.path.hasPrefix("/gridpoints/") && !$0.path.hasSuffix("/stations")
        }
        let svc = NWSWeatherService(fetch: fetch, now: { Self.recordedAt })
        let start = Date()
        let r = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertLessThan(Date().timeIntervalSince(start), NWSWeatherService.deadlineSeconds)
        XCTAssertEqual(r?.temperature?.stationId, "KBTV")
        XCTAssertEqual(r?.pressure?.stationId, "KBTV")
        // No grid: cloud from the observation's layers, no forecast half.
        XCTAssertEqual(r?.cloudCover?.origin, .observation)
        XCTAssertEqual(r?.hourlyConditions.filter { $0.date > Self.recordedAt }.count, 0)
    }

    func testSlowStationsDegradeToGridOnlyAndAreNotCached() async {
        let rec = Recorder()
        let fetch = Self.slow(Self.fixtureFetch("champlain", recorder: rec)) { $0.path.hasSuffix("/stations") }
        let svc = NWSWeatherService(fetch: fetch, now: { Self.recordedAt })
        let start = Date()
        let r = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertLessThan(Date().timeIntervalSince(start), NWSWeatherService.deadlineSeconds)
        XCTAssertEqual(r?.temperature?.origin, .nbmGrid)
        XCTAssertNil(r?.pressure)
        let cached = await svc.cachedPointsCount
        XCTAssertEqual(cached, 0)
    }

    func testEmptyStationListIsNeverCached() async {
        let rec = Recorder()
        let base = Self.fixtureFetch("champlain", recorder: rec)
        let svc = NWSWeatherService(fetch: { url in
            if url.path.hasSuffix("/stations") { rec.add(url); return Data("{\"features\":[]}".utf8) }
            return await base(url)
        }, now: { Self.recordedAt })
        let r = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertEqual(r?.temperature?.origin, .nbmGrid)      // grid-only, not nil
        let cached = await svc.cachedPointsCount
        XCTAssertEqual(cached, 0)
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertEqual(rec.all.filter { $0.path.hasSuffix("/stations") }.count, 2)   // retried
    }

    func testPointsCacheEvictsLeastRecentlyUsed() async {
        let rec = Recorder()
        let svc = NWSWeatherService(fetch: Self.fixtureFetch("champlain", recorder: rec),
                                    now: { Self.recordedAt }, cacheCapacity: 2)
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.30))
        _ = await svc.reading(near: .init(latitude: 44.48, longitude: -73.30))
        _ = await svc.reading(near: .init(latitude: 44.47, longitude: -73.30))   // touch the first
        _ = await svc.reading(near: .init(latitude: 44.49, longitude: -73.30))   // evicts 44.48
        let keys = await svc.cachedPointsKeys
        XCTAssertEqual(keys, ["44.47,-73.30", "44.49,-73.30"])
        XCTAssertEqual(NWSWeatherService.pointsCacheCapacity, 5_000)
    }

    func testDeadlineReturnsNil() async {
        let svc = NWSWeatherService(fetch: { _ in
            try? await Task.sleep(nanoseconds: 30_000_000_000)
            return nil
        }, now: { Self.recordedAt })
        let start = Date()
        let r = await svc.reading(near: .init(latitude: 44.47, longitude: -73.3))
        XCTAssertNil(r)
        XCTAssertLessThan(Date().timeIntervalSince(start), NWSWeatherService.deadlineSeconds + 2)
    }

    // MARK: Parity

    private func openMeteo(humidity: Int = 61, pressure: Double = 1012, temp: Double = 60,
                           cloud: Double = 40, code: Int = 2, wind: Double = 10, dir: Int = 350) -> WeatherReading {
        let (desc, sym) = WeatherService.condition(forCode: code)
        return WeatherReading(temperature: temp, conditionDescription: desc, conditionSymbol: sym,
                              windSpeed: wind, windDirection: dir, precipitation: 0, recentRainfall: 0,
                              humidity: humidity, pressure: pressure, pressureTrend: .falling,
                              pressureChange: -2, cloudCover: cloud, weatherCode: code, time: Self.recordedAt)
    }

    func testParityPerTileDeltas() throws {
        let nws = try XCTUnwrap(try reading("champlain"))
        let p = NWSWeatherParity.compare(old: openMeteo(), new: nws)
        XCTAssertEqual(p.map(\.tile), ["humidity", "pressure", "temperature", "sky", "wind"])
        let byTile = Dictionary(uniqueKeysWithValues: p.map { ($0.tile, $0) })
        XCTAssertEqual(byTile["humidity"]?.old, 61); XCTAssertEqual(byTile["humidity"]?.new, 59)
        XCTAssertEqual(byTile["humidity"]?.delta, -2)
        XCTAssertEqual(byTile["pressure"]?.delta, -1.6)
        XCTAssertEqual(byTile["pressure"]?.detail["trendOld"], .string("falling"))
        XCTAssertEqual(byTile["pressure"]?.detail["trendNew"], .string("steady"))
        XCTAssertEqual(byTile["pressure"]?.detail["pressureKindNew"], .string("seaLevel"))
        XCTAssertEqual(byTile["temperature"]?.delta, 2.6)
        XCTAssertEqual(byTile["sky"]?.delta, 8)
        XCTAssertEqual(byTile["sky"]?.detail["codeMatch"], .bool(true))
        XCTAssertEqual(byTile["sky"]?.detail["symbolMatch"], .bool(true))
        XCTAssertEqual(byTile["wind"]?.delta, -0.78)
        XCTAssertEqual(byTile["wind"]?.detail["dirDelta"], .number(-30))   // 350 → 320
        XCTAssertEqual(byTile["wind"]?.newStation, "KBTV")
        XCTAssertEqual(byTile["wind"]?.newOrigin, "observation")
        XCTAssertTrue(p.allSatisfy { $0.oldSource == "open-meteo" && $0.newSource == "nws-nbm" })
    }

    func testParityWithMissingNWSValues() throws {
        let p = NWSWeatherParity.compare(old: openMeteo(), new: nil)
        XCTAssertEqual(p.count, 5)
        XCTAssertTrue(p.allSatisfy { $0.new == nil && $0.delta == nil && $0.old != nil })
        // Explicit nulls, so every shadow line has the same keys.
        let line = NWSWeatherParity.logLine(p[0], lakeId: nil, latR: nil, lonR: nil)
        XCTAssertTrue(line.contains("\"new\":null"), line)
        XCTAssertTrue(line.contains("\"delta\":null"), line)
        XCTAssertTrue(line.contains("\"old\":61"), line)
    }

    func testAngleDeltaWraps() {
        XCTAssertEqual(NWSWeatherParity.angleDelta(from: 350, to: 10), 20)
        XCTAssertEqual(NWSWeatherParity.angleDelta(from: 10, to: 350), -20)
        XCTAssertEqual(NWSWeatherParity.angleDelta(from: 0, to: 180), 180)
        XCTAssertEqual(NWSWeatherParity.angleDelta(from: 90, to: 90), 0)
    }

    func testShadowLogLine() throws {
        let nws = try XCTUnwrap(try reading("champlain"))
        let humidity = NWSWeatherParity.compare(old: openMeteo(), new: nws)[0]
        let line = NWSWeatherParity.logLine(humidity, lakeId: "Champlain|VT", latR: 44.5, lonR: -73.3)
        XCTAssertTrue(line.hasPrefix("[tile-shadow] {"))
        let json = try XCTUnwrap(try JSONSerialization.jsonObject(
            with: Data(line.dropFirst("[tile-shadow] ".count).utf8)) as? [String: Any])
        XCTAssertEqual(json["tile"] as? String, "humidity")
        XCTAssertEqual(json["old"] as? Double, 61)
        XCTAssertEqual(json["new"] as? Double, 59)
        XCTAssertEqual(json["delta"] as? Double, -2)
        XCTAssertEqual(json["oldSource"] as? String, "open-meteo")
        XCTAssertEqual(json["newSource"] as? String, "nws-nbm")
        XCTAssertEqual(json["lakeId"] as? String, "Champlain|VT")
        XCTAssertEqual(json["latR"] as? Double, 44.5)
        XCTAssertEqual(json["newObservedAt"] as? String, "2026-11-06T20:30:00Z")
    }
}
