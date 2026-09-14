//
//  SingleFlightCache.swift
//  SectorEngine
//
//  The one concurrency-safe cache the upstream adapters use instead of plain
//  `var` dictionaries on shared singletons.
//
//  Before 2026-09-14 the TVA, SWPA and CWMS adapters kept their caches in
//  unsynchronized `var`s on `static let shared` classes. Concurrent renders on
//  one instance (or a single /conditions/batch request, which scores six points
//  at once) mutated those dictionaries from different threads — a memory-
//  corruption crash the Swift 5 compiler couldn't flag. Prod logged SIGSEGV
//  container crashes that fit it.
//
//  This actor gives every adapter the same three guarantees:
//   1. Safety — all cache state is actor-isolated.
//   2. Single-flight — concurrent callers for the same key share ONE fetch
//      instead of each starting their own (a cold burst of renders for lakes on
//      one TVA/CWMS district does one request, not N).
//   3. Failure memory — a nil result can be remembered for `failureTTL`, so an
//      upstream that is down costs one timeout per window, not one per render.
//
//  The computation runs in an unstructured Task, so a caller that gives up
//  (withDeadline abandons it) doesn't cancel the fetch: it finishes and warms
//  the cache for the next render. Only the cache bookkeeping is actor-isolated;
//  the fetch and its parsing run off the actor, in parallel with other keys.
//

import Foundation

actor SingleFlightCache<Key: Hashable & Sendable, Value: Sendable> {
    private struct Entry {
        let value: Value?
        let at: Date
    }

    private var entries: [Key: Entry] = [:]
    private var inFlight: [Key: Task<Value?, Never>] = [:]

    private let ttl: TimeInterval
    private let failureTTL: TimeInterval
    private let maxEntries: Int

    /// - Parameters:
    ///   - ttl: how long a non-nil value is served before refetching.
    ///   - failureTTL: how long a nil result is remembered; 0 = never cache nil.
    ///   - maxEntries: bound on stored keys. Expired entries are dropped first,
    ///     then the oldest, so a public endpoint can't grow the cache forever.
    init(ttl: TimeInterval, failureTTL: TimeInterval = 0, maxEntries: Int = 1_000) {
        self.ttl = ttl
        self.failureTTL = failureTTL
        self.maxEntries = maxEntries
    }

    /// The cached value for `key` if still fresh; otherwise joins an in-flight
    /// computation for the same key, or starts one.
    /// - Parameter force: skip the cache read (pull-to-refresh). Still joins an
    ///   in-flight computation rather than starting a duplicate, and still stores
    ///   the result for the next caller.
    func value(for key: Key, force: Bool = false,
               compute: @escaping @Sendable () async -> Value?) async -> Value? {
        if !force, let entry = entries[key] {
            let age = Date().timeIntervalSince(entry.at)
            if entry.value != nil, age < ttl { return entry.value }
            if entry.value == nil, age < failureTTL { return nil }
        }
        if let running = inFlight[key] { return await running.value }

        let task = Task<Value?, Never> { await compute() }
        inFlight[key] = task
        let result = await task.value
        inFlight[key] = nil

        if result != nil || failureTTL > 0 {
            entries[key] = Entry(value: result, at: Date())
            if entries.count > maxEntries { prune() }
        }
        return result
    }

    /// Drop expired entries; if still over the bound, drop the oldest.
    private func prune() {
        let now = Date()
        let keep = max(ttl, failureTTL)
        entries = entries.filter { now.timeIntervalSince($0.value.at) < keep }
        guard entries.count > maxEntries else { return }
        let overflow = entries.count - maxEntries
        for key in entries.sorted(by: { $0.value.at < $1.value.at }).prefix(overflow).map(\.key) {
            entries.removeValue(forKey: key)
        }
    }
}
