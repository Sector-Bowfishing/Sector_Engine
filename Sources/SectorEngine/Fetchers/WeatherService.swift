//
//  WeatherService.swift
//  Sector
//
//  Fetches current conditions (temperature, wind, precipitation, and a
//  12-hour barometric-pressure trend) from the free Open-Meteo forecast
//  API. No API key, no entitlement required.
//  https://open-meteo.com/
//
//  Pressure trend matters for fishing: fish tend to feed harder on a
//  falling barometer, so the trend is surfaced alongside the raw value.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

enum PressureTrend: Equatable {
    case rising
    case falling
    case steady
}

/// One hourly sample inside a trip window (for the "how it changed" chart).
struct WindowHourly: Equatable {
    let date: Date
    let windMph: Double?
    let tempF: Double?
    let pressureInHg: Double?
}

/// Weather aggregated across a trip's start→end window, plus the hourly series.
struct WindowWeather: Equatable {
    let windAvg: Double   // mph
    let windMin: Double
    let windMax: Double
    let tempAvg: Double   // °F
    let tempMin: Double
    let tempMax: Double
    let sky: String       // dominant condition over the window
    let hoursSampled: Int
    let hourly: [WindowHourly]   // chronological samples within the window
}

/// One hourly sample of the metrics the conditions detail sheets chart. Pressure
/// keeps its own `PressureSample` series — that one predates this, is tuned, and
/// is the star of the pressure sheet; duplicating its value here would be two
/// sources of truth for the same number.
struct ConditionsHourly: Hashable {
    let date: Date
    let tempF: Double?
    let humidity: Double?
    let windMph: Double?
    let gustMph: Double?
    let windDir: Double?
    /// Dew point °F. Temperature falling to meet this is what makes fog.
    let dewPointF: Double?
    /// Cloud cover % (0…100) — drives the Sky tile's chart and, with the moon,
    /// how much light actually reaches the water.
    var cloudPct: Double? = nil
    /// Precipitation this hour (inches) — drives the Clarity tile's chart:
    /// rain is what muddies the shallows.
    var precipIn: Double? = nil
}

struct WeatherReading: Equatable {
    let temperature: Double         // °F
    let conditionDescription: String
    let conditionSymbol: String     // SF Symbol name
    let windSpeed: Double           // mph
    let windDirection: Int          // degrees (0 = N)
    let precipitation: Double        // inches (right now)
    let recentRainfall: Double       // inches, total over the past ~3 days
    let humidity: Int               // %
    let pressure: Double            // hPa
    let pressureTrend: PressureTrend
    let pressureChange: Double      // signed hPa change over the lookback window
    let cloudCover: Double          // % (0…100) — feeds the conditions darkness factor
    let weatherCode: Int            // WMO code — feeds the conditions sky factor
    let time: Date

    /// Hourly barometric series around `time` — roughly the past 24h plus the next
    /// 12h of forecast — so the pressure detail can chart where it's been and where
    /// it's headed. Chronological; empty if the hourly data was unavailable.
    var pressureHistory: [PressureSample] = []

    /// Hourly temperature / humidity / wind around `time`, same window as
    /// `pressureHistory`. Drives the trend charts on the non-pressure sheets.
    /// Empty when the hourly data was unavailable — every chart guards on that.
    var hourlyConditions: [ConditionsHourly] = []

    /// Samples at or before `time` (measured) and after it (forecast).
    var conditionsPast: [ConditionsHourly] { hourlyConditions.filter { $0.date <= time } }
    var conditionsForecast: [ConditionsHourly] { hourlyConditions.filter { $0.date > time } }

    /// Compass abbreviation for the wind direction, e.g. "SW".
    var windCompass: String { WeatherService.compass(forDegrees: windDirection) }

    /// Barometric pressure in inches of mercury (US convention) — the app shows
    /// pressure in inHg everywhere it's user-facing. `pressure`/`pressureChange`
    /// stay in hPa (what Open-Meteo returns); convert only at the display edge.
    static let hPaToInHg = 0.0295299830714
    var pressureInHg: Double { pressure * WeatherReading.hPaToInHg }
    /// Signed pressure change over the lookback window, in inHg.
    var pressureChangeInHg: Double { pressureChange * WeatherReading.hPaToInHg }

