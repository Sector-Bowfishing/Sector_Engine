//
//  NWSWeatherService.swift
//  SectorEngine
//
//  NWS/NBM weather source adapter (Sector_Ops #53, conditions consolidation
//  spec V1 §1: the Humidity, Barometric Pressure, Temperature, Sky and Wind
//  tiles, source id `nws-nbm`). NOT wired into /conditions: it is called by
//  nothing in the request path until the tile flags and the shadow helper land.
//
//  Sources (all api.weather.gov, US only, free, no key, User-Agent required):
//   1. /points/{lat},{lon} → the NDFD gridpoint (`forecastGridData`) and the
//      observation-station list (nearest first). Static mapping, cached 24 h
//      per 0.01°.
//   2. /stations/{id}/observations?start=… → the last ~49 h of observations
//      for the three nearest stations. The newest fresh one is "now"; the rest
//      is the past half of the hourly series and the pressure trend.
//   3. forecastGridData → the NBM-based NDFD grid: the next 24 h of hourly
//      temperature, humidity, wind, gust, dew point and sky cover.
//
//  Meaning rules (docs/architecture/conditions/NWS_WEATHER_ADAPTER_V1.md):
//   - Units are the build 28 units: °F, Int %, hPa, mph, Int degrees, 0…100 %
//     cloud, WMO weather code + the SF Symbol vocabulary of WeatherService.
//   - Every value carries its real `observedAt` (observation timestamp, or the
//     start of the NBM grid hour) and where it came from. Nothing is invented:
//     a value nobody reported stays nil.
//   - An observation older than `observationMaxAge` is stale and never used as
//     "now". Stale/missing temperature, humidity and wind fall back to the NBM
//     grid's current hour (origin `.nbmGrid`). Pressure and present weather have
//     no grid fallback and stay nil.
//   - Pressure is mean-sea-level pressure, which is what WeatherService serves
//     (Open-Meteo `pressure_msl`; NOT `surface_pressure`). The newest altimeter
//     setting (`barometricPressure` in the NWS API) is converted to SLP with the
//     station's own measured SLP − altimeter offset; with no offset available
//     it is served as the altimeter value and labelled `.altimeter`.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Reading

/// Where one NWS value came from.
enum NWSValueOrigin: String, Equatable, Sendable, Codable {
    /// A station observation (METAR/ASOS/AWOS via api.weather.gov).
    case observation
    /// The NBM-based NDFD gridpoint forecast for the current hour.
    case nbmGrid
}

/// One value with its provenance. `observedAt` is the observation timestamp, or
/// the start of the grid hour the forecast value is valid for.
struct NWSValue<T: Equatable & Sendable>: Equatable, Sendable {
    let value: T
    let observedAt: Date
    let origin: NWSValueOrigin
    /// Station identifier for `.observation` values; nil for grid values.
    let stationId: String?
}

/// Which pressure the NWS reading carries. Both are sea-level reductions.
enum NWSPressureKind: String, Equatable, Sendable, Codable {
    /// Mean-sea-level pressure — the quantity Open-Meteo `pressure_msl` is,
    /// which is what WeatherService serves: the METAR SLP, or the altimeter
    /// converted with the station's measured SLP − altimeter offset.
    case seaLevel
    /// The altimeter setting (NWS API `barometricPressure`): station pressure
    /// reduced with the ICAO standard atmosphere. Served only when no SLP pair
    /// exists to convert it; it differs from MSL by ~0.1 hPa in Vermont and
    /// ~1.9 hPa at Needles, CA in the 2026-11-06 recordings.
    case altimeter
}

/// The NWS/NBM reading for the five weather tiles, in build 28 units.
struct NWSWeatherReading: Equatable, Sendable {
    let fetchedAt: Date
    /// NDFD gridpoint, e.g. "HUN/76,30".
    let gridpoint: String

