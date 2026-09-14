//
//  HumidityFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Humidity, scored as FOG RISK (§ new). Humidity on its own barely moves fish,
//  so scoring the raw percentage would be noise. What actually matters to a
//  bowfisher is fog: when the air cools to within a couple degrees of its dew
//  point, fog forms over the water, and fog ends the night — you can't shoot
//  what you can't see, and you can't run a boat blind.
//
//  So this factor is neutral (≈100) on a clear, dry night and only pulls the
//  score down when fog is genuinely likely during the window. It's low-weight
//  (0.03) by design: a tie-breaker, not a driver.
//
//  Pure function: numbers in, FactorScore out.
//

import Foundation

public enum HumidityFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let rh = Int(input.humidityPct.rounded())

        // Prefer the forecast air–dewpoint spread over the window; it's the real
        // fog predictor. Fall back to raw RH only when no dewpoint series exists.
        if let spread = input.fogSpreadF {
            let score: Double
            let label: String
            let why: String
            switch spread {
            case ..<2:
                score = 45
                label = "Fog likely"
                why = "Air cools to within \(fmt(spread)) of the dew point tonight — fog forms on the water, which kills your lights' reach and makes running the boat dangerous."
            case ..<4:
                score = 72
                label = "Patchy fog possible"
                why = "The air–dewpoint spread drops to about \(fmt(spread)) — patchy fog is possible over the water late. Watch for it thickening."
            case ..<6:
                score = 90
                label = "Slight fog risk"
                why = "A narrow air–dewpoint spread (\(fmt(spread))) — a little fog is possible in low spots, but nothing that should stop you."
            default:
                score = 100
                label = "Clear air"
                why = "Plenty of margin between air and dew point — no fog expected, clear sightlines all night."
            }
            return FactorScore(score: score, label: label, why: why)
        }

        // No dewpoint series — lean on raw RH. Only a near-saturated sky is worth
        // flagging; everything else is neutral.
        if rh >= 97 {
            return FactorScore(score: 70, label: "\(rh)% — fog possible",
                               why: "Humidity is near saturation, so fog could form over the water late. No dewpoint forecast to confirm timing.")
        }
        return FactorScore(score: 100, label: "\(rh)%",
                           why: "Humidity is comfortable — no fog concern for tonight.")
    }

    private static func fmt(_ f: Double) -> String {
        "\(Int(f.rounded()))°F"
    }
}