    /// Series samples at or before `time` (measured/past).
    var pressurePast: [PressureSample] { pressureHistory.filter { $0.date <= time } }
    /// Series samples after `time` (forecast).
    var pressureForecast: [PressureSample] { pressureHistory.filter { $0.date > time } }

    /// Expected signed change (inHg) from now to `hours` into the forecast — the
    /// "what it's about to do" readout. `nil` if there isn't forecast that far out.
    func expectedPressureChangeInHg(inHours hours: Int) -> Double? {
        let target = time.addingTimeInterval(TimeInterval(hours * 3600))
        guard let future = pressureForecast.min(by: {
            abs($0.date.timeIntervalSince(target)) < abs($1.date.timeIntervalSince(target))
        }) else { return nil }
        return future.inHg - pressureInHg
    }

    /// Signed pressure change (inHg) over the last `hours`, read off the hourly
    /// series — the short-window "tendency" the eye sees on the chart. `nil` when
    /// there's no sample near that hour.
    func recentPressureChangeInHg(hours: Int) -> Double? {
        let target = time.addingTimeInterval(TimeInterval(-hours * 3600))
        guard let past = pressurePast.min(by: {
            abs($0.date.timeIntervalSince(target)) < abs($1.date.timeIntervalSince(target))
        }), abs(past.date.timeIntervalSince(target)) < 90 * 60 else { return nil }
        return pressureInHg - past.inHg
    }

    /// The barometric trend used everywhere — the 3-hour tendency (NWS convention)
    /// so the label matches recent motion on the chart, not a 12h endpoint delta
    /// that washes out intraday swings (a dip-and-recover day would read "steady").
    /// Falls back to the 12h `pressureTrend` when the hourly series is unavailable.
    /// Drives BOTH the detail-sheet label/narrative AND the conditions-engine
    /// pressure factor (via `ConditionsInputBuilder`), so score + sheet agree.
    var displayPressureTrend: PressureTrend {
        guard let change = recentPressureChangeInHg(hours: 3) else { return pressureTrend }
        let steadyBand = 0.02   // inHg over 3h
        if change >  steadyBand { return .rising }
        if change < -steadyBand { return .falling }
        return .steady
    }
}

/// One hourly barometric reading in the pressure series.
struct PressureSample: Hashable {
    let date: Date
    let hPa: Double
    var inHg: Double { hPa * WeatherReading.hPaToInHg }
}

enum WeatherError: Error {
    case invalidURL
    case requestFailed
    case decodingFailed
}

final class WeatherService {
    static let shared = WeatherService()
    private init() {}


    /// Open-Meteo forecast hosts, tried in order. The primary is occasionally
    /// unreachable from some US carrier networks (AT&T ↔ Hetzner peering /
    /// edge filtering — TCP connects but TLS never completes). The
    /// historical-forecast instance runs the same /v1/forecast API from a
    /// different datacenter IP, so it works as a transparent fallback.
    static let forecastEndpoints = [
        "https://api.open-meteo.com/v1/forecast",
        "https://historical-forecast-api.open-meteo.com/v1/forecast",
    ]
    // A 12-hour window is enough to read the barometric trend.
    private let lookbackHours = 12
    // Pressure swings smaller than this (hPa) over the window read as "steady".
    static let steadyThresholdHPa = 1.5

