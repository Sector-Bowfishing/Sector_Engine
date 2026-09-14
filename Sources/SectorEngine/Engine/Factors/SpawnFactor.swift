//
//  SpawnFactor.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  Spawn activity — the highest-value factor (§5.2). A spawn run packs shallow
//  water with fish and overrides much of the moon caution. The score is the max
//  intensity across species that are *legal and present* in the region, plus the
//  contributing species for "where to look".
//
//    intensity = 100 · tempScore · dateScore · floodScore   (Tier 1)
//
//  Soft triangular temp edges and a tapered date window (sources conflict on
//  exact spawn temps — §14). Rising water amplifies flood-dependent spawners
//  (buffalo, alligator gar); the amplification is multiplicative, so it can only
//  lift a night whose temp AND date are already favorable — it can't manufacture
//  a spawn out of cold or out-of-season water. Tier 2 (riverine Asian carps) is
//  scored as *staging* on a separate, lower band; Tier 3 never contributes.
//  Protected species are skipped entirely.
//

import Foundation

public struct SpawnResult: Equatable, Sendable {
    public let factor: FactorScore
    /// The argmax legal contributor — drives the spawn card copy + targeting.
    public let species: SpawnSpecies?
    public let needsDisclaimer: Bool
    /// True when the leader is a Tier-2 staging score (not an active spawn act).
    public let isStaging: Bool

    public var intensity: Double { factor.score }
}

public enum SpawnFactor: Sendable {

    /// True when at least one legal, sight-shootable species is within (or tapering
    /// into) its spawn window for this region/date — regardless of water temp. When
    /// false, spawn is OUT OF SEASON: the aggregator drops it and renormalises the
    /// rest, rather than scoring a zero that quietly costs points every winter.
    public static func isInSeason(_ input: ConditionsInput,
                                  config: ConditionsConfig = .default) -> Bool {
        let cfg = config.spawn
        let doy = dayOfYear(input.date)
        for species in SpeciesDatabase.species(in: input.region) {
            guard SpeciesLegality.canAutoRecommend(species) else { continue }
            if species.tier == .tier3 { continue }
            if !species.sightShootableSpawn { continue }
            guard species.present(in: input.region, latitude: input.latitude, longitude: input.longitude) else { continue }
            let m = species.window(for: input.region).membership(dayOfYear: doy, taperDays: cfg.windowTaperDays)
            if m > 0.05 { return true }
        }
        return false
    }

