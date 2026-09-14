//
//  DarknessFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Darkness / moon (§5.3). Dark water lets boat lights create the contrast that
//  lets a shooter approach close; a bright moon up during the window makes fish
//  spooky and deep. Keyed on moon *altitude during the window* (not raw phase)
//  and on whether cloud actually cancels the moon — which depends on light
//  pollution: away from cities cloud blocks the moon; near skyglow it reflects.
//
//  Pure function: numbers in, FactorScore out.
//

import Foundation

public enum DarknessFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore {
        let cfg = config.darkness
        let illum = (input.moonIllumPct / 100).clamped01
        let presence = input.moonAltitudeAtWindow.clamped01

        // How much cloud cancels the moon. Heavy cloud blocks moonlight in the
        // dark countryside (blocking≈1) but reflects city glow near towns
        // (blocking≈0.2). Our input.cityGlowFactor is 0 (pristine) … 1 (heavy
        // skyglow), so blocking falls as glow rises.
        let cloudFactor = ((input.cloudPct - cfg.cloudKneePct) / cfg.cloudSpanPct).clamped01
        let ruralBlocking = 1 - 0.8 * input.cityGlowFactor.clamped01   // rural→1.0, city→0.2
        let cloudCancel = (cloudFactor * ruralBlocking).clamped01

        let ambientMoon = (illum * presence * (1 - cloudCancel)).clamped01
        var score = 100 * (1 - ambientMoon)

        // Bonus when the window actually starts after astronomical (true) dark.
        if let start = input.windowStart, let astro = input.astronomicalDusk, start >= astro {
            score += cfg.astroDarkBonus
        }
        // Solunar majors/minors are intentionally NOT applied — unproven under
        // controlled testing, and irrelevant when you're shooting fish you can
        // see (§3, §14). The ±2 tiebreaker stays in config for future calibration.

        // Lead the label with the EFFECTIVE darkness (how much moonlight actually
        // reaches the water this window), not the raw phase. A 99%-phase moon that's
        // down or clouded is a DARK night, but labelling it "99% lit" read as a
        // full-moon-is-good bug — "lit" implied the whole sky was lit tonight. So:
        // "% moon" = the phase (context), and the second word = what actually
        // competes with the boat lights. The score is altitude/cloud-aware, so this
        // keeps the number and its label telling the same story.
        let effective: String
        if ambientMoon < 0.15 {
            effective = presence < 0.15 ? "moon down" : "dark water"
        } else if ambientMoon < 0.35 {
            effective = "mostly dark"
        } else if ambientMoon < 0.60 {
            effective = "some glow"
        } else {
            effective = "bright — moon up"
        }

        return FactorScore(score: score.clampedToScore,
                           label: "\(Int((illum * 100).rounded()))% moon · \(effective)",
                           why: why(ambientMoon: ambientMoon, illum: illum, presence: presence,
                                    cloudCancel: cloudCancel))
    }

    private static func why(ambientMoon: Double, illum: Double, presence: Double,
                            cloudCancel: Double) -> String {
        if ambientMoon < 0.20 {
            if illum >= 0.6 && presence < 0.3 { return "Bright moon, but below the horizon for the window — dark water" }
            if illum >= 0.6 && cloudCancel > 0.4 { return "Cloud cover cancels the bright moon — dark water" }
            return "Dark water — little moonlight in the window"
        } else if ambientMoon < 0.50 {
            return "Some moonlight during the window — workable contrast"
        } else {
            return "Bright moon up across the window — moonlight competing with your lights"
        }
    }
}
