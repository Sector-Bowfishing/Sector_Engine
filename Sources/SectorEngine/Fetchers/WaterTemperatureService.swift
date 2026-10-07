//
//  WaterTemperatureService.swift
//  Sector — modeled lake surface water temperature
//
//  WHY THIS EXISTS. There is no free national real-time lake surface-temperature
//  API. USGS parameter 00010 is published by exactly 103 lake/reservoir sites in
//  the entire United States — Alabama and Tennessee have none, so a live query
//  for Lake Guntersville returns zero — and NOAA's buoy/satellite products cover
//  the Great Lakes and the coast only. So for nearly every water people bowfish,
//  the number the app shows is MODELED. That makes the model worth doing
//  properly.
//
//  THE MODEL. A lake does not chase air temperature; it relaxes toward its own
//  EQUILIBRIUM temperature, and it does so slowly because it has thermal mass.
//  Both halves matter, and the old version had both wrong.
//
//      T_eq[t] = Tair[t] + c0 + a·SW[t] − b·wind[t]·(1 − RH[t]/100)
//      Tw[t]   = max(32, Tw[t−1] + k·(T_eq[t] − Tw[t−1]))
//
//  Every term is physical, not a curve fit:
//    · c0 + a·SW  absorbed shortwave. A sunlit lake sits ABOVE the daily-mean
//                 air temperature; this is why the old air-only model ran cold,
//                 and why it ran coldest in summer when the sun is strongest.
//    · b·wind·(1−RH)  evaporative (latent) heat loss. Wind over dry air cools a
//                 lake hard; wind over saturated air barely cools it at all,
//                 which is why the humidity term is not optional.
//    · max(32, …) the phase change. Liquid water does not go below freezing.
//                 The old model happily predicted a 12 °F lake in North Dakota.
//    · k          thermal mass. τ = 1/k ≈ 11 days.
//
//  CALIBRATION. Fit globally against every USGS lake gauge with a usable record
//  — 17 lakes, 8,110 lake-days, Vermont to Texas to Oregon, 32 °F to 94 °F.
//  Scored by LEAVE-ONE-LAKE-OUT: the parameters are refit with a lake removed
//  and then tested on it, because Guntersville has no gauge and the numbers have
//  to work on a water the fit never saw.
//
//      held-out RMSE        6.00 °F  →  3.40 °F
//      held-out bias       −3.67 °F  →  −0.06 °F
//      days off by >5 °F        44%  →  14%
//
//  It is better on 15 of the 17 and slightly worse on two Pacific Northwest
//  lakes (Osoyoos −1.2 °F, Detroit −0.2 °F). One global parameter set, no
//  per-lake asset — a per-lake tune would score better on gauged lakes and be
//  worth nothing on the ungauged ones that are the whole point.
//
//  WHY 45 PAST DAYS. With τ ≈ 11 days the lag needs roughly 4τ to forget its
//  seed. Measured spin-up error against a fully converged run: 15 days → 1.32 °F,
//  30 → 0.29 °F, 45 → 0.05 °F. The previous 15-day window was contributing more
//  than a degree of error on its own. Any window ≥ 45 agrees to within 0.05 °F,
//  which is what lets this service and the iOS copy use different windows and
//  still produce the same number.
//
//  The gage override (when one is genuinely nearby) is handled upstream in
//  WaterLevelService; this is the always-available fallback layer.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif

/// One day of the modeled series: modeled water temp and the daily-mean air
/// temp that drove it. Air is carried so the chart can show water's lag.
struct WaterTempDay: Hashable {
    let date: Date
    let waterF: Double
    let airF: Double
    /// The provider's lake-local calendar date ("yyyy-MM-dd") for this day.
    var localDate: String? = nil
}

/// Result of the model: the current estimate plus the daily series for the chart.
struct WaterTempModel: Equatable {
    /// Modeled surface temp for today, °F.
    let currentF: Double
    /// Past ~45 days → next ~4 days, oldest → newest.
    let series: [WaterTempDay]
    /// The lake-local date `currentF` is for, and the lake's zone (IANA) — nil when unknown.
    var currentLocalDate: String? = nil
    var timeZoneIdentifier: String? = nil

    static func == (l: WaterTempModel, r: WaterTempModel) -> Bool {
        l.currentF == r.currentF && l.series == r.series
            && l.currentLocalDate == r.currentLocalDate && l.timeZoneIdentifier == r.timeZoneIdentifier
    }
}

enum WaterTemperatureService {

    // MARK: Calibration constants (see header for how these were fit)

    /// Thermal-lag constant, per day. τ = 1/k ≈ 11 days.
    static let k = 0.09
    /// Equilibrium offset, °F — the part of solar gain that isn't in `solarGainF`.
    static let equilibriumOffsetF = 5.0
    /// Absorbed shortwave, °F per MJ/m²/day.
    static let solarGainF = 0.11
    /// Evaporative cooling, °F per km/h of wind at zero humidity.
    static let evaporativeF = 1.0
    /// Offset used when the energy-balance inputs are unavailable and only air
    /// temperature is in hand. Fit the same way: RMSE 3.70 °F vs 3.25 °F for the
    /// full model — worse, but still far better than the 6.00 °F air-only-with-
    /// no-offset model this replaces.
    static let airOnlyOffsetF = 4.0
    /// Liquid water does not go below this.
    static let freezingF = 32.0

    /// Days of trailing air-temp mean used to seed the model.
    private static let seedDays = 7
    /// Past days fetched. ≥45 keeps spin-up error ≤0.05 °F — see header.
    private static let pastDays = 45

