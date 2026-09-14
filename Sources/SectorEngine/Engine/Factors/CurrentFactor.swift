//
//  CurrentFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Current / dam generation (§5.7), tailwater-aware. Lakes/ponds are rarely
//  current-limited (neutral-positive).
//
//  On a tailwater the response is a CURVE, not a slope. Moderate generation is
//  the best case — the current stacks fish on points and seams while the water
//  is still shootable. Settled water scores well but not best (clear, but fish
//  scattered); heavy generation scores badly (muddy, fast, a gate candidate).
//
//  TVA/USACE generation feeds are deferred (per project decision), so when no
//  resolved `generationLevel` is supplied we classify from the live USGS
//  discharge trend. If a tailwater can't be classified at all, the factor is
//  dropped and confidence drops. §3.
//

import Foundation

public enum CurrentFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore? {
        let cfg = config.current

        guard input.isTailwater else {
            // RESERVOIR, with a dam feed covering it. Say what the dam is doing
            // — the dashboard row already does, and "Lake / pond" next to a row
            // reading "Pickwick · 2 units" is the app contradicting itself.
            //
            // But a lake is NOT a tailwater and must not be scored like one.
            // Pulling water moves the pool near the dam and can pull bait and
            // fish toward it; it does not turn the lake muddy and fast the way
            // it transforms the river below. So the score stays close to the
            // neutral lake value and only nudges — heavy generation is a mild
            // negative, settled flow a mild positive. Scoring it identically
            // would have swung every reservoir score by the tailwater spread.
            if let level = input.generationLevel {
                switch level {
                case .low:
                    return FactorScore(score: cfg.nonTailwaterScore,
                                       label: "Low / steady",
                                       why: "Lake — dam settled, little pull")
                case .moderate:
                    return FactorScore(score: cfg.nonTailwaterScore - 5,
                                       label: "Moderate",
                                       why: "Lake — dam pulling, some current near the dam")
                case .high:
                    return FactorScore(score: cfg.nonTailwaterScore - 12,
                                       label: "High / rising",
                                       why: "Lake — heavy pull, current and drawdown near the dam")
                }
            }
            return FactorScore(score: cfg.nonTailwaterScore,
                               label: "Lake / pond",
                               why: "Not a tailwater — current rarely limits sight-shooting")
        }

        guard let level = input.generationLevel
                ?? classify(dischargeCfs: input.dischargeCfs,
                            trendCfs: input.dischargeTrend12hCfs, cfg: cfg) else {
            return nil   // tailwater, but no way to judge generation → drop + lower confidence
        }

        switch level {
        case .low:
            return FactorScore(score: cfg.lowGenScore, label: "Low / steady",
                               why: "Settled flow — clear water, fish roaming shallow")
        case .moderate:
            return FactorScore(score: cfg.moderateGenScore, label: "Moderate",
                               why: "Moderate current — it stacks fish on points and seams. The best of it.")
        case .high:
            return FactorScore(score: cfg.highGenScore, label: "High / rising",
                               why: "Heavy generation — muddy, fast, hard to see")
        }
    }

    /// Resolve a generation level from the live discharge trend when no forecast
    /// is available. Rising flow by a large relative fraction = high; a smaller
    /// rise = moderate; steady or falling = settled (low).
    static func classify(dischargeCfs: Double?, trendCfs: Double?,
                         cfg: ConditionsConfig.Current) -> GenerationLevel? {
        guard let base = dischargeCfs, base > 0 else { return nil }
        let trend = trendCfs ?? 0
        guard trend > 0 else { return .low }   // steady or easing → settled
        let frac = trend / base
        if frac >= cfg.risingCfsHighFrac { return .high }
        if frac >= cfg.risingCfsModerateFrac { return .moderate }
        return .low
    }
}
