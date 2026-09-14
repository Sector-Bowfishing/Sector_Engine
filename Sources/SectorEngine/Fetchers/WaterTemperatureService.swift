//
//  WaterTemperatureService.swift
//  Sector — modeled lake surface water temperature
//
//  WHY THIS EXISTS. There is no free national real-time lake surface-temperature
//  API. USGS gages (parameter 00010) exist on only a handful of US lakes — a
//  live query for Lake Guntersville returns ZERO temperature sites — and NOAA's
//  buoy/satellite products cover the Great Lakes only. So for ~90% of the
//  waters people bowfish, the number the app shows will be MODELED. That makes
//  the model worth doing properly, instead of the old "water temp = air temp",
//  which is badly wrong at night (a 2 a.m. air reading is far colder than the
//  water it's supposedly estimating).
//
//  THE MODEL. Lake surface temperature has thermal memory: it integrates the
//  last several days of weather, not this instant's air. The standard predictor
//  (air2water / Toffolon 2022 / Mohseni) is a multi-day running mean of
//  daily-mean air temperature. We use its discrete first-order-lag form — an
//  EWMA of daily-mean air temp:
//
//      Tw[today] = Tw[yesterday] + k · (Tair_dailymean[today] − Tw[yesterday])
//
//  k = 0.20/day → thermal time constant τ ≈ 5 days, the right memory for the
//  SHALLOW near-shore water a bowfisher shoots in. Seeded with the trailing
//  7-day mean of daily-mean air temp. Computed on DAILY MEAN (not the night
//  value), so the night estimate needs no diurnal correction — surface temp at
//  night sits near the daily mean once the daytime skin warming has mixed down.
//
//  The gage override (when one is genuinely nearby) is handled upstream in
//  WaterLevelService; this is the always-available fallback layer.
//
//  Lives in SwiftData/Models/ so Xcode auto-includes it.
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
}

/// Result of the model: the current estimate plus the daily series for the chart.
struct WaterTempModel: Equatable {
    /// Modeled surface temp for today, °F.
    let currentF: Double
    /// Past ~14 days → next ~4 days, oldest → newest.
    let series: [WaterTempDay]

    static func == (l: WaterTempModel, r: WaterTempModel) -> Bool {
        l.currentF == r.currentF && l.series == r.series
    }
}

enum WaterTemperatureService {

    /// Thermal-lag constant (per day). τ = 1/k ≈ 5 days — shallow near-shore water.
    private static let k = 0.20
    /// Days of trailing air-temp mean used to seed the model.
    private static let seedDays = 7

    /// Modeled water temperature at `coordinate`, or nil if the daily air-temp
    /// history can't be fetched.
    static func model(near coordinate: CLLocationCoordinate2D) async -> WaterTempModel? {
        let items = [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", coordinate.latitude)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", coordinate.longitude)),
            URLQueryItem(name: "daily", value: "temperature_2m_mean"),
            // 15 past days: 7 to seed + a week of visible history for the chart.
            URLQueryItem(name: "past_days", value: "15"),
            URLQueryItem(name: "forecast_days", value: "4"),
            URLQueryItem(name: "temperature_unit", value: "fahrenheit"),
            URLQueryItem(name: "timezone", value: "auto"),
        ]

        guard let data = try? await WeatherService.fetchForecastData(queryItems: items),
              let decoded = try? JSONDecoder().decode(DailyMeanResponse.self, from: data),
              let means = decoded.daily.temperature_2m_mean else { return nil }

        let days: [(date: Date, airF: Double)] = zip(decoded.daily.time, means).compactMap { t, v in
            guard let v, let d = parseDay(t) else { return nil }
            return (d, v)
        }
        guard days.count >= seedDays else { return nil }

        // Seed with the trailing mean of the first `seedDays`, then roll the
        // first-order lag forward one day at a time.
        let seed = days.prefix(seedDays).map(\.airF).reduce(0, +) / Double(seedDays)
        var tw = seed
        var series: [WaterTempDay] = []
        for day in days {
            tw += k * (day.airF - tw)
            series.append(WaterTempDay(date: day.date, waterF: tw, airF: day.airF))
        }

        // "Now" = the modeled value for the LOCATION's today (the last day that
        // isn't in the future). Series dates are local date labels at UTC
        // midnight, so compare against the location's today as the same kind of
        // label. `Calendar.current` is UTC on Cloud Run, which every US evening
        // already counted tomorrow's forecast day as "today". Fall back to the
        // last point.
        let todayLabel = OpenMeteoTime.localDay(Date(), utcOffsetSeconds: decoded.utc_offset_seconds)
        let todayMidnight = parseDay(todayLabel) ?? Date()
        let current = series.last(where: { $0.date <= todayMidnight }) ?? series.last
        guard let current else { return nil }
        return WaterTempModel(currentF: current.waterF, series: series)
    }

    /// A local date label ("yyyy-MM-dd") pinned to UTC midnight, on every host.
    /// It was `TimeZone.current`, so the same label meant a different instant on
    /// a laptop than on Cloud Run, and day matching drifted between them.
    private static func parseDay(_ s: String) -> Date? { OpenMeteoTime.instant(s, utcOffsetSeconds: 0) }

    private struct DailyMeanResponse: Decodable {
        /// The location's offset from UTC; `daily.time` holds its local dates.
        let utc_offset_seconds: Int?
        let daily: Daily
        struct Daily: Decodable {
            let time: [String]
            let temperature_2m_mean: [Double?]?
        }
    }
}