    /// Fetches `queryItems` from whichever forecast endpoint answers FIRST.
    ///
    /// This used to try the hosts in sequence: primary, and only after its 15s
    /// window elapsed, the sibling. The failure mode that caused it was a primary
    /// that ACCEPTS the TCP connection but never completes the TLS handshake
    /// (a peering/edge-filter issue that's intermittent from Cloud Run's egress),
    /// so it didn't refuse fast — it hung the full 15s on every single weather
    /// fetch, and a conditions request makes several. That stacked into the 30s+
    /// floor we measured, and past the 60s Cloud Run limit it became a 504.
    ///
    /// Racing both hosts concurrently fixes it at the root: the healthy host
    /// (~0.5s) wins immediately and the stalled one is cancelled, so a dead
    /// primary costs nothing instead of 15s. Each host still gets its own
    /// fail-fast timeout as a backstop.
    static func fetchForecastData(queryItems: [URLQueryItem]) async throws -> Data {
        let data: Data? = await withTaskGroup(of: Data?.self) { group in
            for endpoint in forecastEndpoints {
                group.addTask { await fetchOne(endpoint: endpoint, queryItems: queryItems) }
            }
            // Take the first host that returns a 2xx body; a fast failure from one
            // host doesn't end the race, it just yields nil and we keep reading.
            for await result in group {
                if let result {
                    group.cancelAll()
                    return result
                }
            }
            return nil
        }
        guard let data else { throw WeatherError.requestFailed }
        return data
    }

    /// One endpoint attempt. Returns the body on a 2xx, nil on any failure
    /// (timeout, cancellation, non-2xx) so the caller's race can move on.
    private static func fetchOne(endpoint: String, queryItems: [URLQueryItem]) async -> Data? {
        var components = URLComponents(string: endpoint)
        components?.queryItems = queryItems
        guard let url = components?.url else { return nil }

        // 8s, not 15: a host that hasn't answered in 8s has lost the race to its
        // sibling anyway — no reason to hold the connection open longer.
        guard let result = try? await HTTP.get(url, timeout: 8), result.isSuccess else {
            return nil
        }
        return result.body
    }

