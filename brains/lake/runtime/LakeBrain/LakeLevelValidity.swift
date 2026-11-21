//
//  LakeLevelValidity.swift
//  Sector — Lake Brain: how long a published level counts as current, and when to look again (pure; no I/O)
//
//  Owner direction (Michael, 2026-11-20, Sector_Ops #51): a flat validity window is wrong — "lake levels can change a
//  lot in 6 hours; the brain should notice rain and watch the levels to see if it's changing". So the window is chosen
//  per lake, per run, from the lake's own recent readings and the forecast rain at the lake:
//
//    FAST      trend RISING/FALLING_RAPIDLY, |Δ6h| ≥ 1.0 ft, or ≥ 1.0 in of rain forecast in the next 12 h → 2 h
//    CHANGING  trend RISING/FALLING, |Δ6h| ≥ 0.25 ft, |Δ24h| ≥ 0.5 ft, ≥ 0.25 in of rain forecast, or the rain
//              signal is unknown (no NWS answer)                                                            → 3 h
//    STABLE    otherwise (steady and dry)                                                                    → 6 h
//
//  The tier window is counted from the READING. The value is then held between two hard limits:
//
//    freshUntil = min(reading + ceiling, max(reading + tierWindow, now + refreshLatency))
//
//    ceiling         the source's own stale rule (lag + 3 × cadence): a reading is never presented as current once its
//                    gauge is overdue, however steady the lake (the LakeLevelClassifier.isStale rule).
//    refreshLatency  counted from the RUN, not the reading: one Orchestrator grant interval (hourly, at :50) + one publish
//                    cycle + run time and jitter. Any window that ends sooner would withdraw a correct value before the
//                    next run's replacement can reach customers. (Review of #216: a floor counted from the reading did.)
//
//  When to look again (`nextCheckAt`; LakeBrainPlanner recomputes a lake once now ≥ nextCheckAt − plannerTolerance):
//    FAST / CHANGING  now + recheck (45 min): recomputed on every hourly grant, so a moving lake tracks the water.
//    STABLE           its source's next reading (at least 2 h out), but never later than freshUntil − refreshLatency, so its
//                     replacement is always computed in time.
//  Thresholds are pre-set, not fitted: tune them against the prediction ledger.
//

import Foundation

public enum LakeLevelValidity {

    public enum Tier: String, Sendable, Equatable { case fast = "FAST", changing = "CHANGING", stable = "STABLE" }

    public static let fastWindowMin = 120
    public static let changingWindowMin = 180
    public static let stableWindowMin = 360
    /// One hourly grant (60) + one publish cycle (60) + run time and jitter (30). Counted from the run.
    public static let refreshLatencyMin = 150
    /// FAST / CHANGING lakes ask for a recompute this soon: below the hourly grant interval, so every grant recomputes them.
    public static let recheckMin = 45
    /// LakeBrainPlanner treats a nextCheckAt this close as reached (grants land a few minutes either side of :50).
    public static let plannerToleranceMin = 10

    public static let fastChange6hFt = 1.0
    public static let changing6hFt = 0.25
    public static let changing24hFt = 0.5
    public static let heavyRainIn = 1.0
    public static let rainIn = 0.25

    public struct Decision: Sendable, Equatable {
        public var tier: Tier
        public var freshUntil: Date
        public var nextCheckAt: Date
        public var reason: String
    }

    public static func tier(trend: LakeTrendState, change: LakeLevelChange, rainNext12hIn: Double?) -> (Tier, String) {
        let h6 = change.h6.map(abs), h24 = change.h24.map(abs)
        if trend == .risingRapidly || trend == .fallingRapidly { return (.fast, "rapid change") }
        if let h = h6, h >= fastChange6hFt { return (.fast, String(format: "%.2f ft in 6 h", h)) }
        if let r = rainNext12hIn, r >= heavyRainIn { return (.fast, String(format: "%.2f in of rain forecast in 12 h", r)) }
        if trend == .rising || trend == .falling { return (.changing, "\(trend == .rising ? "rising" : "falling")") }
        if let h = h6, h >= changing6hFt { return (.changing, String(format: "%.2f ft in 6 h", h)) }
        if let h = h24, h >= changing24hFt { return (.changing, String(format: "%.2f ft in 24 h", h)) }
        if let r = rainNext12hIn, r >= rainIn { return (.changing, String(format: "%.2f in of rain forecast in 12 h", r)) }
        if rainNext12hIn == nil { return (.changing, "rain forecast unavailable") }
        return (.stable, "steady and dry")
    }

    static func windowMin(_ t: Tier) -> Int {
        switch t { case .fast: fastWindowMin; case .changing: changingWindowMin; case .stable: stableWindowMin }
    }

    /// The window and the next check for one reading of one source.
    public static func decide(trend: LakeTrendState, change: LakeLevelChange, rainNext12hIn: Double?,
                              cadenceMin: Int, lagMin: Int, observedAt: Date, now: Date) -> Decision {
        let (t, why) = tier(trend: trend, change: change, rainNext12hIn: rainNext12hIn)
        let ceiling = observedAt.addingTimeInterval(Double(lagMin + 3 * cadenceMin) * 60)
        let wanted = observedAt.addingTimeInterval(Double(windowMin(t)) * 60)
        let floor = now.addingTimeInterval(Double(refreshLatencyMin) * 60)
        let freshUntil = min(ceiling, max(wanted, floor))

        let next: Date
        switch t {
        case .fast, .changing:
            next = now.addingTimeInterval(Double(recheckMin) * 60)
        case .stable:
            let nextReading = observedAt.addingTimeInterval(Double(cadenceMin + lagMin) * 60)
            let relaxed = max(nextReading, now.addingTimeInterval(max(Double(cadenceMin) * 60, 2 * 3600)))
            let latest = freshUntil.addingTimeInterval(-Double(refreshLatencyMin) * 60)
            next = max(now, min(relaxed, latest))
        }
        let minutes = Int((freshUntil.timeIntervalSince(observedAt) / 60).rounded())
        let bound = freshUntil == ceiling ? " (the source's stale limit)" : (freshUntil == floor && floor > wanted ? " (held to the refresh latency)" : "")
        return Decision(tier: t, freshUntil: freshUntil, nextCheckAt: next,
                        reason: "\(t.rawValue): \(why); current for \(minutes) min after the reading\(bound)")
    }
}