    /// °F.
    let temperature: NWSValue<Double>?
    /// Relative humidity, %, rounded like WeatherService.
    let humidity: NWSValue<Int>?
    /// hPa, sea-level reduced (see `pressureKind`).
    let pressure: NWSValue<Double>?
    let pressureKind: NWSPressureKind?
    /// SLP − altimeter (hPa) applied to the altimeter reading, from the same
    /// station's newest observation carrying both. nil when not applied.
    let seaLevelOffset: Double?
    /// 12 h tendency with WeatherService's rule (closest sample to 12 h before
    /// the current pressure, steady within ±1.5 hPa) — the meaning of the
    /// served `pressureTrend` / `pressureChange` fields. nil without a sample
    /// within 90 min of that time (WeatherService would say steady/0; we don't
    /// invent a flat barometer).
    let pressureTrend: PressureTrend?
    /// Signed hPa over the 12 h lookback.
    let pressureChange: Double?
    /// 3 h tendency with `WeatherReading.displayPressureTrend`'s rule (±0.02
    /// inHg over 3 h) — what the pressure sheet and the score actually show.
    let pressureTrend3h: PressureTrend?
    /// Signed hPa over 3 h.
    let pressureChange3h: Double?
    /// mph.
    let windSpeed: NWSValue<Double>?
    /// Degrees, 0 = N, Int. nil for calm-without-direction or variable wind.
    let windDirection: NWSValue<Int>?
    /// Total sky cover, 0…100 %.
    let cloudCover: NWSValue<Double>?
    /// WMO weather code, restricted to the codes WeatherService emits.
    let weatherCode: NWSValue<Int>?
    /// `WeatherService.condition(forCode:)` for `weatherCode` — the same
    /// labels and SF Symbols the apps already map.
    let conditionDescription: String?
    let conditionSymbol: String?
    /// The NWS observation's own text, e.g. "Light Rain and Fog/Mist".
    let nwsTextDescription: String?

    /// Hourly sea-level pressure, past 48 h (observations only — the NBM grid
    /// carries no pressure, so there is no forecast half). Chronological.
    let pressureHistory: [PressureSample]
    /// Hourly conditions: past 48 h from observations, next 24 h from the NBM
    /// grid. Same shape as `WeatherReading.hourlyConditions`. Chronological.
    let hourlyConditions: [ConditionsHourly]
}

// MARK: - Service

actor NWSWeatherService {
    static let shared = NWSWeatherService()

    /// Same identifying User-Agent WeatherAlertsService sends to api.weather.gov
    /// (NWS returns 403 without one).
    static let userAgent = HTTP.defaultUserAgent
    /// Whole-reading budget; on expiry the result is nil.
    static let deadlineSeconds: Double = 8
    /// An observation older than this is stale: never used as "now".
    static let observationMaxAge: TimeInterval = 2 * 3600
    /// The points → gridpoint/stations mapping is static; refresh daily.
    static let pointsTTL: TimeInterval = 24 * 3600
    /// Nearest stations tried, in NWS's nearest-first order.
    static let maxStations = 3
    /// History requested from each station (48 h series + the 12 h trend slack).
    static let observationLookback: TimeInterval = 49 * 3600
    /// Oldest SLP/altimeter pair used to convert the altimeter to SLP.
    static let slpOffsetMaxAge: TimeInterval = 6 * 3600
    /// A trend's past sample must be this close to its target time.
    static let trendSampleTolerance: TimeInterval = 90 * 60
    static let pastHours = 48
    static let futureHours = 24

    /// GET returning the body on HTTP 200, nil otherwise. Injectable for tests.
    typealias Fetch = @Sendable (URL) async -> Data?

    private let fetch: Fetch
    private let now: @Sendable () -> Date
    private var pointsCache: [String: (point: NWSPoint, stations: [String], at: Date)] = [:]

    init(fetch: @escaping Fetch = NWSWeatherService.liveFetch,
         now: @escaping @Sendable () -> Date = { Date() }) {
        self.fetch = fetch
        self.now = now
    }

    static let liveFetch: Fetch = { url in
        guard let r = try? await HTTP.get(url, headers: [
            "User-Agent": NWSWeatherService.userAgent,
            "Accept": "application/geo+json",
        ], timeout: deadlineSeconds), r.status == 200 else { return nil }
        return r.body
    }

    /// The NWS/NBM reading at the coordinate, or nil (outside NWS coverage, any
    /// upstream failure that leaves no value, or the 8 s deadline).
    func reading(near coordinate: CLLocationCoordinate2D) async -> NWSWeatherReading? {
        let lat = coordinate.latitude, lon = coordinate.longitude
        return await withDeadline(Self.deadlineSeconds, "nws-weather") { [self] in
            await self.fetchReading(lat: lat, lon: lon)
        }
    }

    /// Cache key and request coordinate: 0.01° (~1 km), well inside one 2.5 km
    /// NDFD cell. NWS redirects requests with more than 4 decimals anyway.
    static func pointsKey(lat: Double, lon: Double) -> String {
        String(format: "%.2f,%.2f", lat, lon)
    }

    /// Number of cached points lookups (tests).
    var cachedPointsCount: Int { pointsCache.count }

    private func lookup(lat: Double, lon: Double) async -> (NWSPoint, [String])? {
        let key = Self.pointsKey(lat: lat, lon: lon)
        let t = now()
        if let hit = pointsCache[key], t.timeIntervalSince(hit.at) < Self.pointsTTL {
            return (hit.point, hit.stations)
        }
        guard let url = URL(string: "https://api.weather.gov/points/\(key)"),
              let data = await fetch(url),
              let point = Self.decodePoint(data),
              let stationsURL = URL(string: point.observationStations),
              let sdata = await fetch(stationsURL) else { return nil }
        let stations = Array(Self.decodeStations(sdata).prefix(Self.maxStations))
        pointsCache[key] = (point, stations, t)
        return (point, stations)
    }

    private func fetchReading(lat: Double, lon: Double) async -> NWSWeatherReading? {
        guard let (point, stations) = await lookup(lat: lat, lon: lon) else { return nil }
        let t = now()
        let start = Self.isoSeconds(t.addingTimeInterval(-Self.observationLookback))
        let fetch = self.fetch

        async let gridData: Data? = {
            guard let url = URL(string: point.forecastGridData) else { return nil }
            return await fetch(url)
        }()
        let observations: [String: [NWSObservation]] = await withTaskGroup(
            of: (String, [NWSObservation]).self) { group in
            for id in stations {
                group.addTask {
                    var c = URLComponents(string: "https://api.weather.gov/stations/\(id)/observations")
                    c?.queryItems = [URLQueryItem(name: "start", value: start),
                                     URLQueryItem(name: "limit", value: "500")]
                    guard let url = c?.url, let d = await fetch(url) else { return (id, []) }
                    return (id, Self.decodeObservations(d))
                }
            }
            var out: [String: [NWSObservation]] = [:]
            for await (id, obs) in group { out[id] = obs }
            return out
        }
        let grid = await gridData.flatMap(Self.decodeGrid)
        return Self.assemble(point: point, stations: stations, observations: observations,
                             grid: grid, now: t)
    }

    /// One formatter per process (a new one per call opens an ICU formatter on
    /// Linux). ISO8601DateFormatter is thread-safe for formatting.
    private static let secondsFormatter: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func isoSeconds(_ d: Date) -> String { secondsFormatter.string(from: d) }
}