    /// Current conditions at the coordinate, with a pressure trend computed
    /// from the past `lookbackHours` of hourly readings.
    func conditions(near coordinate: CLLocationCoordinate2D) async throws -> WeatherReading {
        let queryItems = [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", coordinate.latitude)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", coordinate.longitude)),
            URLQueryItem(name: "current", value: "temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m"),
            URLQueryItem(name: "hourly", value: "pressure_msl,temperature_2m,relative_humidity_2m,dew_point_2m,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover,precipitation"),
            URLQueryItem(name: "daily", value: "precipitation_sum"),
            URLQueryItem(name: "past_days", value: "3"),
            // 2 days, not 1: with 1, "forecast" ends at local midnight, so an
            // afternoon load left the 12-hour forecast tail truncated.
            URLQueryItem(name: "forecast_days", value: "3"),
            URLQueryItem(name: "temperature_unit", value: "fahrenheit"),
            URLQueryItem(name: "wind_speed_unit", value: "mph"),
            URLQueryItem(name: "precipitation_unit", value: "inch"),
            URLQueryItem(name: "timezone", value: "auto"),
        ]

        let data: Data
        do {
            data = try await Self.fetchForecastData(queryItems: queryItems)
        } catch let error as WeatherError {
            throw error
        } catch {
            throw WeatherError.requestFailed
        }

        return try Self.reading(from: data, lookbackHours: lookbackHours)
    }

    // MARK: - Windowed conditions (a trip's start→end span)

    /// Aggregated weather across a time window `[from, to]` — used when a trip has a
    /// start and end time, so its captured conditions represent the whole night
    /// rather than one instant. Pulls Open-Meteo's HOURLY series for the day(s) the
    /// window spans (works for past nights via the same historical-forecast host)
    /// and averages / ranges the hours that fall inside the window.
    func windowConditions(near coordinate: CLLocationCoordinate2D,
                          from: Date, to: Date) async throws -> WindowWeather {
        guard to > from else { throw WeatherError.requestFailed }
        let df = DateFormatter()
        df.calendar = Calendar(identifier: .gregorian)
        df.locale = Locale(identifier: "en_US_POSIX")
        df.dateFormat = "yyyy-MM-dd"
        // Span local calendar days (a night usually crosses midnight).
        let startDay = df.string(from: from)
        let endDay = df.string(from: to)

        let queryItems = [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", coordinate.latitude)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", coordinate.longitude)),
            URLQueryItem(name: "hourly", value: "temperature_2m,wind_speed_10m,weather_code,cloud_cover,pressure_msl"),
            URLQueryItem(name: "start_date", value: startDay),
            URLQueryItem(name: "end_date", value: endDay),
            URLQueryItem(name: "temperature_unit", value: "fahrenheit"),
            URLQueryItem(name: "wind_speed_unit", value: "mph"),
            URLQueryItem(name: "timezone", value: "auto"),
        ]

        let data: Data
        do { data = try await Self.fetchForecastData(queryItems: queryItems) }
        catch let e as WeatherError { throw e }
        catch { throw WeatherError.requestFailed }

        return try Self.windowReading(from: data, from: from, to: to)
    }

    /// Pure aggregation of an hourly response over `[from, to]` — testable with
    /// canned JSON. Averages temp/wind, keeps their min/max, and picks the window's
    /// most-common weather code for the sky label.
    static func windowReading(from data: Data, from: Date, to: Date) throws -> WindowWeather {
        let decoded: WindowResponse
        do { decoded = try JSONDecoder().decode(WindowResponse.self, from: data) }
        catch { throw WeatherError.decodingFailed }

        let h = decoded.hourly
        var winds: [Double] = [], temps: [Double] = [], codes: [Int] = []
        var samples: [WindowHourly] = []
        for i in h.time.indices {
            guard let t = parseLocalTime(h.time[i]), t >= from, t <= to else { continue }
            let w = i < h.wind_speed_10m.count ? h.wind_speed_10m[i] : nil
            let tp = i < h.temperature_2m.count ? h.temperature_2m[i] : nil
            let pr = (i < (h.pressure_msl?.count ?? 0) ? h.pressure_msl?[i] : nil)
                .map { $0 * WeatherReading.hPaToInHg }
            if let w { winds.append(w) }
            if let tp { temps.append(tp) }
            if i < h.weather_code.count, let c = h.weather_code[i] { codes.append(c) }
            samples.append(WindowHourly(date: t, windMph: w, tempF: tp, pressureInHg: pr))
        }
        guard !winds.isEmpty || !temps.isEmpty else { throw WeatherError.requestFailed }

        func avg(_ a: [Double]) -> Double { a.isEmpty ? 0 : a.reduce(0, +) / Double(a.count) }
        // Most-common weather code → sky description (defaults to clear).
        let domCode = Dictionary(grouping: codes, by: { $0 })
            .max(by: { $0.value.count < $1.value.count })?.key ?? 0
        let (sky, _) = condition(forCode: domCode)

        return WindowWeather(
            windAvg: avg(winds), windMin: winds.min() ?? 0, windMax: winds.max() ?? 0,
            tempAvg: avg(temps), tempMin: temps.min() ?? 0, tempMax: temps.max() ?? 0,
            sky: sky, hoursSampled: max(winds.count, temps.count),
            hourly: samples.sorted { $0.date < $1.date })
    }

    // MARK: - Parsing (pure, unit-testable)

    /// Decodes an Open-Meteo response into a `WeatherReading`, computing the
    /// pressure trend from the hourly series. Pure — no network — so tests can
    /// feed it canned JSON.
    static func reading(from data: Data, lookbackHours: Int = 12) throws -> WeatherReading {
        let decoded: OpenMeteoResponse
        do {
            decoded = try JSONDecoder().decode(OpenMeteoResponse.self, from: data)
        } catch {
            throw WeatherError.decodingFailed
        }

        let current = decoded.current
        let now = parseLocalTime(current.time) ?? Date()

        let (trend, change) = pressureTrend(
            currentPressure: current.pressure_msl,
            hourlyTimes: decoded.hourly.time,
            hourlyPressures: decoded.hourly.pressure_msl,
            now: now,
            lookbackHours: lookbackHours
        )

        // Windowed hourly series (past 24h → next 12h) for the pressure detail chart.
        // 48 each way so the pressure sheet's 48H range has real data behind it.
        // Only what the selected range asks for is ever plotted, so the wider
        // window costs nothing on the default view.
        let history = pressureSamples(
            hourlyTimes: decoded.hourly.time,
            hourlyPressures: decoded.hourly.pressure_msl,
            now: now, pastHours: 48, futureHours: 48
        )

        let hourlyConditions = conditionSamples(
            hourlyTimes: decoded.hourly.time,
            temps: decoded.hourly.temperature_2m,
            humidity: decoded.hourly.relative_humidity_2m,
            winds: decoded.hourly.wind_speed_10m,
            gusts: decoded.hourly.wind_gusts_10m,
            dirs: decoded.hourly.wind_direction_10m,
            dewPoints: decoded.hourly.dew_point_2m,
            clouds: decoded.hourly.cloud_cover,
            precip: decoded.hourly.precipitation,
            // 48/24, matching the pressure history window, so the Sky and
            // Clarity charts have the same 6/12/24H range options as the rest.
            now: now, pastHours: 48, futureHours: 24
        )

        // Open-Meteo's categorical `weather_code` is model-derived and sometimes
        // reports rain/storm on a step its OWN measurements say is clear and dry
        // (observed: code 95 with precipitation 0.0 and 0% cloud on a calm night).
        // Trust the measurements: if the code claims precip (≥51 = drizzle/rain/
        // snow/storm) but none is falling and the sky is clear, downgrade it to a
        // clear/cloudy code. High cloud cover is preserved, so a real storm — which
        // always brings heavy cloud — is never wrongly cleared.
        let effectiveCode = Self.sanitizedWeatherCode(current.weather_code,
                                                      precipitation: current.precipitation,
                                                      cloudCover: current.cloud_cover ?? 0)
        let (description, symbol) = condition(forCode: effectiveCode)

        // Recent rainfall that can still be muddying the water RIGHT NOW: the
        // last ~48 h of OBSERVED daily totals (yesterday + today). This endpoint
        // returns past_days=3 + forecast_days=3 = SIX daily buckets
        // [D-3 … D+2]; summing the whole array (the old bug) counted three extra
        // past days AND two days of FUTURE forecast rain that hasn't fallen yet,
        // inflating rainLast48hIn ~3× and blowing the no-gage clarity estimate
        // out to ~0.1 ft. Restrict to today + yesterday, never the future.
        // See docs/audits/2026-08-06 conditions clarity audit.
        let recentRain: Double = {
            guard let daily = decoded.daily else { return 0 }
            let cal = Calendar.current
            let today = cal.startOfDay(for: now)
            let df = DateFormatter()
            df.locale = Locale(identifier: "en_US_POSIX")
            df.dateFormat = "yyyy-MM-dd"
            df.timeZone = .current
            var sum = 0.0
            for (i, t) in daily.time.enumerated() where i < daily.precipitation_sum.count {
                guard let d = df.date(from: t) else { continue }
                let daysAgo = cal.dateComponents([.day], from: cal.startOfDay(for: d), to: today).day ?? -1
                // 0 = today, 1 = yesterday. Skip future (< 0) and older (> 1).
                if daysAgo >= 0, daysAgo <= 1 { sum += daily.precipitation_sum[i] ?? 0 }
            }
            return sum
        }()

        return WeatherReading(
            temperature: current.temperature_2m,
            conditionDescription: description,
            conditionSymbol: symbol,
            windSpeed: current.wind_speed_10m,
            windDirection: Int(current.wind_direction_10m.rounded()),
            precipitation: current.precipitation,
            recentRainfall: recentRain,
            humidity: Int(current.relative_humidity_2m.rounded()),
            pressure: current.pressure_msl,
            pressureTrend: trend,
            pressureChange: change,
            cloudCover: current.cloud_cover ?? 0,
            weatherCode: effectiveCode,
            time: now,
            pressureHistory: history,
            hourlyConditions: hourlyConditions
        )
    }

    /// Pure: hourly temp / humidity / wind within `[now - pastHours, now + futureHours]`.
    /// Mirrors `pressureSamples`. A sample survives if it has ANY of the metrics —
    /// each chart filters for the one it needs, so a gap in (say) gusts doesn't
    /// drop the temperature reading for that hour.
    static func conditionSamples(hourlyTimes: [String],
                                 temps: [Double?]?,
                                 humidity: [Double?]?,
                                 winds: [Double?]?,
                                 gusts: [Double?]?,
                                 dirs: [Double?]?,
                                 dewPoints: [Double?]?,
                                 clouds: [Double?]? = nil,
                                 precip: [Double?]? = nil,
                                 now: Date,
                                 pastHours: Int,
                                 futureHours: Int) -> [ConditionsHourly] {
        let lower = now.addingTimeInterval(TimeInterval(-pastHours * 3600))
        let upper = now.addingTimeInterval(TimeInterval(futureHours * 3600))
        func at(_ a: [Double?]?, _ i: Int) -> Double? {
            guard let a, i < a.count else { return nil }
            return a[i]
        }
        var samples: [ConditionsHourly] = []
        for (i, timeString) in hourlyTimes.enumerated() {
            guard let date = parseLocalTime(timeString), date >= lower, date <= upper else { continue }
            let s = ConditionsHourly(date: date,
                                     tempF: at(temps, i),
                                     humidity: at(humidity, i),
                                     windMph: at(winds, i),
                                     gustMph: at(gusts, i),
                                     windDir: at(dirs, i),
                                     dewPointF: at(dewPoints, i),
                                     cloudPct: at(clouds, i),
                                     precipIn: at(precip, i))
            if s.tempF == nil && s.humidity == nil && s.windMph == nil
                && s.cloudPct == nil && s.precipIn == nil { continue }
            samples.append(s)
        }
        return samples.sorted { $0.date < $1.date }
    }

    /// Pure: builds the chronological hourly pressure series within
    /// `[now - pastHours, now + futureHours]`. Skips samples without a value.
    static func pressureSamples(hourlyTimes: [String],
                                hourlyPressures: [Double?],
                                now: Date,
                                pastHours: Int,
                                futureHours: Int) -> [PressureSample] {
        let lower = now.addingTimeInterval(TimeInterval(-pastHours * 3600))
        let upper = now.addingTimeInterval(TimeInterval(futureHours * 3600))
        var samples: [PressureSample] = []
        for (index, timeString) in hourlyTimes.enumerated() {
            guard index < hourlyPressures.count,
                  let hPa = hourlyPressures[index],
                  let date = parseLocalTime(timeString),
                  date >= lower, date <= upper else { continue }
            samples.append(PressureSample(date: date, hPa: hPa))
        }
        return samples.sorted { $0.date < $1.date }
    }

    /// Classifies the barometric trend by comparing the current pressure to the
    /// hourly reading closest to `lookbackHours` ago.
    static func pressureTrend(currentPressure: Double,
                              hourlyTimes: [String],
                              hourlyPressures: [Double?],
                              now: Date,
                              lookbackHours: Int = 12) -> (PressureTrend, Double) {
        let target = now.addingTimeInterval(TimeInterval(-lookbackHours * 3600))

        // Find the hourly sample closest to the target time that has a value.
        var best: (pressure: Double, distance: TimeInterval)?
        for (index, timeString) in hourlyTimes.enumerated() {
            guard index < hourlyPressures.count,
                  let pressure = hourlyPressures[index],
                  let date = parseLocalTime(timeString) else { continue }
            let distance = abs(date.timeIntervalSince(target))
            if best == nil || distance < best!.distance {
                best = (pressure, distance)
            }
        }

        guard let past = best?.pressure else { return (.steady, 0) }
        let change = currentPressure - past
        if change > steadyThresholdHPa { return (.rising, change) }
        if change < -steadyThresholdHPa { return (.falling, change) }
        return (.steady, change)
    }

    /// Maps a WMO weather-interpretation code to a label and SF Symbol.
    /// Reconciles Open-Meteo's categorical weather code with its measured
    /// precipitation + cloud cover. Codes ≥ 51 mean drizzle/rain/snow/storm; if
    /// nothing's actually falling and the sky is clear, the code is a false
    /// positive and we return a clear/cloudy code instead. Pure + testable.
    static let falsePrecipCloudCeiling: Double = WeatherCode.falsePrecipCloudCeiling

    /// Thin wrapper over the engine's pure sanitizer (single source of truth).
    static func sanitizedWeatherCode(_ code: Int, precipitation: Double, cloudCover: Double) -> Int {
        WeatherCode.sanitized(code, precipitation: precipitation, cloudCover: cloudCover)
    }

    static func condition(forCode code: Int) -> (description: String, symbol: String) {
        switch code {
        case 0:            return ("Clear", "sun.max.fill")
        case 1:            return ("Mainly clear", "sun.max.fill")
        case 2:            return ("Partly cloudy", "cloud.sun.fill")
        case 3:            return ("Overcast", "cloud.fill")
        case 45, 48:       return ("Fog", "cloud.fog.fill")
        case 51, 53, 55:   return ("Drizzle", "cloud.drizzle.fill")
        case 56, 57:       return ("Freezing drizzle", "cloud.sleet.fill")
        case 61, 63, 65:   return ("Rain", "cloud.rain.fill")
        case 66, 67:       return ("Freezing rain", "cloud.sleet.fill")
        case 71, 73, 75, 77: return ("Snow", "cloud.snow.fill")
        case 80, 81, 82:   return ("Rain showers", "cloud.heavyrain.fill")
        case 85, 86:       return ("Snow showers", "cloud.snow.fill")
        case 95:           return ("Thunderstorm", "cloud.bolt.fill")
        case 96, 99:       return ("Thunderstorm, hail", "cloud.bolt.rain.fill")
        default:           return ("—", "cloud.fill")
        }
    }

    /// 16-point compass abbreviation for a bearing in degrees.
    static func compass(forDegrees degrees: Int) -> String {
        let points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        let normalized = ((Double(degrees).truncatingRemainder(dividingBy: 360)) + 360)
            .truncatingRemainder(dividingBy: 360)
        let index = Int((normalized / 22.5).rounded()) % points.count
        return points[index]
    }

    // Open-Meteo (with timezone=auto) returns local times like "2026-05-30T13:00".
    private static let timeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm"
        f.timeZone = TimeZone.current
        return f
    }()

    static func parseLocalTime(_ string: String) -> Date? {
        timeFormatter.date(from: string)
    }
}

