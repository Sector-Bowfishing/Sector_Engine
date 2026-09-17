//
//  ConditionsAggregator.swift
//  Sector — Bowfishing Conditions Engine v2
//
//  The one place that knows about weights, gates, regime, and confidence (§2).
//  Pipeline (§7): run the factor scorers → pick the regime → blend with that
//  regime's weight set (renormalized over the factors actually present) → add the
//  spawn boost → apply gate caps → compute confidence. Pure function:
//  ConditionsInput in, ConditionsResult out.
//

import Foundation

public enum ConditionsAggregator {

    public static func evaluate(_ rawInput: ConditionsInput,
                                config: ConditionsConfig = .default) -> ConditionsResult {

        // 0) Defense-in-depth: reconcile the categorical weather code against the
        // measured precip + cloud BEFORE anything reads it, so a lone false storm
        // code can never gate, tank seeability, or crush the sky factor — even if
        // the caller passed a raw (unsanitized) code.
        var input = rawInput
        input.weatherCode = WeatherCode.sanitized(input.weatherCode,
                                                  precipitation: input.precipitationInchNow,
                                                  cloudCover: input.cloudPct)

        // 1) Factor scorers. Always-present factors first.
        var scores: [FactorKey: FactorScore] = [
            .clarity:  ClarityFactor.score(input, config: config),
            .darkness: DarknessFactor.score(input, config: config),
            .wind:     WindFactor.score(input, config: config),
            .pressure: PressureFactor.score(input, config: config),
            .sky:      SkyFactor.score(input, config: config),
            .humidity: HumidityFactor.score(input, config: config),
        ]

        // Spawn participates only when we have a water temp to judge it against AND
        // a run is actually in season. Out of season it's not a bad night, it's an
        // inapplicable factor — scoring it zero quietly costs points every winter.
        // Excluding it lets the weighted blend renormalise over the rest (§step 3).
        let spawnResult = SpawnFactor.score(input, config: config)
        let spawnInSeason = SpawnFactor.isInSeason(input, config: config)
        let spawnPresent = input.waterTempF != nil && spawnInSeason
        if spawnPresent { scores[.spawn] = spawnResult.factor }

        // Dormant factors: present in the model but not in play tonight. Surfaced
        // so the UI can explain the dormancy instead of hiding it.
        var dormantFactors: [DormantFactor] = []
        if input.waterTempF != nil && !spawnInSeason {
            dormantFactors.append(DormantFactor(key: .spawn, label: "Out of season",
                                                reason: "No run — carp spawn Apr–Jun"))
        }

        if let wt = WaterTempFactor.score(input, config: config) { scores[.waterTemp] = wt }
        if let lvl = WaterLevelFactor.score(input, config: config) { scores[.level] = lvl }

        let generationLevel = input.generationLevel
            ?? CurrentFactor.classify(dischargeCfs: input.dischargeCfs,
                                      trendCfs: input.dischargeTrend12hCfs, cfg: config.current)
        if input.isTailwater {
            if let cur = CurrentFactor.score(input, config: config) { scores[.current] = cur }
        } else {
            scores[.current] = CurrentFactor.score(input, config: config)  // neutral 90
        }

        // 2) Regime.
        let spawnScore = spawnPresent ? spawnResult.intensity : 0
        let regime: ConditionsRegime
        if spawnScore >= config.spawn.regimeThreshold {
            regime = .spawn
        } else if input.isTailwater {
            regime = .tailwater
        } else {
            regime = .normal
        }

        // 3) Weighted blend over present factors, weights renormalized.
        let weightSet = config.weights.set(for: regime)
        let presentKeys = FactorKey.allCases.filter { scores[$0] != nil }
        let totalWeight = presentKeys.reduce(0.0) { $0 + weightSet.weight(for: $1) }
        var weighted = 0.0
        var normWeight: [FactorKey: Double] = [:]
        for key in presentKeys {
            let w = totalWeight > 0 ? weightSet.weight(for: key) / totalWeight : 0
            normWeight[key] = w
            weighted += (scores[key]?.score ?? 0) * w
        }

        // 4) Spawn boost — can lift an already-good spawn night (§7.3). Suppressed
        // when the spawn signal rests on an estimated water temp (no real gage).
        var raw = weighted
        if regime == .spawn && !input.waterTempEstimated {
            let boost = Swift.min(config.spawnBoost.maxBoost,
                                  Swift.max(0, (spawnScore - config.spawn.regimeThreshold) * config.spawnBoost.perPointAboveThreshold))
            raw += boost
        }

        // 5) Gates + the seeability ceiling — "can I see fish through the surface?"
        // is the master constraint, so clarity + surface calm CAP the score rather
        // than just voting in the blend.
        let gates = ConditionsGates.evaluate(input, config: config, generationLevel: generationLevel)
        // A hard gate (softness 0) is a flat ceiling. A soft gate pulls the score most
        // of the way down but keeps a slice of what the night earned, so two capped
        // nights don't land on the identical number and lose their order.
        let gateCapped = gates.reduce(raw) { acc, hit in
            let cap = Double(hit.cap)
            guard acc > cap else { return acc }
            return Swift.min(acc, cap + (acc - cap) * hit.softness)
        }
        let ceiling = seeabilityCeiling(input, config: config)
        let capped = Swift.min(gateCapped, ceiling)
        let finalScore = Int(capped.clampedToScore.rounded())

        // 6) Confidence. §8.
        let confidence = confidenceScore(input, config: config, regime: regime,
                                         spawnScore: spawnScore)

        // 7) Breakdown rows (stable order, active/renormalized weight).
        // Integer weights via largest-remainder so they sum to EXACTLY 100 —
        // rounding each independently could show a column that adds to 99 or 101,
        // which reads as an error the moment a user totals it.
        let weightPctByKey = largestRemainderPercents(normWeight, keys: presentKeys)
        let factors: [FactorBreakdown] = FactorKey.allCases.compactMap { key in
            guard let fs = scores[key] else { return nil }
            // Signed points off the 50 baseline: renormalized weight × (sub − 50).
            // Σ contribution = weighted − 50, so baseline + Σ reconciles to the
            // pre-gate score (a gate/ceiling shows as a separate row in the UI).
            let contribution = (normWeight[key] ?? 0) * (Double(fs.intScore) - 50)
            return FactorBreakdown(key: key,
                                   score: fs.intScore,
                                   weightPct: weightPctByKey[key] ?? 0,
                                   label: fs.label,
                                   why: fs.why,
                                   contribution: contribution)
        }

        // 8) Top reasons — binding gate first, then strengths, then the limiter.
        var topReasons = reasons(scores: scores, gates: gates, regime: regime,
                                 spawn: spawnPresent ? spawnResult : nil)
        // If the seeability ceiling is the BINDING constraint — i.e. it holds the
        // score below whatever the gates would cap it to — say so as the primary
        // reason. This fires even when a gate is also present: with a gate cap of
        // 30 and a ceiling of 20 the shown score is 20, and citing only the gate's
        // "capped at 30" would name a number above the score on screen.
        if ceiling < gateCapped - 3 {
            let viz = ClarityFactor.visibilityFt(input, config: config)
            let rainy = (config.seeability.weatherComponent[input.weatherCode]
                         ?? config.seeability.defaultWeatherComponent) < 0.8
            let note: String
            if input.windMph > 12 {
                note = "Held back by chop — \(Int(input.windMph.rounded())) mph on the surface"
            } else if rainy {
                note = "Held back by wet weather — rain churning the surface"
            } else {
                note = "Held back by clarity — ~\(String(format: "%.1f", viz)) ft of sightline"
            }
            topReasons.insert(note, at: 0)
            topReasons = Array(topReasons.prefix(4))
        }

        // 9) Where to look.
        let cards = WhereToLookEngine.cards(input, regime: regime,
                                            spawn: spawnPresent ? spawnResult : nil,
                                            generationLevel: generationLevel)

        return ConditionsResult(
            score: finalScore,
            band: ConditionsBand(score: finalScore),
            regime: regime,
            confidence: confidence,
            confidenceBand: ConfidenceBand(score: confidence),
            factors: factors,
            gates: gates,
            topReasons: topReasons,
            whereToLook: cards,
            closingLine: WhereToLookEngine.closingLine,
            spawnSpeciesName: spawnPresent ? spawnResult.species?.name : nil,
            spawnNeedsDisclaimer: spawnPresent ? spawnResult.needsDisclaimer : false,
            baseline: 50,
            dormantFactors: dormantFactors)
    }