// MARK: - Decoded upstream shapes

struct NWSPoint: Equatable, Sendable {
    let gridId: String
    let gridX: Int
    let gridY: Int
    let forecastGridData: String
    let observationStations: String
}

/// One station observation, already in build 28 units. QC-rejected values are nil.
struct NWSObservation: Equatable, Sendable {
    let stationId: String
    let timestamp: Date
    let textDescription: String?
    let icon: String?
    let temperatureF: Double?
    let dewPointF: Double?
    let humidity: Double?
    let windMph: Double?
    let windDir: Double?
    let gustMph: Double?
    let seaLevelHPa: Double?
    let altimeterHPa: Double?
    let precipLastHourIn: Double?
    /// Highest reported layer amount mapped to %, e.g. OVC = 100. ASOS sees
    /// only below 12,000 ft, so CLR is not "no cloud".
    let layerCoverPct: Double?
}

/// NBM/NDFD grid layers expanded to hourly values keyed by the hour start.
struct NWSGrid: Equatable, Sendable {
    var temperatureF: [Date: Double] = [:]
    var dewPointF: [Date: Double] = [:]
    var humidity: [Date: Double] = [:]
    var windMph: [Date: Double] = [:]
    var gustMph: [Date: Double] = [:]
    var windDir: [Date: Double] = [:]
    var skyCover: [Date: Double] = [:]
    /// Only hours whose QPF period is exactly one hour (longer periods are
    /// accumulations; splitting them would invent an hourly rate).
    var precipIn: [Date: Double] = [:]

    var allHours: Set<Date> {
        Set(temperatureF.keys).union(dewPointF.keys).union(humidity.keys).union(windMph.keys)
            .union(gustMph.keys).union(windDir.keys).union(skyCover.keys)
    }
}

// MARK: - Decoding and assembly (pure)

extension NWSWeatherService {

    static func decodePoint(_ data: Data) -> NWSPoint? {
        struct R: Decodable {
            let properties: P
            struct P: Decodable {
                let gridId: String?; let gridX: Int?; let gridY: Int?
                let forecastGridData: String?; let observationStations: String?
            }
        }
        guard let p = try? JSONDecoder().decode(R.self, from: data).properties,
              let id = p.gridId, let x = p.gridX, let y = p.gridY,
              let g = p.forecastGridData, let s = p.observationStations else { return nil }
        return NWSPoint(gridId: id, gridX: x, gridY: y, forecastGridData: g, observationStations: s)
    }

    /// Station identifiers in NWS's order (nearest first).
    static func decodeStations(_ data: Data) -> [String] {
        struct R: Decodable {
            let features: [F]
            struct F: Decodable { let properties: P }
            struct P: Decodable { let stationIdentifier: String? }
        }
        guard let r = try? JSONDecoder().decode(R.self, from: data) else { return [] }
        return r.features.compactMap { $0.properties.stationIdentifier }
    }

    struct Quantity: Decodable {
        let unitCode: String?
        let value: Double?
        let qualityControl: String?
    }

