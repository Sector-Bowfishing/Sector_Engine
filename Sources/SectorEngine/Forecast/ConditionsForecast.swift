//
//  ConditionsForecast.swift
//  Sector
//
//  Tonight's hourly window + the 7-night outlook. As of the v2 consolidation
//  these are driven by the SAME engine as the hero gauge — `ConditionsAggregator`
//  fed by `ConditionsInputBuilder` — so the storm sanitizer, gates, seeability
//  ceiling, spawn, clarity, water-temp and confidence all apply here too. There
//  is no longer a second, independent scoring path.
//
//    • 7-night outlook: one full `ConditionsAggregator.evaluate` per evening,
//      with that night's weather + astronomy overriding a shared base input.
//    • Tonight's curve: the night's real score sets the magnitude; a per-hour
//      "shootability" envelope (daylight/twilight × moon-at-hour × wind × active
//      weather) shapes WHEN across the night. Because the envelope is ≤ 1, no
//      hour can ever exceed the night's gauge score — a gate-capped night can
//      never show a green PRIME window.
//
//  Source: Open-Meteo hourly/daily (wind/cloud/precip/weather-code + sun times)
//  plus the same USGS water readings the gauge uses.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

// MARK: - Output models

/// One hour of tonight's conditions curve.
struct HourScore: Identifiable, Equatable {
    let date: Date
    let score: Int            // 0...100
    var id: Date { date }
}

/// Tonight's window derived from the hourly curve.
struct TonightWindow: Equatable {
    let hours: [HourScore]    // across the 6 PM → 6 AM display range
    let windowStart: Date?    // first hour of the contiguous prime run
    let windowEnd: Date?      // last hour of the prime run
    let peak: Date?           // best REMAINING hour (>= now), nil if the night's done
    let headline: String      // "Peak 10:40 PM" / "Peak: on now" / "Winding down" / "Night's over"
    let sunset: Date?
    let sunrise: Date?
    let displayStart: Date    // 6 PM tonight (or the current hour if daytime)
    let displayEnd: Date      // 6 AM tomorrow

    /// 5 evenly-spaced short time labels across the display range (e.g. 12P · 9P · 6A).
    var tickLabels: [String] {
        let total = displayEnd.timeIntervalSince(displayStart)
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "ha"
        return (0...4).map { i in
            let t = displayStart.addingTimeInterval(total * Double(i) / 4)
            return f.string(from: t)
                .replacingOccurrences(of: "AM", with: "A")
                .replacingOccurrences(of: "PM", with: "P")
        }
    }
}

/// One contributing factor in a night's score — drives the breakdown sheet.
struct ScoreFactor: Equatable {
    let key: String      // FactorKey rawValue: "clarity" | "spawn" | "darkness" | …
    let detail: String   // human value, e.g. "74% lit", "3 mph"
    let sub: Int         // 0...100 normalized sub-score
    let weight: Int      // active (regime) weight, percent
}

/// One hour of the night-detail ribbon (8 PM → 5 AM). `score` is the engine
/// evaluated at that hour's wind/sky + the moon's altitude then, so the shape
/// shows the score jumping when the moon sets. `fogRisk`: 0 none, 1 low, 2 high.
struct HourPoint: Equatable {
    let hour: Date
    let score: Int
    let windMph: Double
    let moonUp: Bool
    let fogRisk: Int
}

struct NightScore: Identifiable, Equatable {
    let date: Date            // the evening's date
    let score: Int            // 0...100 (same engine as the gauge)
    let moonIllumination: Double  // 0...1
    let windMax: Double       // mph (night average)
    let weatherCode: Int      // sanitized WMO code
    let precip: Double        // inches (daily sum)
    let precipProbability: Int?  // 0...100 % chance of rain; nil when unknown
    let factors: [ScoreFactor]
    let confidence: Int       // 0...100 — drives the far-out fade
    let regime: ConditionsRegime
    let topReasons: [String]  // why the score is what it is (incl. any cap)
    /// Hour-by-hour ribbon across the fishing window; empty if not computed.
    let hourly: [HourPoint]
    /// Moonset within the night window, if the moon sets while it's dark.
    let moonset: Date?
    var id: Date { date }

    init(date: Date, score: Int, moonIllumination: Double, windMax: Double,
         weatherCode: Int, precip: Double, precipProbability: Int? = nil,
         factors: [ScoreFactor],
         confidence: Int = 100, regime: ConditionsRegime = .normal, topReasons: [String] = [],
         hourly: [HourPoint] = [], moonset: Date? = nil) {
        self.date = date; self.score = score; self.moonIllumination = moonIllumination
        self.windMax = windMax; self.weatherCode = weatherCode; self.precip = precip
        self.precipProbability = precipProbability
        self.factors = factors; self.confidence = confidence; self.regime = regime
        self.topReasons = topReasons
        self.hourly = hourly; self.moonset = moonset
    }

