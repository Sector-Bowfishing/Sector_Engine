//
//  LakeLevelValidity.swift
//  Sector — Lake Brain: how long a published level counts as current (pure; no I/O)
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
//  and then held inside two hard limits:
//    ceiling  the source's own stale rule (lag + 3 × cadence): a reading is never presented as current once its
//             gauge is overdue, however steady the lake (the existing LakeLevelClassifier.isStale rule).
//    floor    one source cycle (cadence + lag) and no less than the refresh latency (`refreshLatencyMin`): Lake is
//             re-run about hourly and a run reaches the app one Orchestrator cycle later, so a window shorter than
//             that would blank a correct value before its replacement can arrive.
//
//  For an hourly gauge (cadence 60, lag 60) that gives STABLE 4 h (the ceiling), CHANGING 3 h, FAST 3 h (the floor);
//  for a daily source it is one source cycle. What makes a changing lake track the water is the hourly refresh
//  (LakeBrainRunner reads every lake's newest reading each run); the window only decides how long a value may stand
//  without a newer one. Thresholds are pre-set, not fitted: tune them against the prediction ledger.
//

import Foundation

public enum LakeLevelValidity {

    public enum Tier: String, Sendable, Equatable { case fast = "FAST", changing = "CHANGING", stable = "STABLE" }

    public static let fastWindowMin = 120
    public static let changingWindowMin = 180
    public static let stableWindowMin = 360
    /// Hourly Lake runs + one Orchestrator cycle to publish: a window below this cannot be refreshed in time.
    public static let refreshLatencyMin = 180

    public static let fastChange6hFt = 1.0
    public static let changing6hFt = 0.25
    public static let changing24hFt = 0.5
    public static let heavyRainIn = 1.0
    public static let rainIn = 0.25

    public struct Decision: Sendable, Equatable {
        public var tier: Tier
        public var windowMin: Int
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

    /// The window for one source. Never above the source's stale limit; never below one source cycle or the refresh latency
    /// (unless the stale limit itself is shorter, which no binding has today).
    public static func decide(trend: LakeTrendState, change: LakeLevelChange, rainNext12hIn: Double?,
                              cadenceMin: Int, lagMin: Int) -> Decision {
        let (t, why) = tier(trend: trend, change: change, rainNext12hIn: rainNext12hIn)
        let ceiling = lagMin + 3 * cadenceMin
        let floor = min(ceiling, max(cadenceMin + lagMin, refreshLatencyMin))
        let want: Int
        switch t { case .fast: want = fastWindowMin; case .changing: want = changingWindowMin; case .stable: want = stableWindowMin }
        let window = min(ceiling, max(floor, want))
        return Decision(tier: t, windowMin: window, reason: "\(t.rawValue): \(why); current for \(window) min after the reading")
    }
}
