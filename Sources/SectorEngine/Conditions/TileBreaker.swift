//
//  TileBreaker.swift
//  SectorEngine
//
//  Per-tile, in-process circuit breaker (spec §3, owner rule 6: per-tile watch with automatic rollback). Evaluated only
//  for tiles in `serve`.
//
//  - Window: the last 15 minutes of samples; it judges only once it holds at least 20 new-path attempts.
//  - Trips when, over the window, either:
//      the new path's failure-or-blank rate is more than 10 percentage points above the old path's, or
//      the new path's p95 fetch latency is more than 3 s above the old path's.
//  - Tripped: serve old for 30 minutes, then half-open: try new on 10% of requests until 20 good samples (then closed).
//    A bad sample while half-open re-opens it for another 30 minutes.
//  - Every state change logs `[tile-breaker] {"tile":…,"state":…,"reason":…,"window":{…}}`.
//
//  The value type `TileBreaker` is pure: time and the 10% roll are passed in, so it is deterministic under test.
//  `TileBreakerRegistry` holds one per tile for the process and supplies the clock and the roll.
//

import Foundation

/// Every breaker threshold, in one place (spec §3).
public enum TileBreakerConstants {
    public static let windowSeconds: TimeInterval = 15 * 60
    public static let minNewSamples = 20
    /// Percentage points, as a fraction: new failure rate − old failure rate above this trips.
    public static let failureRateMargin = 0.10
    /// Seconds: new p95 latency − old p95 latency above this trips.
    public static let p95LatencyMarginSeconds: TimeInterval = 3
    public static let openSeconds: TimeInterval = 30 * 60
    /// Share of requests that try the new path while half-open.
    public static let halfOpenTrialFraction = 0.10
    /// Consecutive good new-path samples that close a half-open breaker.
    public static let halfOpenGoodSamples = 20
    /// Memory cap per tile: the oldest samples beyond this are dropped even inside the window.
    public static let maxSamplesPerTile = 2_000
}

public struct TileBreaker: Equatable, Sendable {

    public enum State: String, Codable, Sendable {
        case closed
        case open
        case halfOpen = "half-open"
    }

    public enum Path: String, Codable, Sendable { case old, new }

    public struct Sample: Equatable, Sendable {
        public let at: Date
        public let path: Path
        /// false when the path failed or returned nothing (blank).
        public let ok: Bool
        public let latency: TimeInterval
    }

    /// The window statistics a decision was made on (logged with every transition).
    public struct WindowStats: Codable, Equatable, Sendable {
        public let newSamples: Int
        public let oldSamples: Int
        public let newFailRate: Double
        public let oldFailRate: Double
        public let newP95Seconds: Double
        public let oldP95Seconds: Double
    }

    /// A state change, with the reason and the window it was decided on.
    public struct Transition: Equatable, Sendable {
        public let tile: TileKey
        public let state: State
        public let reason: String
        public let window: WindowStats

        /// `[tile-breaker] {...}` (spec §3).
        public var logLine: String {
            struct Line: Encodable { let tile: String; let state: String; let reason: String; let window: WindowStats }
            let enc = JSONEncoder()
            enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
            let body = (try? enc.encode(Line(tile: tile.rawValue, state: state.rawValue, reason: reason, window: window)))
                .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
            return "[tile-breaker] " + body
        }
    }

    public let tile: TileKey
    public private(set) var state: State = .closed
    /// The window's samples, oldest first (at most `maxSamplesPerTile`).
    public private(set) var samples: [Sample] = []
    /// Per path, the window's latencies kept sorted (binary insertion and removal) and its failure count, so a sample
    /// never re-sorts the window.
    private var newWindow = PathWindow()
    private var oldWindow = PathWindow()
    /// When the breaker last opened (open state only).
    public private(set) var openedAt: Date?
    /// Consecutive good new-path samples while half-open.
    public private(set) var halfOpenGood = 0

    public init(tile: TileKey) { self.tile = tile }

    /// Should this request try the new path? Advances open → half-open once the open period has passed.
    /// - Parameter roll: a uniform draw in [0, 1); used only while half-open (try new when roll < 10%).
    public mutating func shouldTryNew(at now: Date, roll: Double) -> (tryNew: Bool, transition: Transition?) {
        switch state {
        case .closed:
            return (true, nil)
        case .open:
            guard let openedAt, now.timeIntervalSince(openedAt) >= TileBreakerConstants.openSeconds else { return (false, nil) }
            state = .halfOpen
            halfOpenGood = 0
            let t = Transition(tile: tile, state: .halfOpen, reason: "open period elapsed; trying new on 10% of requests",
                               window: stats(at: now))
            return (roll < TileBreakerConstants.halfOpenTrialFraction, t)
        case .halfOpen:
            return (roll < TileBreakerConstants.halfOpenTrialFraction, nil)
        }
    }