    /// Banding aligned with the gauge (ConditionsBand: Prime 80 / Good 65 / Fair 50).
    var rating: BowfishingConditionsResult.Rating {
        switch score {
        case 80...:   return .prime
        case 65..<80: return .good
        case 50..<65: return .fair
        default:      return .poor
        }
    }
    var confidenceBand: ConfidenceBand { ConfidenceBand(score: confidence) }
}

struct ConditionsForecast: Equatable {
    let tonight: TonightWindow?
    let nights: [NightScore]
}

// MARK: - Server forecast cache

/// Cross-request cache for the RAW Open-Meteo 7-night download — not for the
/// computed forecast.
///
/// It used to cache the computed Tonight window + nights for 30 minutes, built
/// from whatever snapshot existed then, while the gauge in the same response came
/// from a snapshot at most 5 minutes old. One payload could show two different
/// "tonight" scores, and after local midnight a cached Tonight described a night
/// that had already ended. Now only the network download is cached; every render
/// recomputes Tonight and the nights from ITS OWN inputs and clock (see
/// `SectorEngineAPI.conditions`), which is cheap now that it runs off the main
/// actor. Keyed at ~100 m like the snapshot and response caches, bounded, and a
/// failed download is remembered for a minute.
enum ForecastResponseCache {
    private static let cache = SingleFlightCache<String, ForecastResponse>(
        ttl: 30 * 60, failureTTL: 60, maxEntries: 2_000)

    /// - Parameter force: pull-to-refresh — skip the cache read.
    static func response(for coordinate: CLLocationCoordinate2D, force: Bool = false) async -> ForecastResponse? {
        let key = String(format: "%.3f,%.3f", coordinate.latitude, coordinate.longitude)
        return await cache.value(for: key, force: force) {
            try? await ConditionsForecastService.fetchForecastResponse(coordinate)
        }
    }
}

// MARK: - Service

/// The 7-night forecast computation. A plain namespace with no isolation.
///
/// This used to be the iOS app's `@MainActor` ObservableObject, carried over
/// with its UI state (`@Published` forecasts, load states, loadIfNeeded /
/// refresh). The server never used any of that — only these static functions —
/// but the class-level `@MainActor` made every render's forecast decode and
/// re-score hop to the one main thread, so concurrent renders computed their
/// 7-night outlooks single-file. As a nonisolated enum they run in parallel.
enum ConditionsForecastService {
    // MARK: Fetch