    /// The lake's equilibrium temperature for one day. Falls back to an
    /// air-plus-offset estimate when the energy terms are missing, rather than
    /// silently dropping them and reintroducing the cold bias.
    static func equilibriumF(airF: Double,
                             solarMJ: Double?,
                             windKph: Double?,
                             humidityPct: Double?) -> Double {
        guard let solarMJ, let windKph, let humidityPct else {
            return airF + airOnlyOffsetF
        }
        // Dryness drives evaporation: saturated air carries almost no latent
        // heat away no matter how hard it blows.
        let dryness = max(0, min(1, 1 - humidityPct / 100))
        return airF + equilibriumOffsetF
            + solarGainF * solarMJ
            - evaporativeF * windKph * dryness
    }

    /// Roll the first-order lag across a day series. Exposed so tests can drive
    /// the physics without a network round trip.
    static func integrate(_ days: [(date: Date, airF: Double, equilibriumF: Double)])
        -> [WaterTempDay] {
        guard !days.isEmpty else { return [] }
        let seed = days.prefix(seedDays).map(\.airF).reduce(0, +)
            / Double(min(seedDays, days.count))
        var tw = max(freezingF, seed)
        var series: [WaterTempDay] = []
        series.reserveCapacity(days.count)
        for day in days {
            tw = max(freezingF, tw + k * (day.equilibriumF - tw))
            series.append(WaterTempDay(date: day.date, waterF: tw, airF: day.airF))
        }
        return series
    }

    /// Modeled water temperature at `coordinate`, or nil if the daily air-temp
    /// history can't be fetched.
    static func model(near coordinate: CLLocationCoordinate2D) async -> WaterTempModel? {
        let items = [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", coordinate.latitude)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", coordinate.longitude)),
            URLQueryItem(name: "daily", value: "temperature_2m_mean,shortwave_radiation_sum,"
                         + "wind_speed_10m_mean,relative_humidity_2m_mean"),
            URLQueryItem(name: "past_days", value: String(pastDays)),
            URLQueryItem(name: "forecast_days", value: "4"),
            URLQueryItem(name: "temperature_unit", value: "fahrenheit"),
            URLQueryItem(name: "timezone", value: "auto"),
        ]

        guard let data = try? await WeatherService.fetchForecastData(queryItems: items),
              let decoded = try? JSONDecoder().decode(DailyMeanResponse.self, from: data),
              let means = decoded.daily.temperature_2m_mean else { return nil }

        let solar = decoded.daily.shortwave_radiation_sum
        let wind = decoded.daily.wind_speed_10m_mean
        let humidity = decoded.daily.relative_humidity_2m_mean

        let days: [(date: Date, airF: Double, equilibriumF: Double)] =
            decoded.daily.time.indices.compactMap { i in
                guard i < means.count, let airF = means[i],
                      let date = parseDay(decoded.daily.time[i]) else { return nil }
                return (date, airF, equilibriumF(airF: airF,
                                                 solarMJ: solar?[safe: i] ?? nil,
                                                 windKph: wind?[safe: i] ?? nil,
                                                 humidityPct: humidity?[safe: i] ?? nil))
            }
        guard days.count >= seedDays else { return nil }

        // Physics unchanged; each modeled day keeps the provider's lake-local date.
        let localDates: [String] = decoded.daily.time.indices.compactMap { i in
            guard i < means.count, means[i] != nil, parseDay(decoded.daily.time[i]) != nil else { return nil }
            return decoded.daily.time[i]
        }
        var series = integrate(days)
        for i in series.indices where i < localDates.count { series[i].localDate = localDates[i] }

        let zone = LakeLocalDate.timeZone(identifier: decoded.timezone, utcOffsetSeconds: decoded.utc_offset_seconds)
        guard let current = currentDay(in: series, now: Date(), lakeTimeZone: zone) else { return nil }
        var m = WaterTempModel(currentF: current.waterF, series: series)
        m.currentLocalDate = zone == nil ? nil : current.localDate
        m.timeZoneIdentifier = zone?.identifier
        return m
    }

    /// "Now" = the modeled value for the LAKE-LOCAL today: the last day whose
    /// lake-local date is not after today in the lake's zone. Never the server's
    /// calendar (Cloud Run is UTC; in a US evening that is already tomorrow).
    /// A day without a provider date is keyed by its parsed date. With no known
    /// zone the selection uses UTC and the caller reports the date as unknown.
    static func currentDay(in series: [WaterTempDay], now: Date, lakeTimeZone: TimeZone?) -> WaterTempDay? {
        let today = LakeLocalDate.string(for: now, in: lakeTimeZone ?? TimeZone(identifier: "UTC")!)
        return series.last(where: { ($0.localDate ?? dayFmt.string(from: $0.date)) <= today })
            ?? series.last
    }

    private static let dayFmt: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        f.timeZone = .current
        return f
    }()
    static func parseDay(_ s: String) -> Date? { dayFmt.date(from: s) }

    private struct DailyMeanResponse: Decodable {
        let timezone: String?
        let utc_offset_seconds: Int?
        let daily: Daily
        struct Daily: Decodable {
            let time: [String]
            let temperature_2m_mean: [Double?]?
            let shortwave_radiation_sum: [Double?]?
            let wind_speed_10m_mean: [Double?]?
            let relative_humidity_2m_mean: [Double?]?
        }
    }
}

private extension Array {
    /// A short array from the provider must not take the whole model down with
    /// an index crash — a missing day degrades to the air-only equilibrium.
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
