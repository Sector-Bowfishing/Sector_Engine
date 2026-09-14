//
//  WaterLevelFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Water level / stage trend (§5.6). Rising water floods cover and pulls fish
//  (and flood-spawners) shallow; a gentle rise is ideal. A hard rain-driven rise
//  is a good *location* signal but its turbidity downside is handled separately
//  by the clarity gate — we do NOT double-count it here (§14). Falling water
//  pulls fish back toward depth; a fast drawdown is worst. Returns nil when no
//  stage trend is available (dropped + renormalized).
//

import Foundation

public enum WaterLevelFactor: Sendable {

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> FactorScore? {
        let cfg = config.level

        // On a RESERVOIR, the pool's own 12h trend (from the dam's history) is
        // the level of the water you're standing on — far truer than a USGS
        // river-stage gage that may be tens of miles off on a different reach.
        // Below a dam (tailwater) the pool behind it ISN'T your level, so there
        // we stay on the gage. §5.6.
        let trend = (input.isTailwater ? nil : input.reservoirTrend12hFt) ?? input.stageTrend12hFt

        // No trend at all, but a dam covers this water → we DO have the pool
        // elevation. Show it with a neutral score rather than dropping the
        // factor and leaving the tile a dash. A reservoir on a normal day is
        // level-stable; the tile shouldn't read "no data" when we know the pool.
        guard let delta = trend else {
            if let pool = input.reservoirElevationFt {
                return FactorScore(score: cfg.stableScore,
                                   label: String(format: "%.2f ft", pool),
                                   why: "Reservoir pool holding around \(String(format: "%.1f", pool)) ft — no fast level change to move fish off the flats.")
            }
            return nil
        }

        let score: Double
        let why: String
        if abs(delta) <= cfg.stableBandFt {
            score = cfg.stableScore;        why = "Stable level — patternable shallow fish"
        } else if delta > 0 {
            if delta <= cfg.gentleRiseMaxFt {
                score = cfg.gentleRiseScore; why = "Gentle rise — flooding cover, pulling fish up"
            } else {
                score = cfg.strongRiseScore; why = "Strong rise — good location (watch clarity)"
            }
        } else {
            if delta <= cfg.fastFallFt {
                score = cfg.fastFallScore;  why = "Fast drawdown — fish pulling off the flats"
            } else {
                score = cfg.slowFallScore;  why = "Slow fall — fish sliding toward depth"
            }
        }

        // On a reservoir, show the POOL ELEVATION. "-0.0 ft/12h" is the honest
        // trend but reads as nothing at all, while "414.0 ft" is the number
        // people actually talk about — and it's the level of the water you're
        // standing on, which a river-stage gage miles away isn't.
        //
        // The SCORE is still the 12h trend either way: how the level is moving
        // is what changes the fishing, not its absolute height. Only the label
        // changes, and the trend moves into `why` so nothing is lost.
        if let pool = input.reservoirElevationFt {
            // TWO decimals, matching the generation detail sheet's RESERVOIR
            // readout exactly. At one decimal the tile rounded 413.99 up to
            // "414.0" while the sheet said "413.99" — same number, two faces.
            // Michael: "we cant have that." One formatter, one value.
            return FactorScore(score: score.clampedToScore,
                               label: String(format: "%.2f ft", pool),
                               why: why + String(format: " · %+.1f ft/12h", delta))
        }
        return FactorScore(score: score.clampedToScore,
                           label: String(format: "%+.1f ft/12h", delta),
                           why: why)
    }
}