    /// Observations newest first. Unparseable rows are dropped.
    static func decodeObservations(_ data: Data) -> [NWSObservation] {
        struct R: Decodable {
            let features: [F]
            struct F: Decodable { let properties: P }
            struct P: Decodable {
                let station: String?
                let timestamp: String?
                let textDescription: String?
                let icon: String?
                let temperature: Quantity?
                let dewpoint: Quantity?
                let relativeHumidity: Quantity?
                let windSpeed: Quantity?
                let windDirection: Quantity?
                let windGust: Quantity?
                let seaLevelPressure: Quantity?
                let barometricPressure: Quantity?
                let precipitationLastHour: Quantity?
                let cloudLayers: [Layer]?
            }
            struct Layer: Decodable { let amount: String? }
        }
        guard let r = try? JSONDecoder().decode(R.self, from: data) else { return [] }
        let rows: [NWSObservation] = r.features.compactMap { f in
            let p = f.properties
            guard let ts = p.timestamp.flatMap(parseDate) else { return nil }
            let id = p.station.map { String($0.split(separator: "/").last ?? "") } ?? ""
            let text = p.textDescription.flatMap { $0.isEmpty ? nil : $0 }
            let icon = p.icon.flatMap { $0.isEmpty ? nil : $0 }
            let layers = (p.cloudLayers ?? []).compactMap { $0.amount.flatMap(layerPercent) }
            return NWSObservation(
                stationId: id, timestamp: ts, textDescription: text, icon: icon,
                temperatureF: convert(p.temperature, to: .fahrenheit),
                dewPointF: convert(p.dewpoint, to: .fahrenheit),
                humidity: convert(p.relativeHumidity, to: .percent),
                windMph: convert(p.windSpeed, to: .mph),
                windDir: convert(p.windDirection, to: .degrees),
                gustMph: convert(p.windGust, to: .mph),
                seaLevelHPa: convert(p.seaLevelPressure, to: .hPa),
                altimeterHPa: convert(p.barometricPressure, to: .hPa),
                precipLastHourIn: convert(p.precipitationLastHour, to: .inches),
                layerCoverPct: layers.max())
        }
        return rows.sorted { $0.timestamp > $1.timestamp }
    }

    /// METAR layer amount → % of sky (octas midpoint). VV (obscured) = 100.
    static func layerPercent(_ amount: String) -> Double? {
        switch amount.uppercased() {
        case "SKC", "CLR", "NCD", "NSC": return 0
        case "FEW": return 18.75     // 1–2 octas
        case "SCT": return 43.75     // 3–4 octas
        case "BKN": return 75        // 5–7 octas
        case "OVC", "VV": return 100
        default: return nil
        }
    }

    static func decodeGrid(_ data: Data) -> NWSGrid? {
        struct Layer: Decodable {
            let uom: String?
            let values: [V]?
            struct V: Decodable { let validTime: String; let value: Double? }
        }
        // `properties` mixes layers with scalars (updateTime, elevation…), so
        // decode it loosely: any entry that isn't a numeric layer becomes nil.
        struct Loose: Decodable {
            let properties: [String: LooseLayer]
            struct LooseLayer: Decodable {
                let layer: Layer?
                init(from decoder: Decoder) throws { layer = try? Layer(from: decoder) }
            }
        }
        guard let r = try? JSONDecoder().decode(Loose.self, from: data) else { return nil }
        func hourly(_ key: String, _ target: Unit, onlyHourly: Bool = false) -> [Date: Double] {
            guard let layer = r.properties[key]?.layer, let values = layer.values else { return [:] }
            var out: [Date: Double] = [:]
            for v in values {
                guard let raw = v.value,
                      let converted = convert(raw, unitCode: layer.uom, to: target),
                      let (start, hours) = parseValidTime(v.validTime) else { continue }
                if onlyHourly && hours != 1 { continue }
                for h in 0..<hours { out[start.addingTimeInterval(TimeInterval(h * 3600))] = converted }
            }
            return out
        }
        var g = NWSGrid()
        g.temperatureF = hourly("temperature", .fahrenheit)
        g.dewPointF = hourly("dewpoint", .fahrenheit)
        g.humidity = hourly("relativeHumidity", .percent)
        g.windMph = hourly("windSpeed", .mph)
        g.gustMph = hourly("windGust", .mph)
        g.windDir = hourly("windDirection", .degrees)
        g.skyCover = hourly("skyCover", .percent)
        g.precipIn = hourly("quantitativePrecipitation", .inches, onlyHourly: true)
        return g
    }