    /// Whole-percent weights that sum to exactly 100. Floors each, then hands the
    /// leftover points to the largest fractional remainders (Hamilton's method).
    static func largestRemainderPercents(_ normWeight: [FactorKey: Double],
                                         keys: [FactorKey]) -> [FactorKey: Int] {
        let scaled = keys.map { (normWeight[$0] ?? 0) * 100 }
        var floors = scaled.map { Int($0.rounded(.down)) }
        let leftover = 100 - floors.reduce(0, +)
        if leftover > 0 {
            let byRemainder = scaled.enumerated()
                .sorted { ($0.element - $0.element.rounded(.down)) > ($1.element - $1.element.rounded(.down)) }
                .map(\.offset)
            for i in 0..<Swift.min(leftover, byRemainder.count) { floors[byRemainder[i]] += 1 }
        }
        return Dictionary(uniqueKeysWithValues: zip(keys, floors))
    }

    // MARK: - Seeability ceiling

    /// 0…100 ceiling on the final score: how well you can see fish through the
    /// surface = clarity (visibility) × surface calm (wind). The master
    /// constraint — a pile of "good" factors can't lift water you can't shoot.
    static func seeabilityCeiling(_ input: ConditionsInput, config: ConditionsConfig) -> Double {
        guard config.seeability.enabled else { return 100 }
        let viz = ClarityFactor.visibilityFt(input, config: config)
        var clarityComp = interp(viz, curve: config.seeability.clarityCurve.map { ($0.ft, $0.factor) })
        // Estimated (no-gage) clarity can't claim a perfect "definitely can see" —
        // unknown water must not hold a 100 ceiling over the whole score. Keyed on
        // hasTurbidityGage (not FNU presence) so a derived FNU without a real gage
        // is still treated as an estimate — matches ClarityFactor.score.
        if !input.hasTurbidityGage {
            clarityComp = Swift.min(clarityComp, config.seeability.estimatedClarityComponentCap)
        }
        let windComp = interp(input.windMph, curve: config.seeability.windCurve.map { ($0.mph, $0.factor) })
        // Active rain/storm hammers the surface and pours in runoff right now —
        // independent of the turbidity gage or the 3-day rain total.
        let weatherComp = config.seeability.weatherComponent[input.weatherCode]
            ?? config.seeability.defaultWeatherComponent
        return (100 * clarityComp * windComp * weatherComp).clampedToScore
    }

