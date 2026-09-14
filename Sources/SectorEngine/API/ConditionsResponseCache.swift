//
//  ConditionsResponseCache.swift
//  SectorEngine
//
//  A short-TTL, single-flight cache for the FULL /conditions render, sitting one
//  level above ConditionsSnapshotProvider.
//
//  The snapshot provider already coalesces + caches the upstream *fetches*. But
//  the /conditions endpoint does more on top of a warm snapshot — a 7-night
//  forecast fetch, the aggregator evaluate, and the DTO mapping — and the My
//  Lakes preload hits /conditions once per saved lake on every app launch. A
//  burst across many distinct lakes cold-misses the snapshot cache all at once,
//  and each request then launches ~9 blocking Linux URLSession fetches; with only
//  CPU-count cooperative threads the pool starves, the withDeadline timers can't
//  fire, and every request rides to Cloud Run's 60s guillotine (→ 504, even for
//  /health). See the 2026-09-14 outage.
//
//  This cache flattens that load two ways:
//   1. Single-flight — concurrent identical requests share ONE computation
//      instead of each launching their own fan-out.
//   2. TTL reuse — a lake computed once is free for every launch/user for the
//      next few minutes (the preload fires on every launch; users relaunch a
//      lot; lakes are shared across users), so the fan-out happens once per TTL
//      per lake rather than continuously.
//
//  Keyed at ~100 m (matching ConditionsSnapshotProvider) so drifting around a
//  ramp reuses the render but a different lake does not.
//

import Foundation

public actor ConditionsResponseCache {
    public static let shared = ConditionsResponseCache()
    public init() {}

    /// How long a rendered response stays good. Matches the snapshot TTL — the
    /// inputs move on the order of an hour, and a "tonight" score barely shifts
    /// in five minutes — so a hit never shows meaningfully staler data than a
    /// cold render would, while collapsing the preload storm.
    public static let defaultTTL: TimeInterval = 5 * 60

    /// Safety cap so a pathological spread of coordinates can't grow the cache
    /// without bound. Far above the count of real lakes anyone lists.
    private static let maxEntries = 500

    private struct Entry { let response: ConditionsResponse; let at: Date }
    private var cache: [String: Entry] = [:]
    /// In-flight renders by key — the single-flight that makes a burst of
    /// identical requests share one fan-out instead of racing.
    private var inFlight: [String: Task<ConditionsResponse?, Never>] = [:]

    /// ~100 m of precision, same convention as ConditionsSnapshotProvider.key.
    private nonisolated func key(_ lat: Double, _ lon: Double) -> String {
        String(format: "%.3f,%.3f", lat, lon)
    }

    /// Return a cached render if fresh, join an in-flight identical render if one
    /// is running, else run `compute` once and cache its result.
    /// - Parameter fresh: pull-to-refresh — skip the cache READ (still joins an
    ///   in-flight render rather than starting a duplicate, and still stores the
    ///   fresh result for the next caller).
    public func conditions(
        lat: Double, lon: Double,
        ttl: TimeInterval = defaultTTL,
        fresh: Bool = false,
        compute: @escaping @Sendable () async -> ConditionsResponse?
    ) async -> ConditionsResponse? {
        let k = key(lat, lon)

        // Fast path: a fresh render already sitting in the cache.
        if !fresh, let hit = cache[k], Date().timeIntervalSince(hit.at) < ttl {
            return hit.response
        }
        // A render for this exact key is already running — ride it instead of
        // launching a second fan-out. (No `await` between the cache check above
        // and here, so the miss→join decision is atomic on the actor.)
        if let running = inFlight[k] { return await running.value }

        // Miss: compute once. Callers that arrive while we're suspended on
        // `task.value` find this task in `inFlight` and share it.
        let task = Task<ConditionsResponse?, Never> { await compute() }
        inFlight[k] = task
        let result = await task.value
        inFlight[k] = nil

        if let result {
            cache[k] = Entry(response: result, at: Date())
            pruneIfNeeded()
        }
        return result
    }

    /// Drop expired entries; if still over the cap, evict the oldest. Cheap and
    /// only runs on a store (a real miss), not on the hot hit path.
    private func pruneIfNeeded() {
        guard cache.count > Self.maxEntries else { return }
        let now = Date()
        cache = cache.filter { now.timeIntervalSince($0.value.at) < Self.defaultTTL }
        if cache.count > Self.maxEntries {
            let overflow = cache.count - Self.maxEntries
            for k in cache.sorted(by: { $0.value.at < $1.value.at }).prefix(overflow).map(\.key) {
                cache.removeValue(forKey: k)
            }
        }
    }
}