    /// Builds the reading. nil when there is no current value for any tile.
    static func assemble(point: NWSPoint, stations: [String],
                         observations: [String: [NWSObservation]],
                         grid: NWSGrid?, now: Date) -> NWSWeatherReading? {
        // Fresh observations per station, nearest station first, newest first.
        let fresh: [(String, [NWSObservation])] = stations.map { id in
            (id, (observations[id] ?? []).filter {
                now.timeIntervalSince($0.timestamp) <= observationMaxAge && $0.timestamp <= now.addingTimeInterval(600)
            })
        }
        /// First fresh observation (nearest station, then newest) with `has`.
        func pick(_ has: (NWSObservation) -> Bool) -> NWSObservation? {
            for (_, obs) in fresh { if let o = obs.first(where: has) { return o } }
            return nil
        }
        func obsValue<T>(_ o: NWSObservation, _ v: T) -> NWSValue<T> {
            NWSValue(value: v, observedAt: o.timestamp, origin: .observation, stationId: o.stationId)
        }
        let hourStart = floorToHour(now)
        func gridValue<T>(_ layer: [Date: Double]?, _ map: (Double) -> T) -> NWSValue<T>? {
            guard let v = layer?[hourStart] else { return nil }
            return NWSValue(value: map(v), observedAt: hourStart, origin: .nbmGrid, stationId: nil)
        }

        // Temperature / humidity: observation, else the grid's current hour.
        let tempObs = pick { $0.temperatureF != nil }
        let temperature = tempObs.map { obsValue($0, $0.temperatureF!) }
            ?? gridValue(grid?.temperatureF) { $0 }
        let humidity = pick { $0.humidity != nil }.map { obsValue($0, Int($0.humidity!.rounded())) }
            ?? gridValue(grid?.humidity) { Int($0.rounded()) }

        // Wind: speed and direction from the SAME observation (or grid hour).
        let windSpeed: NWSValue<Double>?
        let windDirection: NWSValue<Int>?
        if let o = pick({ $0.windMph != nil }) {
            windSpeed = obsValue(o, o.windMph!)
            windDirection = o.windDir.map { obsValue(o, Int($0.rounded()) % 360) }
        } else {
            windSpeed = gridValue(grid?.windMph) { $0 }
            windDirection = windSpeed == nil ? nil : gridValue(grid?.windDir) { Int($0.rounded()) % 360 }
        }

        // Pressure. The API fills the METAR SLP group hours late (in the
        // 2026-11-06 recordings the newest SLP was ~3 h old at every station),
        // while the altimeter setting comes with every observation. So "now" is
        // the newest fresh altimeter, converted to sea-level pressure with the
        // station's own measured offset (SLP − altimeter on its newest
        // observation carrying both, within `slpOffsetMaxAge`). Without such a
        // pair the altimeter value is served as-is and labelled `.altimeter`.
        // Trends are computed on the raw altimeter series, so the offset never
        // leaks into a tendency. No grid fallback: NDFD has no pressure here.
        var pressure: NWSValue<Double>?
        var pressureKind: NWSPressureKind?
        var slpOffset: Double?
        var pressureSeries: [(Date, Double)] = []   // raw, for the trends
        var historyOffset = 0.0                     // added to the charted series
        if let o = pick({ $0.altimeterHPa != nil }) {
            let rows = (observations[o.stationId] ?? []).filter { $0.timestamp <= o.timestamp }
            pressureSeries = rows.compactMap { x in x.altimeterHPa.map { (x.timestamp, $0) } }
            if let pair = rows.first(where: { $0.seaLevelHPa != nil && $0.altimeterHPa != nil
                && o.timestamp.timeIntervalSince($0.timestamp) <= slpOffsetMaxAge }) {
                slpOffset = pair.seaLevelHPa! - pair.altimeterHPa!
            }
            historyOffset = slpOffset ?? 0
            pressure = obsValue(o, o.altimeterHPa! + historyOffset)
            pressureKind = slpOffset == nil ? .altimeter : .seaLevel
        } else if let o = pick({ $0.seaLevelHPa != nil }) {
            let rows = (observations[o.stationId] ?? []).filter { $0.timestamp <= o.timestamp }
            pressureSeries = rows.compactMap { x in x.seaLevelHPa.map { (x.timestamp, $0) } }
            pressure = obsValue(o, o.seaLevelHPa!)
            pressureKind = .seaLevel
        }
        var trend12: (PressureTrend, Double)?
        var trend3: (PressureTrend, Double)?
        if let p = pressure, let raw = pressureSeries.first?.1 {
            trend12 = pressureTendency(current: raw, at: p.observedAt, series: pressureSeries,
                                       hours: 12, steadyHPa: WeatherService.steadyThresholdHPa)
            trend3 = pressureTendency(current: raw, at: p.observedAt, series: pressureSeries,
                                      hours: 3, steadyHPa: 0.02 / WeatherReading.hPaToInHg)
        }

        // Sky: cover from the NBM grid (total cloud, like Open-Meteo's model
        // cloud_cover); the observation's layers only if the grid has no hour.
        let skyObs = pick { $0.icon != nil || $0.textDescription != nil }
        let cloudCover = gridValue(grid?.skyCover) { $0 }
            ?? pick({ $0.layerCoverPct != nil }).map { obsValue($0, $0.layerCoverPct!) }
        // Present weather needs a fresh observation; the grid only says "chance".
        var weatherCode: NWSValue<Int>?
        if let o = skyObs, let code = NWSCondition.weatherCode(icon: o.icon, text: o.textDescription,
                                                               skyCoverPct: cloudCover?.value) {
            weatherCode = obsValue(o, code)
        }
        let label = weatherCode.map { WeatherService.condition(forCode: $0.value) }

        if temperature == nil && humidity == nil && pressure == nil && windSpeed == nil
            && cloudCover == nil && weatherCode == nil { return nil }

        // Hourly series: past from the temperature station (else the nearest
        // station with any data), future from the grid.
        let seriesStation = tempObs?.stationId
            ?? stations.first { !(observations[$0] ?? []).isEmpty }
        let past = hourlyPast(observations[seriesStation ?? ""] ?? [], grid: grid, now: now)
        let future = hourlyFuture(grid, now: now)
        let pressureHistory = thinHourly(pressureSeries, now: now)
            .map { PressureSample(date: $0.0, hPa: $0.1 + historyOffset) }

        return NWSWeatherReading(
            fetchedAt: now,
            gridpoint: "\(point.gridId)/\(point.gridX),\(point.gridY)",
            temperature: temperature, humidity: humidity,
            pressure: pressure, pressureKind: pressureKind, seaLevelOffset: slpOffset,
            pressureTrend: trend12?.0, pressureChange: trend12?.1,
            pressureTrend3h: trend3?.0, pressureChange3h: trend3?.1,
            windSpeed: windSpeed, windDirection: windDirection,
            cloudCover: cloudCover, weatherCode: weatherCode,
            conditionDescription: label?.description, conditionSymbol: label?.symbol,
            nwsTextDescription: skyObs?.textDescription,
            pressureHistory: pressureHistory,
            hourlyConditions: (past + future).sorted { $0.date < $1.date })
    }