    /// The raw Open-Meteo hourly/daily download behind Tonight and the 7-night
    /// outlook. Cached by `ForecastResponseCache`; the render computes the forecast
    /// from it with its own inputs (see `SectorEngineAPI.conditions`).
    static func fetchForecastResponse(_ coordinate: CLLocationCoordinate2D) async throws -> ForecastResponse {
        // Goes through WeatherService.fetchForecastData, which fails fast (15s)
        // per host and falls back to a sibling Open-Meteo instance when the
        // primary is unreachable (e.g. carrier ↔ Hetzner peering issues).
        let data = try await WeatherService.fetchForecastData(queryItems: [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", coordinate.latitude)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", coordinate.longitude)),
            URLQueryItem(name: "hourly", value: "wind_speed_10m,cloud_cover,precipitation,weather_code,relative_humidity_2m"),
            URLQueryItem(name: "daily", value: "sunrise,sunset,wind_speed_10m_max,weather_code,precipitation_sum,precipitation_probability_max,cloud_cover_mean"),
            URLQueryItem(name: "past_days", value: "1"),
            URLQueryItem(name: "forecast_days", value: "8"),
            URLQueryItem(name: "wind_speed_unit", value: "mph"),
            URLQueryItem(name: "precipitation_unit", value: "inch"),
            URLQueryItem(name: "timezone", value: "auto"),
        ])
        return try JSONDecoder().decode(ForecastResponse.self, from: data)
    }

    // MARK: Compute

    struct HourSample { let date: Date; let wind: Double; let cloud: Double; let precip: Double; let code: Int; let humidity: Double }

    static func compute(r: ForecastResponse, base: ConditionsInput,
                        coordinate: CLLocationCoordinate2D, now: Date = Date(),
                        generation: DamGeneration? = nil,
                        waterTempModel: WaterTempModel? = nil,
                        config: ConditionsConfig = .default) -> ConditionsForecast {
        // All local-clock reasoning ("6 PM tonight", "today") happens in the LAKE's
        // zone, and every hourly sample is a real instant — see OpenMeteoTime.
        // This used Calendar.current + a TimeZone.current parse: UTC on Cloud Run,
        // which put the Tonight window at 1 PM–1 AM CDT.
        let offset = r.utc_offset_seconds ?? 0
        let cal = OpenMeteoTime.calendar(utcOffsetSeconds: offset)

        // Index hourly samples; sanitize each weather code against its own precip+cloud.
        var hourly: [HourSample] = []
        for (i, t) in r.hourly.time.enumerated() {
            guard let d = OpenMeteoTime.instant(t, utcOffsetSeconds: offset) else { continue }
            let wind = (r.hourly.wind_speed_10m[safe: i] ?? nil) ?? 0
            let cloud = (r.hourly.cloud_cover[safe: i] ?? nil) ?? 0
            let precip = (r.hourly.precipitation[safe: i] ?? nil) ?? 0
            let rawCode = (r.hourly.weather_code[safe: i] ?? nil) ?? 0
            let code = WeatherService.sanitizedWeatherCode(rawCode, precipitation: precip, cloudCover: cloud)
            let humidity = (r.hourly.relative_humidity_2m?[safe: i] ?? nil) ?? 0
            hourly.append(HourSample(date: d, wind: wind, cloud: cloud, precip: precip, code: code, humidity: humidity))
        }

        let tonight = buildTonight(base: base, hourly: hourly, coordinate: coordinate,
                                   now: now, cal: cal, generation: generation, config: config)
        let nights = buildNights(r: r, base: base, hourly: hourly, coordinate: coordinate,
                                 now: now, cal: cal, waterTempModel: waterTempModel, config: config)
        return ConditionsForecast(tonight: tonight, nights: nights)
    }

    // MARK: Tonight's window

    private static func buildTonight(base: ConditionsInput, hourly: [HourSample],
                                     coordinate: CLLocationCoordinate2D,
                                     now: Date, cal: Calendar,
                                     generation: DamGeneration? = nil,
                                     config: ConditionsConfig) -> TonightWindow? {
        // Window runs 6 PM → next 6 AM; pull the start back to the current hour
        // during the day so "Now" is always on the chart.
        var sixComps = cal.dateComponents([.year, .month, .day], from: now)
        sixComps.hour = 6
        guard let sixAMToday = cal.date(from: sixComps) else { return nil }
        let windowEnd = sixAMToday > now ? sixAMToday : (cal.date(byAdding: .day, value: 1, to: sixAMToday) ?? sixAMToday)
        guard let windowStart = cal.date(byAdding: .hour, value: -12, to: windowEnd) else { return nil }
        let nowComps = cal.dateComponents([.year, .month, .day, .hour], from: now)
        let nowHour = cal.date(from: nowComps) ?? now
        let displayStart = Swift.min(windowStart, nowHour)
        let displayEnd = windowEnd

        // Sun times anchored to the window's own endpoints: the sunset near the
        // start of the display range and the sunrise near its end (tomorrow
        // morning). Using base.sunrise would give THIS morning's sunrise, which
        // sits before every night hour and would zero out the darkness ramp.
        //
        // Astronomy picks the day by its UTC date, so it's asked about LOCAL NOON
        // of each day: noon falls on the same UTC date as the local date for every
        // US zone, whereas 6 PM Pacific is already tomorrow in UTC and would
        // return tomorrow's sunset.
        let lat = coordinate.latitude, lon = coordinate.longitude
        let sunEventsStart = Astronomy.sunEvents(on: Self.localNoon(of: displayStart, cal: cal), lat: lat, lon: lon)
        let sunset = sunEventsStart.sunset ?? base.sunset
        let fullDark = sunEventsStart.astronomicalDusk    // true dark; ramp anchor
        let sunrise = Astronomy.sunEvents(on: Self.localNoon(of: displayEnd, cal: cal), lat: lat, lon: lon).sunrise
            ?? base.sunrise

        // The night's real score sets the ceiling/magnitude for the whole curve.
        let nightScore = Double(ConditionsAggregator.evaluate(base, config: config).score)

        let pts = hourly
            .filter { $0.date >= displayStart && $0.date <= displayEnd }
            .map { h -> HourScore in
                let env = timeEnvelope(hour: h, base: base, sunset: sunset, sunrise: sunrise,
                                       fullDark: fullDark, generation: generation, config: config)
                return HourScore(date: h.date, score: Int((nightScore * env).rounded()).clampedScore)
            }
        guard !pts.isEmpty else { return nil }

        // Best band = the sustained top of the night: hours within ~15% of the
        // night's OWN peak. Relative (not a fixed 60) so a Fair night still surfaces
        // its best stretch; a flat, genuinely poor night (peak < 40) has none.
        let peakScore = pts.map(\.score).max() ?? 0
        let (wStart, wEnd) = peakScore >= 40
            ? longestRun(in: pts, threshold: Int((Double(peakScore) * 0.85).rounded()))
            : (nil, nil)

        // Peak + headline are RELATIVE TO NOW — never headline an hour already gone.
        let remaining = pts.filter { $0.date >= nowHour }
        let bestRemaining = remaining.max { $0.score < $1.score }
        let nightPeak = pts.max { $0.score < $1.score }
        let peak = bestRemaining?.date
        let headline = headlineFor(bestRemaining: bestRemaining, nightPeak: nightPeak,
                                   nowHour: nowHour, cal: cal)

        return TonightWindow(hours: pts, windowStart: wStart, windowEnd: wEnd, peak: peak,
                             headline: headline, sunset: sunset, sunrise: sunrise,
                             displayStart: displayStart, displayEnd: displayEnd)
    }

    /// Noon on the local day containing `date` — a date whose UTC day matches the
    /// lake's local day, which is what `Astronomy` keys its day on.
    static func localNoon(of date: Date, cal: Calendar) -> Date {
        var comps = cal.dateComponents([.year, .month, .day], from: date)
        comps.hour = 12
        return cal.date(from: comps) ?? date
    }

    private static func headlineFor(bestRemaining: HourScore?, nightPeak: HourScore?,
                                    nowHour: Date, cal: Calendar) -> String {
        guard let best = bestRemaining else { return "Night's over" }
        // The best remaining hour is still ahead → name when to be out, regardless
        // of how high the night tops out. A modest night still has a best time; it
        // is NOT "winding down" before the good hours have even started.
        if !cal.isDate(best.date, equalTo: nowHour, toGranularity: .hour) {
            // Formatted in the LAKE's zone. A shared formatter defaulted to the
            // server's zone (UTC), so a 9 PM peak read "Peak 2:00 AM".
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX")
            f.dateFormat = "h:mm a"
            f.timeZone = cal.timeZone
            return "Peak \(f.string(from: best.date))"
        }
        // The current hour is the best that's left. Only call it "winding down" once
        // the night's real peak is already behind us and what remains is lower.
        if let np = nightPeak, np.date < nowHour, np.score > best.score {
            return "Winding down"
        }
        return "Peak: on now"
    }

    /// Per-hour "can I shoot this hour?" envelope in [0,1]: daylight/twilight ×
    /// moon-at-hour × surface-calm-vs-baseline × active-weather-vs-baseline ×
    /// generation-current. Multiplying the night score by this shapes WHEN across
    /// the night and guarantees no hour exceeds the night's gauge score.
    ///
    /// Wind and weather are expressed RELATIVE to the night baseline the gauge
    /// already scored, not as absolute seeability terms — otherwise they'd be
    /// double-charged (the seeability ceiling in the aggregator already docked
    /// the night for its average wind/weather), making the window's peak fall
    /// below the hero gauge on any night that isn't dead calm.
    private static func timeEnvelope(hour h: HourSample, base: ConditionsInput,
                                     sunset: Date?, sunrise: Date?,
                                     fullDark: Date? = nil,
                                     generation: DamGeneration? = nil,
                                     config: ConditionsConfig) -> Double {
        let dark = darkness(at: h.date, sunset: sunset, sunrise: sunrise, fullDark: fullDark)

        // Moon presence at this specific hour (a late-rising moon leaves the early
        // window dark), softened by cloud the same way the darkness factor does.
        let illum = (base.moonIllumPct / 100).clamped01
        let altDeg = Astronomy.moonAltitudeDeg(at: h.date, lat: base.latitude, lon: base.longitude)
        let presence = Swift.max(0, sin(altDeg * .pi / 180))
        let cloudFactor = ((h.cloud - config.darkness.cloudKneePct) / config.darkness.cloudSpanPct).clamped01
        let ruralBlocking = 1 - 0.8 * base.cityGlowFactor.clamped01
        let cloudCancel = (cloudFactor * ruralBlocking).clamped01
        let moonDark = (1 - illum * presence * (1 - cloudCancel)).clamped01

        // Wind + weather RELATIVE to the night's baseline (what the gauge scored).
        // 1.0 when this hour matches the baseline; < 1 only when it's worse — so
        // the window re-weights WHEN without re-subtracting the average.
        let windCurve = config.seeability.windCurve.map { ($0.mph, $0.factor) }
        let baseWind = interp(base.windMph, curve: windCurve)
        let windEnv = baseWind > 0.001 ? Swift.min(1, interp(h.wind, curve: windCurve) / baseWind) : 1
        let baseWx = config.seeability.weatherComponent[base.weatherCode] ?? config.seeability.defaultWeatherComponent
        let hourWx = config.seeability.weatherComponent[h.code] ?? config.seeability.defaultWeatherComponent
        let weatherEnv = baseWx > 0.001 ? Swift.min(1, hourWx / baseWx) : 1

        // Generation current, TAILWATERS ONLY: heavy flow (dangerous, muddy, fast)
        // collapses the window for those hours; moderate flow stacks fish and
        // settled water is clear — both fine, so they don't dip. On a RESERVOIR
        // the release doesn't blow out the water (CurrentFactor only nudges it),
        // so the window isn't reshaped there. Only when a forward schedule
        // actually covers the hour.
        let currentEnv: Double = {
            guard base.isTailwater,
                  let g = generation, g.hasSchedule,
                  let units = g.generators(at: h.date) else { return 1 }
            return units >= 3 ? 0.4 : 1
        }()

        return (dark * moonDark * windEnv * weatherEnv * currentEnv).clamped01
    }

    /// Daylight = 0, full dark = 1, ramped through twilight at each end. Full dark
    /// prefers astronomical dusk (passed in) and falls back to sunset + 80 min, so
    /// tonight's ramp matches the 7-night outlook (which uses astronomical dusk).
    private static func darkness(at date: Date, sunset: Date?, sunrise: Date?,
                                 fullDark fullDarkIn: Date? = nil) -> Double {
        guard let sunset, let sunrise else { return 0.5 }
        let fullDark = fullDarkIn ?? sunset.addingTimeInterval(80 * 60)
        let dawnTwilight: TimeInterval = 80 * 60
        let dawnStart = sunrise.addingTimeInterval(-dawnTwilight)
        if date <= sunset || date >= sunrise { return 0 }
        if date >= fullDark && date <= dawnStart { return 1 }
        if date < fullDark {
            let span = fullDark.timeIntervalSince(sunset)
            return span > 0 ? Swift.max(0, date.timeIntervalSince(sunset) / span) : 1
        }
        return Swift.max(0, sunrise.timeIntervalSince(date) / dawnTwilight)
    }

    // MARK: 7-night outlook — full engine per night

    private static func buildNights(r: ForecastResponse, base: ConditionsInput, hourly: [HourSample],
                                    coordinate: CLLocationCoordinate2D,
                                    now: Date, cal: Calendar,
                                    waterTempModel: WaterTempModel? = nil,
                                    config: ConditionsConfig) -> [NightScore] {
        var nights: [NightScore] = []
        let lat = coordinate.latitude, lon = coordinate.longitude

        // `past_days=1` puts yesterday at index 0 — start at the LOCATION's local
        // today. Open-Meteo's `daily.time` is in the location's local dates, but
        // `.current` is UTC on Cloud Run — so in a US evening (UTC already rolled
        // to tomorrow) this picked tomorrow's date and the outlook skipped tonight,
        // starting a day ahead. Render `now` in the location's own timezone
        // (Open-Meteo's utc_offset) so the comparison is local-vs-local.
        let locationTZ = TimeZone(secondsFromGMT: r.utc_offset_seconds ?? 0) ?? .current
        let todayStr: String = {
            let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX")
            f.dateFormat = "yyyy-MM-dd"; f.timeZone = locationTZ
            return f.string(from: now)
        }()
        let startIdx = r.daily.time.firstIndex(where: { $0 >= todayStr }) ?? 0
        let endIdx = Swift.min(startIdx + 7, r.daily.time.count)
        guard startIdx < endIdx else { return [] }

        let offset = r.utc_offset_seconds ?? 0
        for i in startIdx..<endIdx {
            // 9 PM at the lake, as a real instant — same frame as the hourly samples.
            guard let evening = OpenMeteoTime.instant(r.daily.time[i] + "T21:00", utcOffsetSeconds: offset),
                  let dayNoon = OpenMeteoTime.instant(r.daily.time[i] + "T12:00", utcOffsetSeconds: offset)
            else { continue }

            // Daily % chance of rain (nil when the host omits it or has no POP).
            let pop = r.daily.precipitation_probability_max?[safe: i] ?? nil

            // TONIGHT is scored from the SAME live `base` the hero gauge and the
            // lake score strip use — not night-averaged forecast weather — so the
            // 7-night mini-card, the outlook sheet, the score strip and the gauge
            // all show ONE tonight number. (Previously tonight used evaluate(ni)
            // with averaged wind/cloud/code, disagreeing with the gauge, which the
            // sheet then papered over with a wrong-location graft.) Future nights
            // below keep the daily-forecast model — there's no live reading for a
            // future night.
            if i == startIdx {
                let res = ConditionsAggregator.evaluate(base, config: config)
                let factors = res.factors.map {
                    ScoreFactor(key: $0.key.rawValue, detail: $0.label, sub: $0.score, weight: $0.weightPct)
                }
                let ribbon = buildRibbon(evening: evening, ni: base, hourly: hourly,
                                         coordinate: coordinate, config: config)
                nights.append(NightScore(date: evening, score: res.score,
                                         moonIllumination: base.moonIllumPct / 100,
                                         windMax: base.windMph, weatherCode: base.weatherCode,
                                         precip: base.precipitationInchNow, precipProbability: pop,
                                         factors: factors, confidence: res.confidence,
                                         regime: res.regime, topReasons: res.topReasons,
                                         hourly: ribbon.points, moonset: ribbon.moonset))
                continue
            }

            let dailyMax = (r.daily.wind_speed_10m_max[safe: i] ?? nil) ?? 0
            let precip = (r.daily.precipitation_sum[safe: i] ?? nil) ?? 0
            let dailyCloud = (r.daily.cloud_cover_mean?[safe: i] ?? nil) ?? nil

            // Average wind + cloud over THIS night's fishing hours from the hourly feed.
            let eveningStart = cal.date(byAdding: .hour, value: -3, to: evening) ?? evening  // ~18:00
            let eveningEnd = cal.date(byAdding: .hour, value: 9, to: evening) ?? evening     // ~06:00 next
            let nightHours = hourly.filter { $0.date >= eveningStart && $0.date <= eveningEnd }
            let wind = nightHours.isEmpty ? dailyMax : nightHours.map(\.wind).reduce(0, +) / Double(nightHours.count)
            let cloud = nightHours.isEmpty
                ? (dailyCloud ?? 0)
                : nightHours.map(\.cloud).reduce(0, +) / Double(nightHours.count)

            let rawCode = (r.daily.weather_code[safe: i] ?? nil) ?? 0
            let code = WeatherService.sanitizedWeatherCode(rawCode, precipitation: precip, cloudCover: cloud)

            // Recent-rain window for THIS night — the same multi-day sum the gauge
            // uses, rebuilt from the daily feed (that day + the prior 2) so future
            // rain muddies future clarity. Tonight keeps the observed history when
            // it's larger: the forecast feed only reaches one day back.
            let rainWindow = (Swift.max(0, i - 2)...i).reduce(0.0) { sum, j in
                sum + ((r.daily.precipitation_sum[safe: j] ?? nil) ?? 0)
            }
            let recentRain = (i == startIdx) ? Swift.max(base.rainLast48hIn, rainWindow) : rainWindow

            // Astronomy for this specific evening — keyed on local noon of that day
            // (Astronomy picks the day by UTC date; see localNoon).
            let sun = Astronomy.sunEvents(on: dayNoon, lat: lat, lon: lon)
            let illum = Astronomy.moonIllumination(on: evening)
            let winStart = sun.astronomicalDusk ?? sun.sunset?.addingTimeInterval(80 * 60)
            // `sun.sunrise` is THIS evening's morning sunrise, which falls BEFORE
            // the night's dusk — so the naive window ends ~15 h before it starts,
            // and moonAltitudeFraction's `guard end > start` collapses to a single
            // dusk sample (bright-moon nights then read dark). Roll the end forward
            // a day so the window spans dusk→dawn, exactly like the tonight path and
            // ConditionsInputBuilder. Fixes the 7-night outlook's moon column.
            let rawWinEnd = sun.sunrise ?? winStart?.addingTimeInterval(8 * 3600)
            let winEnd: Date? = {
                guard let s = winStart, let e = rawWinEnd else { return rawWinEnd }
                return e > s ? e : e.addingTimeInterval(24 * 3600)
            }()
            let moonAlt: Double = (winStart != nil && winEnd != nil)
                ? Astronomy.moonAltitudeFraction(from: winStart!, to: winEnd!, lat: lat, lon: lon)
                : 0

            // Copy the shared base and override the time-varying fields for this night.
            var ni = base
            ni.date = evening
            ni.windMph = wind
            ni.cloudPct = cloud
            ni.weatherCode = code
            ni.precipitationInchNow = precip
            ni.rainLast48hIn = recentRain
            ni.sunset = sun.sunset; ni.sunrise = sun.sunrise
            ni.civilDusk = sun.civilDusk; ni.astronomicalDusk = sun.astronomicalDusk
            ni.moonIllumPct = illum * 100
            ni.moonrise = nil; ni.moonset = nil
            ni.moonAltitudeAtWindow = moonAlt
            ni.windowStart = winStart; ni.windowEnd = winEnd
            ni.forecastDayIndex = i - startIdx
            // Per-FUTURE-night temperature from the modeled series: the water
            // temp for THAT day (a cold front on night +4 really does cool the
            // water; a warming trend can push night +3 across the spawn
            // threshold) and the daily-mean air carried with it (drives the
            // sky-comfort term). Without this every night reused tonight's temp.
            // Tonight (index 0) keeps base, which may be a live gage. Nights
            // beyond the model's ~4-day reach fall back to tonight's values.
            // Model series dates are the location's local date labels stored at UTC
            // midnight, so match on that label, not on an instant comparison.
            if ni.forecastDayIndex > 0, let model = waterTempModel,
               let day = model.series.first(where: { Self.utcDayLabel($0.date) == r.daily.time[i] }) {
                ni.waterTempF = day.waterF
                ni.airTempF = day.airF
                ni.waterTempEstimated = true
            }
            // TVA only publishes today's schedule, so a resolved generation
            // level belongs to tonight alone — carrying it forward would state
            // tomorrow's release as fact. Later nights fall back to the
            // discharge trend (and take the no-forecast confidence hit).
            if ni.forecastDayIndex > 0 {
                ni.generationLevel = nil
                ni.hasGenerationForecast = false
            }

            let res = ConditionsAggregator.evaluate(ni, config: config)
            let factors = res.factors.map {
                ScoreFactor(key: $0.key.rawValue, detail: $0.label, sub: $0.score, weight: $0.weightPct)
            }
            let ribbon = buildRibbon(evening: evening, ni: ni, hourly: hourly,
                                     coordinate: coordinate, config: config)
            nights.append(NightScore(date: evening, score: res.score, moonIllumination: illum,
                                     windMax: wind, weatherCode: code, precip: precip,
                                     precipProbability: pop,
                                     factors: factors, confidence: res.confidence, regime: res.regime,
                                     topReasons: res.topReasons,
                                     hourly: ribbon.points, moonset: ribbon.moonset))
        }
        return nights
    }

    // MARK: Night ribbon (hour-by-hour)

    /// The night-detail ribbon: 10 hours 8 PM → 5 AM, each scored by the engine at
    /// that hour's wind/sky and the moon's altitude then — so the score visibly
    /// jumps when the moon sets — plus the exact moonset inside the window.
    /// `ni` carries the night's slow-moving inputs (clarity, temp, level, regime).
    private static func buildRibbon(evening: Date, ni: ConditionsInput, hourly: [HourSample],
                                    coordinate: CLLocationCoordinate2D,
                                    config: ConditionsConfig) -> (points: [HourPoint], moonset: Date?) {
        let lat = coordinate.latitude, lon = coordinate.longitude
        // `evening` and the HourSamples are both real instants now (OpenMeteoTime),
        // so one clock serves weather matching, astronomy and the emitted times.
        // (This used to juggle a "naive" wall-clock frame for the samples and a
        // "true" frame for the moon, because the parse was in the server's zone.)
        let trueStart = evening.addingTimeInterval(-3600)                  // 8 PM local

        func sample(near t: Date) -> HourSample? {
            guard let nearest = hourly.min(by: {
                abs($0.date.timeIntervalSince(t)) < abs($1.date.timeIntervalSince(t))
            }) else { return nil }
            return abs(nearest.date.timeIntervalSince(t)) <= 45 * 60 ? nearest : nil
        }

        var points: [HourPoint] = []
        for h in 0..<10 {
            let trueHourStart = trueStart.addingTimeInterval(Double(h) * 3600)
            let trueMid = trueHourStart.addingTimeInterval(1800)
            let s = sample(near: trueMid)
            let wind = s?.wind ?? ni.windMph
            let cloud = s?.cloud ?? ni.cloudPct
            let precip = s?.precip ?? 0
            let humidity = s?.humidity ?? ni.humidityPct
            let code = s.map { WeatherService.sanitizedWeatherCode($0.code, precipitation: precip, cloudCover: cloud) }
                ?? ni.weatherCode

            let altDeg = Astronomy.moonAltitudeDeg(at: trueMid, lat: lat, lon: lon)
            let moonUp = altDeg > 0

            var hi = ni
            hi.date = trueMid
            hi.windMph = wind
            hi.cloudPct = cloud
            hi.weatherCode = code
            hi.humidityPct = humidity
            hi.precipitationInchNow = precip
            hi.moonAltitudeAtWindow = Astronomy.moonAltitudeFraction(from: trueHourStart, to: trueHourStart.addingTimeInterval(3600), lat: lat, lon: lon)
            hi.windowStart = trueHourStart
            hi.windowEnd = trueHourStart.addingTimeInterval(3600)
            let score = ConditionsAggregator.evaluate(hi, config: config).score

            // Fog risk — radiation fog forms on calm, clear, humid nights, mostly
            // after midnight. WMO 45/48 is reported fog (high). Otherwise a
            // dewpoint-proxy from humidity + a calm/clear/late gate.
            let late = h >= 5     // 1 AM and after
            let fogRisk: Int
            if code == 45 || code == 48 { fogRisk = 2 }
            else if humidity >= 92 && wind < 4 && cloud < 45 && late { fogRisk = 2 }
            else if humidity >= 86 && wind < 6 && cloud < 60 && h >= 4 { fogRisk = 1 }
            else { fogRisk = 0 }

            points.append(HourPoint(hour: trueHourStart, score: score, windMph: wind, moonUp: moonUp, fogRisk: fogRisk))
        }

        // Moonset inside the window: first descending zero-crossing of altitude,
        // scanned in TRUE time so the tick lands at the real moment.
        var moonset: Date?
        let step: TimeInterval = 5 * 60
        var prevT = trueStart
        var prevAlt = Astronomy.moonAltitudeDeg(at: prevT, lat: lat, lon: lon)
        var t = trueStart.addingTimeInterval(step)
        let end = trueStart.addingTimeInterval(10 * 3600)
        while t <= end {
            let alt = Astronomy.moonAltitudeDeg(at: t, lat: lat, lon: lon)
            if prevAlt > 0, alt <= 0 {
                let frac = prevAlt / (prevAlt - alt)   // 0…1 between prevT and t
                moonset = prevT.addingTimeInterval(step * frac)
                break
            }
            prevT = t; prevAlt = alt; t = t.addingTimeInterval(step)
        }
        return (points, moonset)
    }

    // MARK: Helpers

    /// Illuminated fraction 0 (new) … 1 (full). Kept for the window sheet's moon
    /// line; delegates to the engine ephemeris so there's one source of moon math.
    static func illumination(on date: Date) -> Double {
        Astronomy.moonIllumination(on: date)
    }

    /// "yyyy-MM-dd" for a date stored at UTC midnight of a local date label.
    private static func utcDayLabel(_ date: Date) -> String {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(secondsFromGMT: 0)!
        let c = cal.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    /// Piecewise-linear lookup over ascending (x, factor) breakpoints; clamps ends.
    private static func interp(_ x: Double, curve: [(Double, Double)]) -> Double {
        guard let first = curve.first else { return 1 }
        if x <= first.0 { return first.1 }
        for i in 1..<curve.count {
            let lo = curve[i - 1], hi = curve[i]
            if x <= hi.0 {
                let t = (x - lo.0) / (hi.0 - lo.0)
                return lo.1 + t * (hi.1 - lo.1)
            }
        }
        return curve.last!.1
    }

    /// Longest contiguous run of hours at/above `threshold`; returns its endpoints.
    private static func longestRun(in pts: [HourScore], threshold: Int) -> (Date?, Date?) {
        var bestStart: Int?, bestLen = 0
        var curStart: Int?, curLen = 0
        for (i, p) in pts.enumerated() {
            if p.score >= threshold {
                if curStart == nil { curStart = i; curLen = 0 }
                curLen += 1
                if curLen > bestLen { bestLen = curLen; bestStart = curStart }
            } else {
                curStart = nil; curLen = 0
            }
        }
        guard let s = bestStart else { return (nil, nil) }
        return (pts[s].date, pts[s + bestLen - 1].date)
    }
}

