//
//  LakeWind.swift
//  Sector — the lake-wide wind for `GET /lakes/ready` (Sector_Engine #158; owner approval on Sector_Ops #51,
//  2026-11-11 ~23:40Z, "#158, wind and Intel").
//
//  Wind has no per-lake CUSTOMER-lane copy, so the Engine computes it: one forecast per lake, at the lake's representative
//  point, labeled ESTIMATE. It is never a reason to list a lake: only a lake that is already ready (a CUSTOMER-lane copy
//  passed its reader) gets a `wind` layer.
//
//    - Point: the centre of the lake's registry bbox (`extent.bbox`) when it has one, else the directory centroid, rounded
//      to 0.01° (the same rounding as the /conditions forecast cache).
//    - Source: the Engine's existing Open-Meteo forecast path (`WeatherService.fetchForecastData`: both hosts raced, 8 s cap
//      per host). Hourly `wind_speed_10m` (mph) and `wind_direction_10m` (degrees true, the direction it blows FROM), in UTC.
//      No `models` parameter, so Open-Meteo answers with `best_match`: the model the Wind Brain's outlook decision keeps for
//      tonight (`WindOutlookModelOutputAPI.tonightModel`, WS-5).
//    - Now: the forecast for the UTC hour that contains the request time; `asOf` is that hour. `hourly` is that hour and the
//      next 12, for the app's play bar.
//    - Cost: every point that needs a forecast goes into ONE multi-location request (up to 100 points per request). A point's
//      forecast is refetched at most every 30 min, and only when a request needs it. A failed fetch is retried after 60 s;
//      meanwhile the last good forecast is served for up to 3 h. A request waits at most `LakesReadyAPI.windBudget` for wind,
//      then answers without it (the fetch carries on and fills the cache).
//

import Foundation

/// The `wind` layer: an Engine forecast, always `ESTIMATE`.
public struct ReadyWindLayer: Codable, Equatable, Sendable {
    public let status: String
    /// The forecast hour the values are for (the UTC hour that contains the request time), ISO 8601 UTC.
    public let asOf: String
    /// Wind speed at 10 m, mph, one decimal.
    public let speedMph: Double
    /// The direction the wind blows FROM, whole degrees true, 0...359.
    public let fromDeg: Int
    /// The `asOf` hour first, then each following forecast hour up to 12 hours later. Never empty.
    public let hourly: [ReadyWindHour]
}

public struct ReadyWindHour: Codable, Equatable, Sendable {
    public let time: String
    public let speedMph: Double
    public let fromDeg: Int
}

/// One forecast hour at a lake's point.
struct LakeWindSample: Equatable, Sendable {
    let time: Date
    let speedMph: Double
    let fromDeg: Int
}

/// A point's hourly wind forecast, chronological, top-of-hour UTC.
public struct LakeWindForecast: Equatable, Sendable {
    let samples: [LakeWindSample]

    init(samples: [LakeWindSample]) { self.samples = samples.sorted { $0.time < $1.time } }

    /// The layer at `now`, or nil when the forecast has no value for the hour that contains `now`.
    func layer(now: Date) -> ReadyWindLayer? {
        let start = (now.timeIntervalSince1970 / 3600).rounded(.down) * 3600
        let end = start + LakeWind.hourlySpan
        let hours = samples.filter { $0.time.timeIntervalSince1970 >= start && $0.time.timeIntervalSince1970 <= end }
        guard let first = hours.first, first.time.timeIntervalSince1970 == start else { return nil }
        return ReadyWindLayer(status: ReadyLayer.estimate, asOf: LakesReadyAPI.iso(first.time), speedMph: first.speedMph,
                              fromDeg: first.fromDeg,
                              hourly: hours.map { ReadyWindHour(time: LakesReadyAPI.iso($0.time), speedMph: $0.speedMph, fromDeg: $0.fromDeg) })
    }
}