    /// Record one sample. Returns the transition when this sample changes the state.
    @discardableResult
    public mutating func record(path: Path, ok: Bool, latency: TimeInterval, at now: Date) -> Transition? {
        let sample = Sample(at: now, path: path, ok: ok, latency: max(0, latency))
        samples.append(sample)
        if path == .new { newWindow.insert(sample) } else { oldWindow.insert(sample) }
        prune(at: now)

        switch state {
        case .open:
            return nil
        case .halfOpen:
            guard path == .new else { return nil }
            let w = currentStats()
            let good = ok && latency - w.oldP95Seconds <= TileBreakerConstants.p95LatencyMarginSeconds
            if !good {
                return open(at: now, reason: ok ? "half-open trial too slow" : "half-open trial failed or blank", window: w)
            }
            halfOpenGood += 1
            guard halfOpenGood >= TileBreakerConstants.halfOpenGoodSamples else { return nil }
            state = .closed
            halfOpenGood = 0
            samples.removeAll()   // a fresh window after recovery
            newWindow = PathWindow(); oldWindow = PathWindow()
            return Transition(tile: tile, state: .closed,
                              reason: "\(TileBreakerConstants.halfOpenGoodSamples) good half-open samples", window: w)
        case .closed:
            guard path == .new else { return nil }
            let w = currentStats()
            guard w.newSamples >= TileBreakerConstants.minNewSamples else { return nil }
            if w.newFailRate - w.oldFailRate > TileBreakerConstants.failureRateMargin {
                return open(at: now, reason: "new failure rate more than 10 points above old", window: w)
            }
            if w.newP95Seconds - w.oldP95Seconds > TileBreakerConstants.p95LatencyMarginSeconds {
                return open(at: now, reason: "new p95 latency more than 3 s above old", window: w)
            }
            return nil
        }
    }

    /// Window statistics at `now` (samples older than the window are ignored).
    public func stats(at now: Date) -> WindowStats {
        var copy = self
        copy.prune(at: now)
        return copy.currentStats()
    }

    /// Statistics of the window as it stands (already pruned).
    private func currentStats() -> WindowStats {
        WindowStats(newSamples: newWindow.count, oldSamples: oldWindow.count,
                    newFailRate: newWindow.failRate, oldFailRate: oldWindow.failRate,
                    newP95Seconds: newWindow.p95, oldP95Seconds: oldWindow.p95)
    }

    /// Nearest-rank p95; 0 for no samples.
    static func p95(_ values: [TimeInterval]) -> TimeInterval {
        guard !values.isEmpty else { return 0 }
        let sorted = values.sorted()
        let rank = Int((0.95 * Double(sorted.count)).rounded(.up))
        return sorted[min(max(rank, 1), sorted.count) - 1]
    }

    private mutating func open(at now: Date, reason: String, window: WindowStats) -> Transition {
        state = .open
        openedAt = now
        halfOpenGood = 0
        return Transition(tile: tile, state: .open, reason: reason, window: window)
    }

    private mutating func prune(at now: Date) {
        let cutoff = now.addingTimeInterval(-TileBreakerConstants.windowSeconds)
        var drop = 0
        while drop < samples.count,
              samples[drop].at < cutoff || samples.count - drop > TileBreakerConstants.maxSamplesPerTile {
            let s = samples[drop]
            if s.path == .new { newWindow.remove(s) } else { oldWindow.remove(s) }
            drop += 1
        }
        if drop > 0 { samples.removeFirst(drop) }
    }
}

/// One path's window: latencies sorted ascending and a failure count, maintained incrementally.
struct PathWindow: Equatable, Sendable {
    private(set) var sortedLatencies: [TimeInterval] = []
    private(set) var failures = 0

    var count: Int { sortedLatencies.count }
    var failRate: Double { count == 0 ? 0 : Double(failures) / Double(count) }
    /// Nearest-rank p95; 0 for no samples.
    var p95: TimeInterval {
        guard !sortedLatencies.isEmpty else { return 0 }
        let rank = Int((0.95 * Double(count)).rounded(.up))
        return sortedLatencies[min(max(rank, 1), count) - 1]
    }

    mutating func insert(_ s: TileBreaker.Sample) {
        sortedLatencies.insert(s.latency, at: lowerBound(s.latency))
        if !s.ok { failures += 1 }
    }

    mutating func remove(_ s: TileBreaker.Sample) {
        let i = lowerBound(s.latency)
        if i < sortedLatencies.count, sortedLatencies[i] == s.latency { sortedLatencies.remove(at: i) }
        if !s.ok { failures -= 1 }
    }

    private func lowerBound(_ v: TimeInterval) -> Int {
        var lo = 0, hi = sortedLatencies.count
        while lo < hi {
            let mid = (lo + hi) / 2
            if sortedLatencies[mid] < v { lo = mid + 1 } else { hi = mid }
        }
        return lo
    }
}

/// One `TileBreaker` per tile for this process. The clock, the half-open roll and the log sink are injectable.
public actor TileBreakerRegistry {
    public static let shared = TileBreakerRegistry()

    private var breakers: [TileKey: TileBreaker] = [:]
    private let now: @Sendable () -> Date
    private let roll: @Sendable () -> Double
    private let log: @Sendable (String) -> Void

    public init(now: @escaping @Sendable () -> Date = { Date() },
                roll: @escaping @Sendable () -> Double = { Double.random(in: 0..<1) },
                log: @escaping @Sendable (String) -> Void = { print($0) }) {
        self.now = now
        self.roll = roll
        self.log = log
    }

    public func shouldTryNew(_ tile: TileKey) -> Bool {
        var b = breakers[tile] ?? TileBreaker(tile: tile)
        let (tryNew, transition) = b.shouldTryNew(at: now(), roll: roll())
        breakers[tile] = b
        if let transition { log(transition.logLine) }
        return tryNew
    }

    public func record(_ tile: TileKey, path: TileBreaker.Path, ok: Bool, latency: TimeInterval) {
        var b = breakers[tile] ?? TileBreaker(tile: tile)
        let transition = b.record(path: path, ok: ok, latency: latency, at: now())
        breakers[tile] = b
        if let transition { log(transition.logLine) }
    }

    public func state(_ tile: TileKey) -> TileBreaker.State { breakers[tile]?.state ?? .closed }

    public func windowStats(_ tile: TileKey) -> TileBreaker.WindowStats {
        (breakers[tile] ?? TileBreaker(tile: tile)).stats(at: now())
    }
}
