//
//  ClarityFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Water clarity / visibility — the master factor (§5.1). Bowfishing only needs
//  to see ~3–4 ft down, so the score *saturates* fast: once you can see a few
//  feet you're good, and there's a tiny penalty for gin-clear "spooky" water.
//  Algal (green bloom) turbidity kills the sightline ~2× sooner than the same
//  FNU of brown sediment. Below ~1 ft of visibility the night is blown out —
//  this factor also feeds the clarity gate (§6).
//

import Foundation

public enum ClarityFactor: Sendable {

    /// Estimated vertical visibility in feet — the shared basis for the score
    /// and the blown-out gate. Prefers a live turbidity gage; otherwise decays
    /// from recent rainfall.
    public static func visibilityFt(_ input: ConditionsInput,
                                    config: ConditionsConfig = .default) -> Double {
        let cfg = config.clarity
        if let fnu = input.turbidityFNU {
            let f = Swift.max(fnu, 0.1)                      // avoid pow(0, negative)
            var secchi = cfg.secchiCoefA * pow(f, cfg.secchiExpB)
            if input.turbidityType == .algal { secchi *= cfg.algalSecchiMultiplier }
            return Swift.max(0, secchi)
        }
        // No gage → decay a clear-water baseline by RECENT RAIN. Prefer the MRMS
        // radar-gauge 72 h total aggregated over the surrounding watershed (rain
        // upstream muddies the lake even when the ramp stayed dry); fall back to
        // the Open-Meteo 48 h point total only when MRMS is unavailable. §5.1.
        //
        // No-data guard: if NEITHER source answered, don't read the dry-baseline
        // "clear" (the most optimistic possible guess) — return a neutral
        // workable estimate so a missing signal can't score Prime.
        if !input.rainDataAvailable && input.rainWatershed72hIn == nil {
            return Swift.max(cfg.reservoirVisibilityFloorFt, cfg.fallbackBaseClearFt * 0.55)
        }
        let rain = Swift.max(0, input.rainWatershed72hIn ?? input.rainLast48hIn)
        if input.isTailwater {
            return cfg.fallbackBaseClearFt * exp(-cfg.fallbackRainDecayK * rain)
        }
        var vis = cfg.fallbackBaseClearFt * exp(-cfg.reservoirRainDecayK * rain)
        // Rising upstream inflow is runoff on its way in — it muddies the arms
        // before the rain total catches up. A strong 12 h discharge rise shaves a
        // little sightline, bounded so it never dominates the rain signal.
        if let trend = input.dischargeTrend12hCfs, trend > 0, let cfs = input.dischargeCfs, cfs > 0 {
            let riseFrac = Swift.min(trend / cfs, 1.0)           // 0…1 of current flow
            vis *= (1.0 - 0.25 * riseFrac)
        }
        return Swift.max(cfg.reservoirVisibilityFloorFt, vis)
    }

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let cfg = config.clarity
        let vis = visibilityFt(input, config: config)
        // "Estimated" means no real turbidity GAGE backing the number — key it on
        // hasTurbidityGage, not on turbidityFNU being nil, so a synthesized/derived
        // FNU without a gage still can't slip past the estimate caps below. §5.1.
        let estimated = !input.hasTurbidityGage
        var score = mapToScore(vis, curve: cfg.curve)

        // Gin-clear, dead-calm water spooks fish and makes the approach harder.
        if vis > cfg.ginClearFt, input.windMph <= cfg.ginClearMaxWindMph {
            score -= cfg.ginClearPenalty
        }

        // A guess can never read Prime — we're estimating, not measuring.
        if estimated { score = Swift.min(score, cfg.estimatedScoreCap) }

        return FactorScore(score: score.clampedToScore,
                           // The leading "~" carries the estimate now; the
                           // explicit "est." read as clutter on a tile.
                           label: estimated ? String(format: "~%.1f ft", vis)
                                            : String(format: "%.1f ft viz", vis),
                           why: why(vis: vis, input: input, estimated: estimated))
    }

    /// Piecewise-linear interpolation across the saturating breakpoints.
    private static func mapToScore(_ vis: Double, curve: [(ft: Double, score: Double)]) -> Double {
        guard let first = curve.first else { return 0 }
        if vis <= first.ft { return first.score }
        for i in 1..<curve.count {
            let lo = curve[i - 1], hi = curve[i]
            if vis <= hi.ft {
                let t = (vis - lo.ft) / (hi.ft - lo.ft)
                return lo.score + t * (hi.score - lo.score)
            }
        }
        return curve.last!.score
    }

    private static func why(vis: Double, input: ConditionsInput, estimated: Bool) -> String {
        // No "(est. …)" tail — the leading "~" on the value and the sheet's
        // source badge carry that. The parenthetical read as clutter.
        let bloom = input.turbidityType == .algal ? " (algal bloom — worse than mud)" : ""
        switch vis {
        case ..<1.0:  return "Blown out — \(String(format: "%.1f", vis)) ft visibility\(bloom)"
        case ..<2.0:  return "Murky — only \(String(format: "%.1f", vis)) ft down\(bloom)"
        case ..<3.0:  return "Workable — ~\(String(format: "%.1f", vis)) ft of sightline\(bloom)"
        case ..<4.0:  return "Good clarity — see ~\(String(format: "%.0f", vis)) ft down"
        default:
            if vis > 12, input.windMph <= 3 { return "Gin-clear & slick — hard to get in range unseen" }
            return "Clear water — full sightline"
        }
    }
}
