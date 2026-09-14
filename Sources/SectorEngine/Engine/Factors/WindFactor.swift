//
//  WindFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Wind (§5.4). This is the INVERSE of rod-fishing wind logic: calm is best,
//  because you must see through the surface. Chop kills the sightline and stirs
//  near-bank sediment. Steady beats gusty; past ~15 mph difficulty climbs fast;
//  >20 mph is a gate candidate. Direction isn't a big score driver — it feeds
//  "where to look" (windward forage vs. lee clarity).
//

import Foundation

public enum WindFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let cfg = config.wind
        let speedScore = speed(input.windMph, cfg: cfg)
        let penalty = gustPenalty(sustained: input.windMph, gust: input.windGustMph, cfg: cfg)
        let score = (speedScore - penalty).clampedToScore
        return FactorScore(score: score,
                           label: "\(Int(input.windMph.rounded())) mph",
                           why: why(input.windMph, gustPenalty: penalty))
    }

    static func speed(_ mph: Double, cfg: ConditionsConfig.Wind) -> Double {
        for band in cfg.bands where mph <= band.maxMph { return band.score }
        return cfg.aboveTopScore
    }

    static func gustPenalty(sustained: Double, gust: Double?, cfg: ConditionsConfig.Wind) -> Double {
        guard let gust, gust > sustained else { return 0 }
        let excess = gust - sustained
        let frac = (excess / cfg.gustExcessForFullPenalty).clamped01
        return cfg.gustPenaltyMax * frac
    }

    private static func why(_ mph: Double, gustPenalty: Double) -> String {
        let gusty = gustPenalty > 4 ? ", gusty" : ""
        switch mph {
        case ..<4:   return "Slick calm — clean sightline\(gusty)"
        case ..<7:   return "Light chop — surface still readable\(gusty)"
        case ..<11:  return "Breezy — surface chopping up\(gusty)"
        case ..<15:  return "Windy — sightline suffering\(gusty)"
        case ..<20:  return "Rough — tuck into sheltered water\(gusty)"
        default:     return "Blowing hard — visibility wrecked"
        }
    }
}
