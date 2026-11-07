//
//  USGSReadingCache.swift
//  SectorEngine
//
//  Sector_Ops #51 F4. USGS readings per box query, in memory, per instance:
//
//   - fresh for 15 min, including an EMPTY answer ("no gauge in this box"), so a
//     lake whose small box has no gauge doesn't re-ask USGS on every render;
//   - last good for 6 h: when a fetch fails, the most recent non-empty answer
//     is served instead of dropping the factor. Each reading keeps its own
//     `dateTime`, so its age stays visible downstream;
//   - at most `maxEntries` keys; the oldest are dropped first;
//   - only whole answers: never one from a cancelled task or one whose
//     names/metadata lookup failed (WaterLevelService.nearbyReadings).
//
//  USGS gauges report every 15–60 min, so a 15 min cache rarely hides a newer
//  value. The cache is lost when an instance stops.
//

import Foundation

actor USGSReadingCache {
    static let shared = USGSReadingCache()

    static let freshFor: TimeInterval = 15 * 60
    static let lastGoodFor: TimeInterval = 6 * 3600
    /// A 2.5° box can hold hundreds of readings with their history, so the cap is kept modest (review of #139).
    static let maxEntries = 500

    private struct Entry { let readings: [WaterLevelReading]; let at: Date }
    private var entries: [String: Entry] = [:]
    private var lastGood: [String: Entry] = [:]

    init() {}

    /// A cached answer younger than `freshFor`, empty answers included.
    func fresh(_ key: String, now: Date = Date()) -> [WaterLevelReading]? {
        guard let e = entries[key], now.timeIntervalSince(e.at) < Self.freshFor else { return nil }
        return e.readings
    }

    /// The most recent NON-empty answer younger than `lastGoodFor`, for a failed fetch.
    func lastGood(_ key: String, now: Date = Date()) -> [WaterLevelReading]? {
        guard let e = lastGood[key], now.timeIntervalSince(e.at) < Self.lastGoodFor else { return nil }
        return e.readings
    }

    func put(_ key: String, _ readings: [WaterLevelReading], now: Date = Date()) {
        entries[key] = Entry(readings: readings, at: now)
        if !readings.isEmpty { lastGood[key] = Entry(readings: readings, at: now) }
        Self.trim(&entries)
        Self.trim(&lastGood)
    }

    var count: Int { entries.count }

    /// Drops the oldest entry once over the cap (one put adds at most one key, so one removal keeps the bound).
    private static func trim(_ d: inout [String: Entry]) {
        while d.count > maxEntries, let oldest = d.min(by: { $0.value.at < $1.value.at })?.key { d.removeValue(forKey: oldest) }
    }
}

extension WaterLevelService {
    /// Sector_Ops #51 F3: every box size at once, decided in box order. The answer is exactly what the old one-after-another
    /// loop gave: the first box (smallest first) whose `decide` returns `.done`, and an error from a box is thrown only if every
    /// smaller box came back empty (as before, where the loop never reached the larger boxes). It returns as soon as that box
    /// is known, cancelling the larger ones still running.
    enum BoxDecision { case next, done(WaterLevelReading?) }

    static func firstAcrossRadii(_ radii: [Double],
                                 fetch: @escaping @Sendable (Double) async throws -> [WaterLevelReading],
                                 decide: @escaping @Sendable ([WaterLevelReading]) -> BoxDecision) async throws -> WaterLevelReading? {
        try await withThrowingTaskGroup(of: (Int, Result<[WaterLevelReading], Error>).self) { group in
            for (i, r) in radii.enumerated() {
                group.addTask {
                    do { return (i, .success(try await fetch(r))) } catch { return (i, .failure(error)) }
                }
            }
            var done: [Int: Result<[WaterLevelReading], Error>] = [:]
            var next = 0
            while let (i, result) = try await group.next() {
                done[i] = result
                while let r = done[next] {
                    let readings: [WaterLevelReading]
                    do { readings = try r.get() } catch { group.cancelAll(); throw error }
                    if case .done(let answer) = decide(readings) { group.cancelAll(); return answer }
                    next += 1
                }
            }
            return nil
        }
    }
}