// MARK: - Open-Meteo JSON

/// Hourly response for a windowed (start_date/end_date) query.
private struct WindowResponse: Decodable {
    let hourly: Hourly
    struct Hourly: Decodable {
        let time: [String]
        let temperature_2m: [Double?]
        let wind_speed_10m: [Double?]
        let weather_code: [Int?]
        let pressure_msl: [Double?]?   // optional so canned test JSON still decodes
    }
}

private struct OpenMeteoResponse: Decodable {
    let current: Current
    let hourly: Hourly
    let daily: Daily?

    struct Current: Decodable {
        let time: String
        let temperature_2m: Double
        let relative_humidity_2m: Double
        let precipitation: Double
        let weather_code: Int
        let cloud_cover: Double?       // optional so older canned test JSON still decodes
        let pressure_msl: Double       // sea-level normalized — valid at any elevation
        let wind_speed_10m: Double
        let wind_direction_10m: Double
    }

    struct Hourly: Decodable {
        let time: [String]
        let pressure_msl: [Double?]
        // Optional so the canned test JSON (pressure-only) still decodes.
        let temperature_2m: [Double?]?
        let relative_humidity_2m: [Double?]?
        let wind_speed_10m: [Double?]?
        let wind_gusts_10m: [Double?]?
        let wind_direction_10m: [Double?]?
        let dew_point_2m: [Double?]?
        let cloud_cover: [Double?]?
        let precipitation: [Double?]?
    }

    struct Daily: Decodable {
        let time: [String]
        let precipitation_sum: [Double?]
    }
}
