//
//  WaterTempFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Water temperature (§5.5). Species-agnostic baseline for "fish shallow &
//  active": rough fish move up into the shallows in the mid-60s°F and hold
//  through the warm season; cold makes them sluggish/deep, extreme heat pushes
//  them off the flats. Returns nil when there's no temperature reading at all —
//  the aggregator then drops it and renormalizes (confidence already accounts
//  for an estimated/absent temp). §3.
//

import Foundation

public enum WaterTempFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore? {
        guard let t = input.waterTempF else { return nil }
        let cfg = config.waterTemp
        var score = cfg.aboveTopScore
        for band in cfg.bands where t < band.maxF { score = band.score; break }

        // No "(est.)" on the number. Whether it's measured or modeled is shown
        // by the detail sheet's source badge and readout copy — stapling "(est.)"
        // onto the value read as clutter, and worse, contradicted the "Measured"
        // badge whenever a gauge WAS backing the reading.
        return FactorScore(score: score.clampedToScore,
                           label: "\(Int(t.rounded()))°F",
                           why: why(t))
    }

    private static func why(_ t: Double) -> String {
        switch t {
        case ..<50:  return "Cold — most species sluggish & deep"
        case ..<60:  return "Cool — fish slow to move shallow"
        case ..<68:  return "Warming — fish starting to use the shallows"
        case ..<82:  return "Prime warmth — fish up in the shallows"
        case ..<88:  return "Warm — still good on the flats"
        default:     return "Hot — fish may slide to cooler depth"
        }
    }
}