    /// Piecewise-linear lookup; clamps to the first/last factor outside the range.
    private static func interp(_ x: Double, curve: [(Double, Double)]) -> Double {
        guard let first = curve.first else { return 1 }
        if x <= first.0 { return first.1 }
        for i in 1..<curve.count {
            let lo = curve[i - 1], hi = curve[i]
            if x <= hi.0 {
                let t = (x - lo.0) / (hi.0 - lo.0)
                return lo.1 + t * (hi.1 - lo.1)
            }
        }
        return curve.last!.1
    }

    // MARK: - Confidence

    static func confidenceScore(_ input: ConditionsInput,
                                config: ConditionsConfig,
                                regime: ConditionsRegime,
                                spawnScore: Double) -> Int {
        let cfg = config.confidence
        var c = cfg.base
        if !input.hasTurbidityGage { c -= cfg.noTurbidityGage }
        if input.waterTempF == nil || input.waterTempEstimated { c -= cfg.estimatedWaterTemp }
        if input.isTailwater && !input.hasGenerationForecast { c -= cfg.tailwaterNoGenForecast }
        c -= Swift.min(cfg.perForecastDayCap, cfg.perForecastDay * Double(Swift.max(0, input.forecastDayIndex)))

        // Unknown turbidity right around the blown-out gate is the shakiest call.
        if input.turbidityType == .unknown {
            let vis = ClarityFactor.visibilityFt(input, config: config)
            if vis < config.gates.blownOutVisibilityFt + 1.0 { c -= cfg.unknownTurbidityNearGate }
        }

        // Strong, fully-aligned spawn window earns trust.
        if regime == .spawn && spawnScore >= 80 { c += cfg.strongSpawnBonus }

        // Plausibility guard: a spawn call resting on an ESTIMATED water temp
        // (no gage) is not something we can vouch for — never let it read "High".
        var score = Int(c.clampedToScore.rounded())
        if regime == .spawn && input.waterTempEstimated {
            score = Swift.min(score, cfg.spawnEstimatedConfidenceCeiling)
        }
        return score
    }

    // MARK: - Reasons

    private static func reasons(scores: [FactorKey: FactorScore],
                                gates: [GateHit],
                                regime: ConditionsRegime,
                                spawn: SpawnResult?) -> [String] {
        var out: [String] = []

        // Binding gate first.
        if let gate = gates.min(by: { $0.cap < $1.cap }) {
            // "Capped" is a promise about the number on screen — only true of a hard
            // gate. A soft gate holds the night back without pinning it to the cap.
            out.append((gate.softness > 0 ? "Held back: " : "Capped: ") + gate.reason)
        }
        // Spawn headline next when in spawn regime.
        if regime == .spawn, let s = spawn, s.intensity > 0 {
            out.append(s.factor.why)
        }
        // Strongest positives.
        // Humidity is excluded alongside spawn: a mid/high humidity score means
        // "fog unlikely", which is not a strength worth headlining, and a fog
        // WARNING (e.g. "patchy fog possible", ~72) must never read as a positive.
        let positives = FactorKey.allCases
            .compactMap { key -> (FactorKey, FactorScore)? in scores[key].map { (key, $0) } }
            .filter { $0.0 != .spawn && $0.0 != .humidity && $0.1.score >= 70 }
            .sorted { $0.1.score > $1.1.score }
            .prefix(2)
            .map { $0.1.why }
        out.append(contentsOf: positives)

        // The single biggest drag, if not already covered by a gate. Inclusive of
        // exactly 45 so a "Fog likely — running the boat is dangerous" night (the
        // humidity factor's fog-likely score is 45) can surface as the limiter
        // instead of dropping out on a strict < 45.
        if let limiter = FactorKey.allCases
            .compactMap({ key -> FactorScore? in scores[key] })
            .filter({ $0.score <= 45 })
            .min(by: { $0.score < $1.score }) {
            if !out.contains(limiter.why) { out.append(limiter.why) }
        }

        // De-dup while preserving order, cap to 4.
        var seen = Set<String>()
        return out.filter { seen.insert($0).inserted }.prefix(4).map { $0 }
    }
}