    /// Signed change from the sample closest to `hours` before `at` (within
    /// `trendSampleTolerance`), classified with a ± steady band in hPa.
    static func pressureTendency(current: Double, at: Date, series: [(Date, Double)],
                                 hours: Int, steadyHPa: Double) -> (PressureTrend, Double)? {
        let target = at.addingTimeInterval(TimeInterval(-hours * 3600))
        guard let past = series.min(by: { abs($0.0.timeIntervalSince(target)) < abs($1.0.timeIntervalSince(target)) }),
              abs(past.0.timeIntervalSince(target)) <= trendSampleTolerance else { return nil }
        let change = current - past.1
        if change > steadyHPa { return (.rising, change) }
        if change < -steadyHPa { return (.falling, change) }
        return (.steady, change)
    }

    /// One sample per clock hour (the latest in that hour), within the past
    /// window, chronological. Real timestamps are kept.
    static func thinHourly<T>(_ series: [(Date, T)], now: Date) -> [(Date, T)] {
        let lower = now.addingTimeInterval(TimeInterval(-pastHours * 3600))
        var byHour: [Date: (Date, T)] = [:]
        for s in series where s.0 >= lower && s.0 <= now {
            let h = floorToHour(s.0)
            if let cur = byHour[h], cur.0 >= s.0 { continue }
            byHour[h] = s
        }
        return byHour.values.sorted { $0.0 < $1.0 }
    }

    static func hourlyPast(_ obs: [NWSObservation], grid: NWSGrid?, now: Date) -> [ConditionsHourly] {
        thinHourly(obs.map { ($0.timestamp, $0) }, now: now).compactMap { (date, o) in
            let s = ConditionsHourly(date: date, tempF: o.temperatureF, humidity: o.humidity,
                                     windMph: o.windMph, gustMph: o.gustMph, windDir: o.windDir,
                                     dewPointF: o.dewPointF,
                                     // Cloud % from the grid hour when it covers it; ASOS
                                     // layers stop at 12,000 ft so they are not total cloud.
                                     cloudPct: grid?.skyCover[floorToHour(date)],
                                     precipIn: o.precipLastHourIn)
            if s.tempF == nil && s.humidity == nil && s.windMph == nil
                && s.cloudPct == nil && s.precipIn == nil { return nil }
            return s
        }
    }

