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

    /// The location's offset from UTC as Open-Meteo reported it — the lake's
    /// clock for "tonight" math on a UTC server.
    var utcOffsetSeconds: Int? = nil

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

final class WeatherService: Sendable {
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

    /// How long the primary gets before the fallback host is also asked.
    /// Open-Meteo normally answers in ~0.3–0.8s from Cloud Run.
    static let hedgeDelaySeconds: Double = 1.5

    private enum Attempt: Sendable {
        case primary(HostResult)
        case fallback(HostResult)
        case hedgeTimer
    }

    /// One host's answer.
    enum HostResult: Sendable {
        case body(Data)
        /// 429: over quota. Both hosts belong to Open-Meteo and share it.
        case rateLimited(retryAfter: Double?)
        case failed
    }

    /// Process-wide pause after Open-Meteo says we're over quota. Hitting it again
    /// — or its sibling host, which shares the quota — only extends the lockout
    /// and burns the daily allowance, so every weather fetch fails fast (the
    /// render degrades or 503s honestly) until Retry-After passes.
    actor RateLimitGate {
        static let shared = RateLimitGate()
        private var blockedUntil: Date?

        var isBlocked: Bool {
            guard let until = blockedUntil else { return false }
            if Date() < until { return true }
            blockedUntil = nil
            return false
        }

        func block(for seconds: Double?) {
            let pause = min(max(seconds ?? 60, 5), 3600)
            let until = Date().addingTimeInterval(pause)
            if blockedUntil.map({ until > $0 }) ?? true {
                blockedUntil = until
                Log.error("open-meteo rate limited; pausing weather fetches", ["pauseSec": .double(pause)])
            }
        }
    }

    /// Fetches `queryItems` from the primary forecast host, HEDGED onto the
    /// fallback host.
    ///
    /// History: hosts were first tried in sequence, so a primary that accepted TCP
    /// but never finished TLS (an intermittent peering issue from Cloud Run's
    /// egress) cost 15s per weather fetch and stacked into 504s. That was fixed by
    /// racing BOTH hosts on every call — which also doubled every render's
    /// Open-Meteo usage against a free-tier daily/minute quota.
    ///
    /// A hedge keeps the resilience at roughly half the calls: the fallback starts
    /// only if the primary FAILS or hasn't answered within `hedgeDelaySeconds`,
    /// and the first 2xx wins. A stalled primary now costs 1.5s, not 15s.
    static func fetchForecastData(queryItems: [URLQueryItem]) async throws -> Data {
        if await RateLimitGate.shared.isBlocked { throw WeatherError.requestFailed }

        let primary = forecastEndpoints[0], fallback = forecastEndpoints[1]
        let data: Data? = await withTaskGroup(of: Attempt.self) { group in
            group.addTask { .primary(await fetchOne(endpoint: primary, queryItems: queryItems)) }
            group.addTask {
                try? await Task.sleep(nanoseconds: UInt64(hedgeDelaySeconds * 1_000_000_000))
                return .hedgeTimer
            }
            var fallbackStarted = false
            var rateLimited = false
            func startFallback() {
                guard !fallbackStarted, !rateLimited else { return }
                fallbackStarted = true
                group.addTask { .fallback(await fetchOne(endpoint: fallback, queryItems: queryItems)) }
            }
            for await attempt in group {
                switch attempt {
                case let .primary(result), let .fallback(result):
                    switch result {
                    case let .body(body):
                        group.cancelAll()
                        return body
                    case let .rateLimited(retryAfter):
                        // Over quota: the sibling host shares it, so don't hedge.
                        rateLimited = true
                        await RateLimitGate.shared.block(for: retryAfter)
                        group.cancelAll()
                        return nil
                    case .failed:
                        startFallback()      // a fast primary failure hedges immediately
                    }
                case .hedgeTimer:
                    startFallback()          // a slow primary gets company
                }
            }
            return nil
        }
        guard let data else {
            Log.warning("open-meteo: weather fetch failed", ["hosts": .strings(forecastEndpoints)])
            throw WeatherError.requestFailed
        }
        return data
    }