private extension Int {
    var clampedScore: Int { Swift.min(100, Swift.max(0, self)) }
}

// MARK: - JSON

struct ForecastResponse: Decodable {
    let hourly: Hourly
    let daily: Daily
    // Lake's offset from UTC (timezone=auto). The hourly/daily strings are the
    // lake's local wall clock; `OpenMeteoTime.instant` uses this to turn each one
    // into a real instant, and `OpenMeteoTime.calendar` to do "6 PM tonight" math
    // in the lake's zone.
    // NOTE: `var`, not `let` — a `let` with a default is dropped from synthesized
    // Decodable (immutable + pre-initialized), so it would never read the JSON.
    var utc_offset_seconds: Int? = nil

    struct Hourly: Decodable {
        let time: [String]
        let wind_speed_10m: [Double?]
        let cloud_cover: [Double?]
        let precipitation: [Double?]
        let weather_code: [Int?]
        // `var` (not `let`) so the default doesn't drop it from synthesized
        // Decodable; drives the ribbon's fog-risk proxy.
        var relative_humidity_2m: [Double?]? = nil
    }
    struct Daily: Decodable {
        let time: [String]
        let sunrise: [String]
        let sunset: [String]
        let wind_speed_10m_max: [Double?]
        let weather_code: [Int?]
        let precipitation_sum: [Double?]
        // % chance of measurable rain that day. `var` (not `let`) so the default
        // doesn't drop it from synthesized Decodable; nil elements are common.
        var precipitation_probability_max: [Int?]? = nil
        let cloud_cover_mean: [Double?]?
    }
}

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