/// A lake's representative point, rounded to 0.01°. `key` identifies it in the cache and in one request.
public struct LakeWindPoint: Hashable, Sendable {
    public let lat: Double
    public let lon: Double

    public init(lat: Double, lon: Double) {
        self.lat = (lat * 100).rounded() / 100
        self.lon = (lon * 100).rounded() / 100
    }

    var key: String { String(format: "%.2f,%.2f", lat, lon) }

    /// The centre of the registry bbox when the lake has an extent, else its directory centroid.
    static func of(_ lake: ReadyLake) -> LakeWindPoint {
        if let b = lake.extent?.bbox {
            return LakeWindPoint(lat: (b.south + b.north) / 2, lon: (b.west + b.east) / 2)
        }
        return LakeWindPoint(lat: lake.centroid.lat, lon: lake.centroid.lon)
    }
}

public enum LakeWind {
    /// `hourly` runs from the current hour to this many seconds later (12 h).
    static let hourlySpan: TimeInterval = 12 * 3600
    /// Points per Open-Meteo request.
    static let chunkSize = 100
    /// A speed above this (mph) is not a 10 m wind; the hour is dropped.
    static let maxSpeedMph = 250.0

    /// One multi-location request for `points`.
    static func queryItems(_ points: [LakeWindPoint]) -> [URLQueryItem] {
        [
            URLQueryItem(name: "latitude", value: points.map { String(format: "%.2f", $0.lat) }.joined(separator: ",")),
            URLQueryItem(name: "longitude", value: points.map { String(format: "%.2f", $0.lon) }.joined(separator: ",")),
            URLQueryItem(name: "hourly", value: "wind_speed_10m,wind_direction_10m"),
            URLQueryItem(name: "forecast_days", value: "2"),
            URLQueryItem(name: "wind_speed_unit", value: "mph"),
            URLQueryItem(name: "timezone", value: "GMT"),
            URLQueryItem(name: "timeformat", value: "unixtime"),
        ]
    }

    /// The forecasts in request order (nil for a location without one), or nil when the body is not a response for
    /// `count` locations. Open-Meteo answers one location with an object and several with an array.
    static func parse(_ data: Data, count: Int) -> [LakeWindForecast?]? {
        let decoder = JSONDecoder()
        let items: [Location]
        if let a = try? decoder.decode([Location].self, from: data) { items = a }
        else if let o = try? decoder.decode(Location.self, from: data) { items = [o] }
        else { return nil }
        guard items.count == count else { return nil }
        return items.map { item -> LakeWindForecast? in
            guard let h = item.hourly, let times = h.time, let speeds = h.wind_speed_10m, let dirs = h.wind_direction_10m else {
                return nil
            }
            var samples: [LakeWindSample] = []
            for i in times.indices where i < speeds.count && i < dirs.count {
                guard let t = times[i], t.isFinite, t.truncatingRemainder(dividingBy: 3600) == 0,
                      let s = speeds[i], s.isFinite, s >= 0, s <= maxSpeedMph,
                      let d = dirs[i], d.isFinite, d >= 0, d <= 360 else { continue }
                samples.append(LakeWindSample(time: Date(timeIntervalSince1970: t), speedMph: (s * 10).rounded() / 10,
                                              fromDeg: Int(d.rounded()) % 360))
            }
            return samples.isEmpty ? nil : LakeWindForecast(samples: samples)
        }
    }

    /// One location of an Open-Meteo response (`timeformat=unixtime`). Every part is optional: a location without its
    /// hourly wind is nil, not a failed response.
    struct Location: Decodable {
        let hourly: Hourly?
        struct Hourly: Decodable {
            let time: [Double?]?
            let wind_speed_10m: [Double?]?
            let wind_direction_10m: [Double?]?
        }
    }
}