    public static func score(_ input: ConditionsInput,
                             config: ConditionsConfig = .default) -> SpawnResult {
        let cfg = config.spawn
        guard let waterTempF = input.waterTempF else {
            // No water temp → can't assess spawn; contribute nothing (and let the
            // missing-temp confidence penalty handle trust). Drops from the blend.
            return SpawnResult(factor: FactorScore(score: 0, label: "No water temp",
                                                   why: "No water-temp reading — spawn activity unknown"),
                               species: nil, needsDisclaimer: false, isStaging: false)
        }

        let doy = dayOfYear(input.date)
        var best: (intensity: Double, species: SpawnSpecies, staging: Bool)?

        // When water temp is only an estimate (no gage), damp spawn so a
        // guessed-warm night can't manufacture a full-strength spawn run.
        let damp = input.waterTempEstimated ? cfg.estimatedTempDamp : 1.0

        for species in SpeciesDatabase.species(in: input.region) {
            guard SpeciesLegality.canAutoRecommend(species) else { continue }  // never recommend protected
            if species.tier == .tier3 { continue }                            // never a warm-water spawn run
            if !species.sightShootableSpawn { continue }                       // cavity nesters (catfish) never headline
            guard species.present(in: input.region, latitude: input.latitude, longitude: input.longitude) else { continue }  // region + lat cap + basin gate

            let dateScore = species.window(for: input.region)
                .membership(dayOfYear: doy, taperDays: cfg.windowTaperDays)
            let tempScore = triangular(waterTempF, min: species.spawnMinF,
                                       peak: species.spawnPeakF, max: species.spawnMaxF)

            let intensity: Double
            let staging: Bool
            if species.tier == .tier2 {
                // Riverine drift spawners: score warm-backwater STAGING, capped low.
                staging = true
                if waterTempF < cfg.stagingTempFloorF {
                    intensity = 0
                } else {
                    intensity = cfg.stagingMaxScore * tempScore * dateScore * damp
                }
            } else {
                staging = false
                let flood = floodScore(for: species, stageTrend12hFt: input.stageTrend12hFt, cfg: cfg)
                intensity = (100 * tempScore * dateScore * flood * damp).clampedToScore
            }

            if intensity > (best?.intensity ?? -1) {
                best = (intensity, species, staging)
            }
        }

        guard let best, best.intensity > 0 else {
            return SpawnResult(factor: FactorScore(score: 0, label: "No active spawn run",
                                                   why: "No active spawn run for the season & temperature"),
                               species: nil, needsDisclaimer: false, isStaging: false)
        }

        // Only NAME a species when the spawn is strong enough to actually target
        // (≥ regime threshold). Below that we don't claim a specific fish — coarse
        // presence data can't be trusted for a weak/staging signal, and naming a
        // species that isn't really there is the credibility killer. §9 caveat.
        guard best.intensity >= cfg.regimeThreshold else {
            return SpawnResult(factor: FactorScore(score: best.intensity, label: "No active spawn run",
                                                   why: "No active spawn run — fish hold shallow on temperature, not spawning"),
                               species: nil, needsDisclaimer: false, isStaging: best.staging)
        }

        let disclaimer = SpeciesLegality.needsDisclaimer(best.species)
        return SpawnResult(
            factor: FactorScore(score: best.intensity,
                                label: best.staging ? "\(best.species.name) staging"
                                                    : "\(best.species.name) spawn",
                                why: whyText(best.species, intensity: best.intensity, staging: best.staging)),
            species: best.species,
            needsDisclaimer: disclaimer,
            isStaging: best.staging)
    }

    // MARK: - Components

    /// 0 at min/max, 1 at peak, linear between — soft spawn-temp edges. §5.2.
    static func triangular(_ t: Double, min: Double, peak: Double, max: Double) -> Double {
        if t <= min || t >= max { return 0 }
        if t == peak { return 1 }
        if t < peak { return (t - min) / Swift.max(0.0001, peak - min) }
        return (max - t) / Swift.max(0.0001, max - peak)
    }

    /// Rising water amplifies flood-dependent spawners; falling/blown-out water
    /// dampens them. Neutral 1.0; full dependence gets the full swing, partial
    /// gets half, none/river → 1.0 (no contribution here). §5.2.
    static func floodScore(for species: SpawnSpecies, stageTrend12hFt: Double?,
                           cfg: ConditionsConfig.Spawn) -> Double {
        guard species.floodDependence == .full || species.floodDependence == .partial,
              let trend = stageTrend12hFt else { return 1.0 }
        let raw: Double
        if trend >= 0 {
            raw = 1 + Swift.min(cfg.floodBonusCap - 1, cfg.floodBonusPerFt * trend)
        } else {
            raw = Swift.max(cfg.floodFallingFloor, 1 + cfg.floodBonusPerFt * trend)
        }
        // Partial dependence feels half the deviation from neutral.
        if species.floodDependence == .partial { return 1 + (raw - 1) * 0.5 }
        return raw
    }

    private static func whyText(_ s: SpawnSpecies, intensity: Double, staging: Bool) -> String {
        if staging {
            return "\(s.name) staging in warm backwaters — \(s.habitat)"
        }
        let strength = intensity >= 80 ? "Peak" : (intensity >= 60 ? "Active" : "Early")
        return "\(strength) \(s.name.lowercased()) spawn — \(s.habitat)"
    }

    private static func dayOfYear(_ date: Date) -> Int {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        return cal.ordinality(of: .day, in: .year, for: date) ?? 1
    }
}
