//
//  SkyFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Sky & temp (§5.9) — a light comfort/quality factor. Cloud % already feeds the
//  darkness factor (a bright-moon rescue); here it's mostly comfort plus a small
//  clear-sky bonus. A clear, comfortable night scores high; storms or temperature
//  extremes pull it down.
//

import Foundation

public enum SkyFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let cfg = config.sky
        let codeScore = cfg.codeScores[input.weatherCode] ?? cfg.defaultCodeScore
        var score = codeScore * 100 * comfort(input.airTempF, cfg: cfg)
        if input.weatherCode == 0 || input.weatherCode == 1 { score += cfg.clearBonus }

        return FactorScore(score: score.clampedToScore,
                           label: skyLabel(code: input.weatherCode, cloudPct: input.cloudPct),
                           why: why(code: input.weatherCode, airF: input.airTempF, cfg: cfg))
    }

    /// A SKY descriptor, not the air temperature. The tile used to show
    /// "\(airTempF)°F", which is the exact number the Temperature tile already
    /// shows — two tiles, one reading. Describe the sky (and the cloud amount
    /// that decides whether the moon reaches the water) instead.
    private static func skyLabel(code: Int, cloudPct: Double) -> String {
        let pct = Int(cloudPct.rounded())
        switch code {
        case 0, 1:       return pct <= 15 ? "Clear" : "Clear · \(pct)%"
        case 2:          return "Partly cloudy · \(pct)%"
        case 3:          return "Overcast · \(pct)%"
        case 45, 48:     return "Foggy"
        case 95, 96, 99: return "Storms"
        default:         return "Wet · \(pct)%"
        }
    }

    /// 1.0 inside the comfort band, tapering as the air gets uncomfortable.
    private static func comfort(_ t: Double, cfg: ConditionsConfig.Sky) -> Double {
        if t >= cfg.comfortLowF && t <= cfg.comfortHighF { return 1 }
        let miss = t < cfg.comfortLowF ? (cfg.comfortLowF - t) : (t - cfg.comfortHighF)
        return Swift.max(0.5, 1 - miss / 40)
    }

    private static func why(code: Int, airF: Double, cfg: ConditionsConfig.Sky) -> String {
        let comfortNote: String
        if airF < cfg.comfortLowF { comfortNote = ", cold out" }
        else if airF > cfg.comfortHighF { comfortNote = ", hot out" }
        else { comfortNote = "" }
        switch code {
        case 0, 1:  return "Clear sky\(comfortNote)"
        case 2, 3:  return "Cloud cover\(comfortNote)"
        case 45, 48: return "Foggy\(comfortNote)"
        case 95, 96, 99: return "Storms — stay home"
        default:    return "Wet weather\(comfortNote)"
        }
    }
}