    /// One endpoint attempt.
    private static func fetchOne(endpoint: String, queryItems: [URLQueryItem]) async -> HostResult {
        var components = URLComponents(string: endpoint)
        components?.queryItems = queryItems
        guard let url = components?.url else { return .failed }

        // 8s per host: with the 1.5s hedge, a success lands inside the snapshot's
        // 11s weather budget even when the primary stalls.
        guard let result = try? await HTTP.get(url, timeout: 8) else { return .failed }
        if result.status == 429 { return .rateLimited(retryAfter: result.retryAfterSeconds) }
        return result.isSuccess ? .body(result.body) : .failed
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
        let offset = decoded.utc_offset_seconds ?? 0
        var winds: [Double] = [], temps: [Double] = [], codes: [Int] = []
        var samples: [WindowHourly] = []
        for i in h.time.indices {
            guard let t = OpenMeteoTime.instant(h.time[i], utcOffsetSeconds: offset), t >= from, t <= to else { continue }
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
        // Every time in this response is the location's local wall clock; this
        // offset (from the same response) turns them into real instants.
        let offset = decoded.utc_offset_seconds ?? 0
        let now = OpenMeteoTime.instant(current.time, utcOffsetSeconds: offset) ?? Date()

        // Windowed hourly series (past 24h → next 12h) for the pressure detail chart.
        // 48 each way so the pressure sheet's 48H range has real data behind it.
        // Only what the selected range asks for is ever plotted, so the wider
        // window costs nothing on the default view.
        let history = pressureSamples(
            hourlyTimes: decoded.hourly.time,
            hourlyPressures: decoded.hourly.pressure_msl,
            now: now, pastHours: 48, futureHours: 48,
            utcOffsetSeconds: offset
        )

        // Anchor the reported "current" pressure to the hourly series at `now`, so
        // the number, the trend, the detail chart, and the score all come from ONE
        // series and can't contradict each other. Open-Meteo's `current` block is a
        // sub-hour nowcast that can sit a couple hPa off its own hourly series
        // during a front; when it did, the 3-hour tendency (computed downstream as
        // current − the hourly reading 3h ago) read "Falling" on a chart that was
        // plainly rising. Fall back to the nowcast only when no hourly sample sits
        // near now.
        let currentPressure: Double = history
            .min(by: { abs($0.date.timeIntervalSince(now)) < abs($1.date.timeIntervalSince(now)) })
            .flatMap { abs($0.date.timeIntervalSince(now)) <= 90 * 60 ? $0.hPa : nil }
            ?? current.pressure_msl

        let (trend, change) = pressureTrend(
            currentPressure: currentPressure,
            hourlyTimes: decoded.hourly.time,
            hourlyPressures: decoded.hourly.pressure_msl,
            now: now,
            lookbackHours: lookbackHours,
            utcOffsetSeconds: offset
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
            now: now, pastHours: 48, futureHours: 24,
            utcOffsetSeconds: offset
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
            // `daily.time` holds the LOCATION's local dates, so "today" and
            // "yesterday" must be the location's too. Comparing against the
            // server's UTC day counted tomorrow's forecast rain as today's every
            // US evening, once UTC had rolled past midnight.
            let today = OpenMeteoTime.localDay(now, utcOffsetSeconds: offset)
            let yesterday = OpenMeteoTime.localDay(now.addingTimeInterval(-86_400), utcOffsetSeconds: offset)
            var sum = 0.0
            for (i, t) in daily.time.enumerated() where i < daily.precipitation_sum.count {
                if t == today || t == yesterday { sum += daily.precipitation_sum[i] ?? 0 }
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
            pressure: currentPressure,
            pressureTrend: trend,
            pressureChange: change,
            cloudCover: current.cloud_cover ?? 0,
            weatherCode: effectiveCode,
            time: now,
            utcOffsetSeconds: decoded.utc_offset_seconds,
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
                                 futureHours: Int,
                                 utcOffsetSeconds: Int) -> [ConditionsHourly] {
        let lower = now.addingTimeInterval(TimeInterval(-pastHours * 3600))
        let upper = now.addingTimeInterval(TimeInterval(futureHours * 3600))
        func at(_ a: [Double?]?, _ i: Int) -> Double? {
            guard let a, i < a.count else { return nil }
            return a[i]
        }
        var samples: [ConditionsHourly] = []
        for (i, timeString) in hourlyTimes.enumerated() {
            guard let date = OpenMeteoTime.instant(timeString, utcOffsetSeconds: utcOffsetSeconds),
                  date >= lower, date <= upper else { continue }
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
                                futureHours: Int,
                                utcOffsetSeconds: Int) -> [PressureSample] {
        let lower = now.addingTimeInterval(TimeInterval(-pastHours * 3600))
        let upper = now.addingTimeInterval(TimeInterval(futureHours * 3600))
        var samples: [PressureSample] = []
        for (index, timeString) in hourlyTimes.enumerated() {
            guard index < hourlyPressures.count,
                  let hPa = hourlyPressures[index],
                  let date = OpenMeteoTime.instant(timeString, utcOffsetSeconds: utcOffsetSeconds),
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
                              lookbackHours: Int = 12,
                              utcOffsetSeconds: Int) -> (PressureTrend, Double) {
        let target = now.addingTimeInterval(TimeInterval(-lookbackHours * 3600))

        // Find the hourly sample closest to the target time that has a value.
        var best: (pressure: Double, distance: TimeInterval)?
        for (index, timeString) in hourlyTimes.enumerated() {
            guard index < hourlyPressures.count,
                  let pressure = hourlyPressures[index],
                  let date = OpenMeteoTime.instant(timeString, utcOffsetSeconds: utcOffsetSeconds) else { continue }
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

}

// MARK: - Open-Meteo JSON

/// Hourly response for a windowed (start_date/end_date) query.
private struct WindowResponse: Decodable {
    /// The location's offset from UTC; all `hourly.time` strings are local.
    let utc_offset_seconds: Int?
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
    /// The location's offset from UTC; every time string below is local.
    let utc_offset_seconds: Int?
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