    static func hourlyFuture(_ grid: NWSGrid?, now: Date) -> [ConditionsHourly] {
        guard let g = grid else { return [] }
        let upper = now.addingTimeInterval(TimeInterval(futureHours * 3600))
        return g.allHours.filter { $0 > now && $0 <= upper }.sorted().map { h in
            ConditionsHourly(date: h, tempF: g.temperatureF[h], humidity: g.humidity[h],
                             windMph: g.windMph[h], gustMph: g.gustMph[h], windDir: g.windDir[h],
                             dewPointF: g.dewPointF[h], cloudPct: g.skyCover[h], precipIn: g.precipIn[h])
        }
    }

    // MARK: Units

    enum Unit { case fahrenheit, percent, mph, degrees, hPa, inches }

    static func convert(_ q: Quantity?, to target: Unit) -> Double? {
        guard let q, let v = q.value else { return nil }
        // QC "X" = rejected, "B" = subjective bad. Everything else is usable.
        if let qc = q.qualityControl?.uppercased(), qc == "X" || qc == "B" { return nil }
        return convert(v, unitCode: q.unitCode, to: target)
    }

    /// Converts a WMO-unit value. An unknown or mismatched unit gives nil —
    /// never a guess.
    static func convert(_ v: Double, unitCode: String?, to target: Unit) -> Double? {
        let u = (unitCode ?? "").replacingOccurrences(of: "wmoUnit:", with: "")
            .replacingOccurrences(of: "unit:", with: "")
        switch (target, u) {
        case (.fahrenheit, "degC"): return v * 9 / 5 + 32
        case (.fahrenheit, "degF"): return v
        case (.percent, "percent"): return v
        case (.mph, "km_h-1"): return v / 1.609344
        case (.mph, "m_s-1"): return v * 3600 / 1609.344
        case (.mph, "kt"), (.mph, "knot"): return v * 1.150779
        case (.degrees, "degree_(angle)"): return v
        case (.hPa, "Pa"): return v / 100
        case (.hPa, "hPa"): return v
        case (.inches, "mm"): return v / 25.4
        case (.inches, "m"): return v / 0.0254
        default: return nil
        }
    }

    // MARK: Time

    private static let isoFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let iso = ISO8601DateFormatter()

    static func parseDate(_ s: String) -> Date? {
        iso.date(from: s) ?? isoFractional.date(from: s)
    }

    /// "2026-11-06T14:00:00+00:00/PT2H" → (start, whole hours). Durations are
    /// ISO 8601 `P[nD][T[nH][nM]]`; a sub-hour remainder is dropped.
    static func parseValidTime(_ s: String) -> (Date, Int)? {
        let parts = s.split(separator: "/", maxSplits: 1)
        guard parts.count == 2, let start = parseDate(String(parts[0])) else { return nil }
        var days = 0, hours = 0, minutes = 0, num = "", inTime = false
        for ch in parts[1] {
            switch ch {
            case "P": continue
            case "T": inTime = true
            case "0"..."9": num.append(ch)
            case "D": days = Int(num) ?? 0; num = ""
            case "H": hours = Int(num) ?? 0; num = ""
            case "M": if inTime { minutes = Int(num) ?? 0 }; num = ""
            default: return nil
            }
        }
        let total = days * 24 + hours + minutes / 60
        guard total > 0 else { return nil }
        return (start, total)
    }

    static func floorToHour(_ d: Date) -> Date {
        Date(timeIntervalSince1970: (d.timeIntervalSince1970 / 3600).rounded(.down) * 3600)
    }
}

// MARK: - NWS icon / text → WMO code

/// Maps the NWS observation icon set (api.weather.gov/icons, 34 icons) and
/// its text descriptions to the WMO codes WeatherService emits, so
/// `WeatherService.condition(forCode:)` gives the label and SF Symbol. Output is
/// limited to Open-Meteo's code set: build 28 apps map exactly those.
enum NWSCondition {

    /// Every icon api.weather.gov serves (GET /icons, 2026-11-06).
    static let iconSet: [String] = [
        "skc", "few", "sct", "bkn", "ovc",
        "wind_skc", "wind_few", "wind_sct", "wind_bkn", "wind_ovc",
        "snow", "rain_snow", "rain_sleet", "snow_sleet", "fzra", "rain_fzra", "snow_fzra",
        "sleet", "rain", "rain_showers", "rain_showers_hi", "tsra", "tsra_sct", "tsra_hi",
        "tornado", "hurricane", "tropical_storm", "dust", "smoke", "haze", "hot", "cold",
        "blizzard", "fog",
    ]

    enum Intensity { case light, moderate, heavy }

    /// The icon name in an NWS icon URL, e.g.
    /// ".../icons/land/night/rain,40/tsra?size=medium" → "rain".
    static func iconName(_ url: String?) -> String? {
        guard let url, !url.isEmpty else { return nil }
        let path = url.split(separator: "?").first.map(String.init) ?? url
        let comps = path.split(separator: "/").map(String.init)
        guard let i = comps.firstIndex(where: { $0 == "day" || $0 == "night" }), i + 1 < comps.count
        else { return nil }
        let name = comps[i + 1].split(separator: ",").first.map(String.init) ?? ""
        return name.isEmpty ? nil : name
    }

