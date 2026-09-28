//
//  CatchmentRainfall.swift
//  Sector — rain over each arm's real drainage area
//
//  REPLACES, FOR THE NEW CLARITY ARCHITECTURE ONLY, the conditions engine's
//  "watershed": four points ±0.35° (about 24 mi) around the spot, with no
//  idea which way the land drains (MrmsPrecipService). That path still scores
//  production and is untouched.
//
//  Here each arm has its contributing drainage — the NHDPlus V2 basin at its
//  mouth, from USGS NLDI (or above its head where the mouth basin is the
//  river's) — as fractional NOAA MRMS 0.01° cells
//  (scripts/hydrology/catchment_rain.py weights). An hourly job at T−2 h (MRMS
//  Pass 2 is gauge-corrected with ~2 h latency) reads the Pass 2 1/6/12/24/48/72 h
//  accumulation products, the hourly product back to the storm's start, and
//  the 72 h products before the window, and publishes one file per lake. The
//  engine reads that file.
//
//  The job is `jobs/hydrology-hourly` (Cloud Run Job `hydrology-hourly`,
//  hourly at :15 UTC, since 2026-09-27). When its file is missing or older
//  than 4 h, every arm reads `unavailable`, and says why.
//

import Foundation

public struct CatchmentRainfall: Codable, Equatable {
    public let arm: String
    /// nhdplusBasinAtMouth | nhdplusBasinAboveHead | unavailable
    public let basis: String
    public let drainageKm2: Double?
    /// "mrmsPass2" | "unavailable"
    public let provenance: String
    public let validTime: Date?
    public let last1hIn: Double?
    public let last6hIn: Double?
    public let last12hIn: Double?
    public let last24hIn: Double?
    public let last48hIn: Double?
    public let last72hIn: Double?
    /// Back from the valid time to the last 6 dry hours (< 0.01 in basin mean).
    public let currentStormIn: Double?
    /// The 7 days before the 72 h window.
    public let antecedent7dBeforeWindowIn: Double?
    public let reason: String?

    public static func unavailable(_ arm: String, basis: String = "unavailable", reason: String) -> CatchmentRainfall {
        CatchmentRainfall(arm: arm, basis: basis, drainageKm2: nil, provenance: "unavailable", validTime: nil,
                          last1hIn: nil, last6hIn: nil, last12hIn: nil, last24hIn: nil, last48hIn: nil,
                          last72hIn: nil, currentStormIn: nil, antecedent7dBeforeWindowIn: nil, reason: reason)
    }
}

public enum CatchmentRainfallFeed {

    /// Where the hourly job publishes (the lake-surface bucket).
    public static func url(forLake slug: String) -> URL? {
        LakeSurfaceBucket.url("rain/\(slug)/catchments.json")
    }

    /// A feed older than this is not "now".
    static let maxAgeHours = 4.0

    /// The file catchment_rain.py writes.
    struct Feed: Decodable {
        let validTime: String
        let arms: [String: Arm]
        struct Arm: Decodable {
            let basis: String?
            let drainageKm2: Double?
            let last1hIn: Double?, last6hIn: Double?, last12hIn: Double?
            let last24hIn: Double?, last48hIn: Double?, last72hIn: Double?
            let currentStormIn: Double?
            let antecedent7dBeforeWindowIn: Double?
        }
    }

    static func parse(_ data: Data, arms: [String], now: Date) -> [String: CatchmentRainfall]? {
        guard let feed = try? JSONDecoder().decode(Feed.self, from: data) else { return nil }
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]
        // the job writes "2026-09-22T00:00:00Z"; accept a minute-only time too
        guard let valid = f.date(from: feed.validTime)
                ?? f.date(from: feed.validTime.replacingOccurrences(of: "Z", with: ":00Z")) else { return nil }
        let stale = now.timeIntervalSince(valid) > maxAgeHours * 3600
        var out: [String: CatchmentRainfall] = [:]
        for id in arms {
            guard let a = feed.arms[id], a.basis != "unavailable", a.basis != nil else {
                out[id] = .unavailable(id, reason: "no drainage area resolved for this creek"); continue
            }
            if stale {
                out[id] = .unavailable(id, basis: a.basis ?? "unavailable",
                                       reason: "the rain feed is older than \(Int(maxAgeHours)) h (\(feed.validTime))")
                continue
            }
            out[id] = CatchmentRainfall(arm: id, basis: a.basis ?? "unavailable", drainageKm2: a.drainageKm2,
                                        provenance: "mrmsPass2", validTime: valid,
                                        last1hIn: a.last1hIn, last6hIn: a.last6hIn, last12hIn: a.last12hIn,
                                        last24hIn: a.last24hIn, last48hIn: a.last48hIn, last72hIn: a.last72hIn,
                                        currentStormIn: a.currentStormIn,
                                        antecedent7dBeforeWindowIn: a.antecedent7dBeforeWindowIn, reason: nil)
        }
        return out
    }

    public static func latest(forLake slug: String, arms: [String], now: Date = Date()) async -> [String: CatchmentRainfall] {
        guard let url = url(forLake: slug),
              let r = try? await HTTP.get(url), r.isSuccess,
              let parsed = parse(r.body, arms: arms, now: now) else {
            return Dictionary(uniqueKeysWithValues: arms.map {
                ($0, CatchmentRainfall.unavailable($0, reason: "the hourly catchment rain feed did not answer"))
            })
        }
        return parsed
    }
}