/// Each point's forecast, fetched at most every `ttl`, in one request per `LakeWind.chunkSize` points. Concurrent requests
/// share one fetch per point. A failed point is retried after `failureTTL`; meanwhile its last good forecast is served up
/// to `maxAge`.
public actor LakeWindCache {
    typealias Fetch = @Sendable ([URLQueryItem]) async throws -> Data

    /// One request's points and what it returned.
    struct Batch: Sendable {
        let keys: [String]
        let forecasts: [String: LakeWindForecast]
    }

    private let fetch: Fetch
    private let ttl: TimeInterval
    private let maxAge: TimeInterval
    private let failureTTL: TimeInterval
    private let clock: @Sendable () -> Date
    private var entries: [String: (forecast: LakeWindForecast, at: Date)] = [:]
    private var failedAt: [String: Date] = [:]
    private var inFlight: [String: Task<Batch, Never>] = [:]

    /// The server's cache: the Engine's Open-Meteo forecast path.
    public init(ttl: TimeInterval = 1800, maxAge: TimeInterval = 3 * 3600, failureTTL: TimeInterval = 60,
                clock: @escaping @Sendable () -> Date = { Date() }) {
        self.init(fetch: { try await WeatherService.fetchForecastData(queryItems: $0) }, ttl: ttl, maxAge: maxAge,
                  failureTTL: failureTTL, clock: clock)
    }

    init(fetch: @escaping Fetch, ttl: TimeInterval = 1800, maxAge: TimeInterval = 3 * 3600, failureTTL: TimeInterval = 60,
         clock: @escaping @Sendable () -> Date = { Date() }) {
        self.fetch = fetch
        self.ttl = ttl
        self.maxAge = maxAge
        self.failureTTL = failureTTL
        self.clock = clock
    }

    /// The forecast for each point that has a usable one, by `LakeWindPoint.key`.
    func forecasts(for points: [LakeWindPoint]) async -> [String: LakeWindForecast] {
        var unique: [LakeWindPoint] = []
        var seen = Set<String>()
        for p in points where seen.insert(p.key).inserted { unique.append(p) }

        let now = clock()
        var due: [LakeWindPoint] = []
        for p in unique {
            if inFlight[p.key] != nil { continue }
            if let e = entries[p.key], now.timeIntervalSince(e.at) < ttl { continue }
            if let f = failedAt[p.key], now.timeIntervalSince(f) < failureTTL { continue }
            due.append(p)
        }
        var start = 0
        while start < due.count {
            let chunk = Array(due[start..<min(start + LakeWind.chunkSize, due.count)])
            start += LakeWind.chunkSize
            let fetch = self.fetch
            let task = Task<Batch, Never> {
                let keys = chunk.map(\.key)
                guard let data = try? await fetch(LakeWind.queryItems(chunk)),
                      let parsed = LakeWind.parse(data, count: chunk.count) else { return Batch(keys: keys, forecasts: [:]) }
                var out: [String: LakeWindForecast] = [:]
                for (k, f) in zip(keys, parsed) { if let f { out[k] = f } }
                return Batch(keys: keys, forecasts: out)
            }
            for p in chunk { inFlight[p.key] = task }
        }

        // Await every request that covers one of these points (each once), and record it if no other caller has yet.
        var tasks: [Task<Batch, Never>] = []
        for p in unique {
            if let t = inFlight[p.key], !tasks.contains(where: { $0 == t }) { tasks.append(t) }
        }
        for t in tasks {
            let batch = await t.value
            let at = clock()
            for k in batch.keys where inFlight[k] == t {
                inFlight[k] = nil
                if let f = batch.forecasts[k] {
                    entries[k] = (f, at)
                    failedAt[k] = nil
                } else {
                    failedAt[k] = at
                }
            }
        }

        let after = clock()
        var out: [String: LakeWindForecast] = [:]
        for p in unique {
            if let e = entries[p.key], after.timeIntervalSince(e.at) < maxAge { out[p.key] = e.forecast }
        }
        return out
    }
}