    static func intensity(_ text: String?) -> Intensity {
        let t = (text ?? "").lowercased()
        if t.hasPrefix("light") || t.contains(" light ") { return .light }
        if t.hasPrefix("heavy") || t.contains(" heavy ") { return .heavy }
        return .moderate
    }

    static func pick(_ i: Intensity, _ light: Int, _ moderate: Int, _ heavy: Int) -> Int {
        switch i { case .light: light; case .moderate: moderate; case .heavy: heavy }
    }

    /// Sky-only code for a total-cloud %: NWS octa categories — clear < 1/8,
    /// mostly clear < 3/8, partly/mostly cloudy < 7/8, overcast ≥ 7/8.
    static func skyCode(percent p: Double) -> Int {
        if p < 12.5 { return 0 }
        if p < 37.5 { return 1 }
        if p < 87.5 { return 2 }
        return 3
    }

    /// Sky-only code for a sky icon (wind_ prefix ignored), or nil.
    static func skyCode(icon: String) -> Int? {
        switch icon.replacingOccurrences(of: "wind_", with: "") {
        case "skc": 0
        case "few": 1
        case "sct", "bkn": 2
        case "ovc": 3
        default: nil
        }
    }

    /// Weather-phenomenon code (≥ 45) for an icon, refined by the text
    /// (intensity, drizzle, hail). nil for sky-only icons and the non-weather
    /// icons (dust, smoke, haze, hot, cold), whose sky comes from cover.
    static func phenomenonCode(icon: String, text: String?) -> Int? {
        let t = (text ?? "").lowercased()
        let i = intensity(text)
        switch icon {
        case "fog": return 45
        case "rain":
            if t.contains("freezing drizzle") { return pick(i, 56, 56, 57) }
            if t.contains("drizzle") && !t.contains("rain") { return pick(i, 51, 53, 55) }
            return pick(i, 61, 63, 65)
        case "rain_showers", "rain_showers_hi": return pick(i, 80, 81, 82)
        case "fzra", "rain_fzra", "snow_fzra", "sleet", "rain_sleet": return pick(i, 66, 66, 67)
        case "snow", "rain_snow", "snow_sleet":
            if t.contains("snow shower") { return i == .heavy ? 86 : 85 }
            return pick(i, 71, 73, 75)
        case "blizzard": return 75
        case "tsra", "tsra_sct", "tsra_hi", "tornado", "hurricane", "tropical_storm":
            return t.contains("hail") ? 96 : 95
        default: return nil
        }
    }

    /// Phenomenon code from the text alone (observations with no icon).
    static func phenomenonCode(text: String) -> Int? {
        let t = text.lowercased()
        if t.contains("thunder") || t.contains("tornado") || t.contains("funnel") {
            return phenomenonCode(icon: "tsra", text: text)
        }
        if t.contains("freezing rain") || t.contains("sleet") || t.contains("ice pellets") {
            return phenomenonCode(icon: "fzra", text: text)
        }
        if t.contains("snow") { return phenomenonCode(icon: "snow", text: text) }
        if t.contains("shower") { return phenomenonCode(icon: "rain_showers", text: text) }
        if t.contains("rain") || t.contains("drizzle") { return phenomenonCode(icon: "rain", text: text) }
        if t.contains("fog") { return 45 }
        return nil
    }

    /// Sky-only code from the text alone.
    static func skyCode(text: String) -> Int? {
        let t = text.lowercased()
        if t.contains("mostly cloudy") || t.contains("partly cloudy") || t.contains("partly sunny") { return 2 }
        if t.contains("mostly clear") || t.contains("mostly sunny") || t.contains("fair") { return 1 }
        if t.contains("cloudy") || t.contains("overcast") { return 3 }
        if t.contains("clear") || t.contains("sunny") { return 0 }
        return nil
    }

    /// The observation's WMO code: a weather phenomenon from the icon (or the
    /// text) wins; otherwise the sky code from the total cloud % when known,
    /// else from the icon / text. nil when nothing identifies the sky.
    static func weatherCode(icon: String?, text: String?, skyCoverPct: Double?) -> Int? {
        let name = iconName(icon)
        if let name, let c = phenomenonCode(icon: name.replacingOccurrences(of: "wind_", with: ""), text: text) {
            return c
        }
        if name == nil, let text, let c = phenomenonCode(text: text) { return c }
        if let p = skyCoverPct { return skyCode(percent: p) }
        if let name, let c = skyCode(icon: name) { return c }
        if let text { return skyCode(text: text) }
        return nil
    }
}
