//
//  MrmsPrecipService.swift
//  SectorEngine
//
//  Recent rainfall from NOAA MRMS (Multi-Radar Multi-Sensor QPE, radar+gauge),
//  read through the Iowa Environmental Mesonet IEMRE point API as plain JSON —
//  no GRIB2 to parse. Two reasons this replaces Open-Meteo for the clarity model:
//
//    1. MRMS is radar-gauge and ~1 km; it catches the localized convective rain
//       an ~11 km forecast model routinely reads as 0.0" (verified: Gardendale AL
//       showed 0.68" on a day Open-Meteo missed entirely).
//    2. We aggregate over the SURROUNDING watershed, not just the ramp — rain
//       upstream muddies the lake even when it stayed dry where you launch.
//
//  Returns nil on any failure so the caller falls back to the Open-Meteo 48 h
//  point total. IEMRE precip is itself MRMS-derived for recent dates.
//

import Foundation
#if canImport(CoreLocation)
import CoreLocation
#endif   // Linux falls back to the engine's CoreLocationShim (CLLocationCoordinate2D).

/// Rainfall the clarity model actually needs: a watershed-aggregated 72 h total,
/// plus the point's daily series for the sightline trend chart.
struct MrmsPrecip {
    let watershed72hIn: Double
    let point72hIn: Double
    let daily: [DailyRain]              // point, last ~14 days (oldest → newest)
    struct DailyRain { let date: Date; let inches: Double }
}

final class MrmsPrecipService: Sendable {
    static let shared = MrmsPrecipService()
    private init() {}

    /// ~0.35° ≈ 24 mi in four directions — samples nearby cells that drain toward
    /// the same water without needing a flow-direction/HUC dataset.
    private let ringOffsetDeg = 0.35
    private let historyDays = 14

    func recent(near coordinate: CLLocationCoordinate2D, now: Date = Date()) async -> MrmsPrecip? {
        let lat = coordinate.latitude, lon = coordinate.longitude
        async let pt = daily(lat: lat, lon: lon, days: historyDays, now: now)
        // Four surrounding samples for the watershed signal (completed days only).
        let d = ringOffsetDeg
        async let n = completed48(lat: lat + d, lon: lon, now: now)
        async let s = completed48(lat: lat - d, lon: lon, now: now)
        async let e = completed48(lat: lat, lon: lon + d, now: now)
        async let w = completed48(lat: lat, lon: lon - d, now: now)
        // TODAY's rain — IEMRE lags a day, so today's bucket never exists there.
        // Open-Meteo carries the current day (coarser, but it's the only current
        // source without parsing real-time MRMS GRIB2). Point-only; runoff from
        // today's rain takes time to reach the lake anyway.
        async let today = todayPrecipIn(lat: lat, lon: lon, now: now)

        guard let ptDaily = await pt, !ptDaily.isEmpty else { return nil }
        let todayIn = await today ?? 0
        // A true 72h ending now: today (so far) + the two completed days behind it.
        let completedPoint = ptDaily.suffix(2).reduce(0) { $0 + $1.inches }
        let point72 = todayIn + completedPoint
        let ring = [await n, await s, await e, await w].compactMap { $0 }
        let ringMax = ring.max() ?? 0
        let ringMean = ring.isEmpty ? 0 : ring.reduce(0, +) / Double(ring.count)
        // Surrounding rain that reaches the lake counts even if the ramp was dry.
        let watershed = todayIn + Swift.max(completedPoint, 0.7 * ringMax, ringMean)

        // Append today to the daily series so the sightline chart reaches "now".
        var series = ptDaily
        let startOfToday = Calendar(identifier: .gregorian).startOfDay(for: now)
        if series.last?.date != startOfToday {
            series.append(MrmsPrecip.DailyRain(date: startOfToday, inches: todayIn))
        }
        return MrmsPrecip(watershed72hIn: watershed, point72hIn: point72, daily: series)
    }

    /// The two completed days behind today (the completed part of a 72h window).
    private func completed48(lat: Double, lon: Double, now: Date) async -> Double? {
        guard let d = await daily(lat: lat, lon: lon, days: 4, now: now) else { return nil }
        return d.suffix(2).reduce(0) { $0 + $1.inches }
    }

    /// Today's rainfall so far (inches) from Open-Meteo — the current-day layer
    /// IEMRE can't provide yet. Uses observed hourly precip up to `now`.
    private func todayPrecipIn(lat: Double, lon: Double, now: Date) async -> Double? {
        var comp = URLComponents(string: "https://api.open-meteo.com/v1/forecast")
        comp?.queryItems = [
            URLQueryItem(name: "latitude", value: String(format: "%.4f", lat)),
            URLQueryItem(name: "longitude", value: String(format: "%.4f", lon)),
            URLQueryItem(name: "hourly", value: "precipitation"),
            URLQueryItem(name: "past_days", value: "1"),
            URLQueryItem(name: "forecast_days", value: "1"),
            URLQueryItem(name: "precipitation_unit", value: "inch"),
            URLQueryItem(name: "timeformat", value: "unixtime"),
            URLQueryItem(name: "timezone", value: "GMT"),
        ]
        guard let url = comp?.url else { return nil }
        guard let result = try? await HTTP.get(url), result.isSuccess else { return nil }
        struct Resp: Decodable { let hourly: Hourly?; struct Hourly: Decodable { let time: [Int]; let precipitation: [Double?] } }
        guard let decoded = try? JSONDecoder().decode(Resp.self, from: result.body), let h = decoded.hourly else { return nil }
        let startOfDay = Calendar(identifier: .gregorian).startOfDay(for: now).timeIntervalSince1970
        let nowTs = now.timeIntervalSince1970
        var sum = 0.0
        for (i, t) in h.time.enumerated() where i < h.precipitation.count {
            let ts = Double(t)
            if ts >= startOfDay && ts <= nowTs { sum += h.precipitation[i] ?? 0 }
        }
        return Swift.max(0, sum)
    }

    private struct IEMREResponse: Decodable {
        let data: [Day]
        struct Day: Decodable { let date: String; let mrms_precip_in: Double? }
    }

    /// Daily MRMS precip (inches) at a point for the last `days`, dropping days the
    /// reanalysis hasn't filled yet (most-recent day is often null).
    private func daily(lat: Double, lon: Double, days: Int, now: Date) async -> [MrmsPrecip.DailyRain]? {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago") ?? .current
        guard let start = cal.date(byAdding: .day, value: -(days - 1), to: now) else { return nil }
        let fmt = DateFormatter()
        fmt.locale = Locale(identifier: "en_US_POSIX")
        fmt.timeZone = cal.timeZone
        fmt.dateFormat = "yyyy-MM-dd"
        let s = fmt.string(from: start), e = fmt.string(from: now)
        let path = "https://mesonet.agron.iastate.edu/iemre/multiday/\(s)/\(e)/\(String(format: "%.4f", lat))/\(String(format: "%.4f", lon))/json"
        guard let url = URL(string: path) else { return nil }
        guard let result = try? await HTTP.get(url, headers: ["Accept": "application/json"]),
              result.isSuccess,
              let decoded = try? JSONDecoder().decode(IEMREResponse.self, from: result.body) else { return nil }
        return decoded.data.compactMap { day -> MrmsPrecip.DailyRain? in
            guard let inches = day.mrms_precip_in, let dt = fmt.date(from: day.date) else { return nil }
            return MrmsPrecip.DailyRain(date: dt, inches: Swift.max(0, inches))
        }
    }
}
