//
//  PressureFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Barometric pressure (§5.8) — a modest factor. Brand stance (2026-07-17,
//  matching the pressure infographic + detail sheet): rising and steady pressure
//  = comfortable, active, feeding fish; falling pressure ahead of weather = fish
//  go inactive and the incoming front dims visibility too. Steady/high stays the
//  practical optimum for a bowfisher — calm, clear, cloudless nights.
//

import Foundation

public enum PressureFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let cfg = config.pressure
        let p = input.pressureInHg

        let score: Double
        let why: String
        if p > cfg.veryHighInHg {
            score = cfg.veryHighScore
            why = "Very high pressure — calm, clear, settled air"
        } else if p < cfg.veryLowInHg {
            score = cfg.veryLowScore
            why = "Very low pressure — unsettled, weather moving in"
        } else {
            switch input.pressureTrend {
            case .falling:
                score = cfg.fallingScore; why = "Falling pressure — fish pull off the shallows ahead of weather"
            case .rising:
                score = cfg.risingFastScore; why = "Rising pressure — fish up shallow and cruising"
            case .steady:
                if p >= cfg.steadyLowInHg && p <= cfg.steadyHighInHg {
                    score = cfg.steadyNormalScore; why = "Steady high pressure — calm, clear nights"
                } else {
                    score = cfg.extremeScore; why = "Steady pressure"
                }
            }
        }

        return FactorScore(score: score.clampedToScore,
                           label: String(format: "%.2f inHg", p),
                           why: why)
    }
}
