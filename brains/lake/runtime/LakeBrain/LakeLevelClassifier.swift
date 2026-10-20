//
//  LakeLevelClassifier.swift
//  Sector — Lake Brain: current level → LakeState (pure; no I/O)
//
//  v2 rules (`lake-level-rules-v2`; pre-registered in
//  docs/brains/LAKE_BRAIN_RULES_V2_PREREGISTRATION.md, spec §7):
//    levelState       operator zone / guide FIRST. Above the top of conservation
//                     (CWMS guide curve) = FLOOD_POOL. Outside the zone =
//                     BELOW_ZONE / ABOVE_ZONE. No operator zone → UNKNOWN.
//    historicalState  gated by the history tier (≥ 5 complete years): inside
//                     p10–p90 NORMAL; outside UNUSUAL; outside p02–p98
//                     VERY_UNUSUAL only at tier FULL (≥ 15 years). PROVISIONAL
//                     (5–9 y) carries the flag `historicalProvisional`.
//    trendState       RAPID when |Δ24h| > max(seasonal p95 |Δ24h|, 0.25 ft);
//                     otherwise the 72 h mean rate against a floor (0.10 ft/day
//                     regulated, 0.05 ft/day natural): STABLE / RISING / FALLING.
//                     No 72 h change → the 24 h change, flag `trend24hFallback`.
//                     The v1 seasonal-p50 term is removed.
//    floodPoolState   only where the operator publishes a flood-pool bottom.
//    PROXY            (a nearby gage) gets a trend and nothing else.
//  Each classification is a separate field; none is folded into another.
//

import Foundation

public struct LakeLevelInputs: Sendable {
    public var lakeId: String
    public var binding: LakeSourceBinding?
    public var capabilityIfUnbound: LevelSourceCapability
    /// Directory normal full pool and how it was sourced.
    public var fullPoolFt: Double?
    public var poolBasisIsFullPool: Bool
    public var poolConfidenceLow: Bool
    /// One entry per live ref in binding order: readings oldest first (may be empty) + fetch error.
    public var live: [(ref: LevelSeriesRef, readings: [LevelObservation], error: String?)]
    /// Extra hourly readings for the PRIMARY source (shared archive), merged for change windows.
    public var archivedHourly: [LevelObservation]
    public var guide: LakeGuideForDay?
    public var baseline: LakeLevelBaseline?
    public var now: Date
    public var processingVersion: String?
}

public enum LakeLevelClassifier {

    /// STABLE floor, ft/day, regulated reservoirs (`poolBasis == fullPool`).
    public static let stableFloorRegulatedFt = 0.10
    /// STABLE floor, ft/day, natural lakes.
    public static let stableFloorNaturalFt = 0.05
    /// RAPID never triggers below this 24 h change, with or without a rate baseline.
    public static let rapidFloorFt = 0.25

    struct Selected {
        var ref: LevelSeriesRef
        var series: [LevelObservation]
        var latest: LevelObservation
        var stale: Bool
        var usedFallback: Bool
    }

    /// Past due by more than two cadences.
    static func isStale(_ obsAt: Date, ref: LevelSeriesRef, now: Date) -> Bool {
        now.timeIntervalSince(obsAt) > Double(ref.lagMin + 3 * ref.cadenceMin) * 60
    }

    /// First fresh live source in binding order; if none is fresh, the most recent reading (flagged stale).
    static func select(_ live: [(ref: LevelSeriesRef, readings: [LevelObservation], error: String?)], now: Date) -> Selected? {
        for (i, x) in live.enumerated() {
            guard let last = x.readings.last, !isStale(last.at, ref: x.ref, now: now) else { continue }
            return Selected(ref: x.ref, series: x.readings, latest: last, stale: false, usedFallback: i > 0)
        }
        let newest = live.enumerated().compactMap { i, x in x.readings.last.map { (i, x, $0) } }.max { $0.2.at < $1.2.at }
        guard let (i, x, last) = newest else { return nil }
        return Selected(ref: x.ref, series: x.readings, latest: last, stale: true, usedFallback: i > 0)
    }

    static func r2(_ x: Double) -> Double { (x * 100).rounded() / 100 }
    static func r1(_ x: Double) -> Double { (x * 10).rounded() / 10 }

    public static func changes(_ series: [LevelObservation], latest: LevelObservation) -> LakeLevelChange {
        func back(_ h: Double, tol: Double) -> Double? {
            LakeLevelSeries.value(at: latest.at.addingTimeInterval(-h * 3600), in: series, tolerance: tol * 60).map { r2(latest.ft - $0) }
        }
        return LakeLevelChange(h1: back(1, tol: 20), h6: back(6, tol: 45), h24: back(24, tol: 90),
                               d3: back(72, tol: 180), d7: back(168, tol: 180))
    }

    public static func levelState(current: Double, guide: LakeGuideForDay?) -> LakeLevelState {
        if let fp = guide?.floodPoolBottomFt, current > fp { return .floodPool }
        guard let z = guide?.zone else { return .unknown }
        if current < z.bottomFt { return .belowZone }
        if current > z.topFt { return .aboveZone }
        return .inZone
    }

    public static func floodPoolState(current: Double, guide: LakeGuideForDay?) -> LakeFloodPoolState {
        guard let fp = guide?.floodPoolBottomFt else { return .unknown }
        return current > fp ? .inFloodPool : .normal
    }

    /// Rules v2 R2. `delta24h` / `delta72h` are the level changes over 24 h / 72 h (nil = unavailable).
    /// Returns the label, the effective RAPID threshold, the rate percentile and the quality flags it raised.
    public static func trend(delta24h: Double?, delta72h: Double? = nil, day: LakeBaselineDay?, regulated: Bool = true)
        -> (LakeTrendState, rapidThreshold: Double?, ratePct: Double?, flags: [String]) {
        guard let d24 = delta24h else { return (.unknown, nil, nil, []) }
        var flags: [String] = []
        let a = abs(d24)
        var rapid = rapidFloorFt
        var pct: Double?
        if let q = day?.rateQ, let p95 = LakeBaselineBuilder.at(95, q) {
            rapid = max(p95, rapidFloorFt)
            pct = r1(LakeBaselineBuilder.percentile(of: a, grid: q))
        } else {
            flags.append("rateBaselineLimited")
        }
        if a > rapid { return (d24 > 0 ? .risingRapidly : .fallingRapidly, rapid, pct, flags) }
        let mean: Double
        if let d72 = delta72h { mean = d72 / 3 } else { mean = d24; flags.append("trend24hFallback") }
        let floor = regulated ? stableFloorRegulatedFt : stableFloorNaturalFt
        if abs(mean) <= floor { return (.stable, rapid, pct, flags) }
        return (mean > 0 ? .rising : .falling, rapid, pct, flags)
    }

    /// R1 gating on the band edges: VERY_UNUSUAL is published only at tier FULL (below it the value is reported UNUSUAL);
    /// PROVISIONAL carries the quality flag `historicalProvisional`; tier NONE is INSUFFICIENT_HISTORY.
    public static func historicalState(current: Double, p02: Double, p10: Double, p90: Double, p98: Double,
                                       tier: LakeHistoricalTier) -> (LakeHistoricalState, flags: [String]) {
        if tier == .none { return (.insufficientHistory, []) }
        var s: LakeHistoricalState = (current < p02 || current > p98) ? .veryUnusual
            : (current < p10 || current > p90) ? .unusual : .normal
        if s == .veryUnusual, tier != .full { s = .unusual }
        return (s, tier == .provisional ? ["historicalProvisional"] : [])
    }

    public static func historical(current: Double, baseline: LakeLevelBaseline?, doy: Int)
        -> (LakeHistoricalState, percentile: Double?, band: LakeSeasonalBand?, flags: [String]) {
        guard let b = baseline, b.historicalTier != .none, let day = b.day(doy), let q = day.levelQ,
              let p02 = LakeBaselineBuilder.at(2, q), let p10 = LakeBaselineBuilder.at(10, q),
              let p50 = LakeBaselineBuilder.at(50, q), let p90 = LakeBaselineBuilder.at(90, q),
              let p98 = LakeBaselineBuilder.at(98, q) else { return (.insufficientHistory, nil, nil, []) }
        let band = LakeSeasonalBand(p02: r2(p02), p10: r2(p10), p50: r2(p50), p90: r2(p90), p98: r2(p98), basisYears: b.basisYears.count,
                                    windowDays: b.windowDays, sampleCount: day.n)
        let pct = r1(LakeBaselineBuilder.percentile(of: current, grid: q))
        let (state, flags) = historicalState(current: current, p02: p02, p10: p10, p90: p90, p98: p98, tier: b.historicalTier)
        return (state, pct, band, flags)
    }

    static func readiness(binding: LakeSourceBinding?, kind: LakeStateKind, stale: Bool,
                          hasGuide: Bool, baseline: LakeBaselineStatus) -> LakeBrainReadiness {
        guard let binding, binding.status == .reviewed else { return .discovered }
        if binding.capability == .noSource { return .profiled }
        if kind == .unavailable || stale { return .degraded }
        if kind == .observed, hasGuide, baseline == .sufficient { return .beta }
        return .calibration
    }

    // MARK: - Facts (factual sentences only; no fish wording)

    static func ft(_ x: Double) -> String { String(format: "%.2f ft", x) }
    static func signed(_ x: Double) -> String { String(format: "%@%.2f ft", x >= 0 ? "+" : "−", abs(x)) }

    static func localTime(_ d: Date, tz: TimeZone) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = tz
        f.dateFormat = "MMM d, h:mm a zzz"
        return f.string(from: d)
    }

    static func ordinal(_ n: Int) -> String {
        let s = (11...13).contains(n % 100) ? "th" : ([1: "st", 2: "nd", 3: "rd"][n % 10] ?? "th")
        return "\(n)\(s)"
    }

    // MARK: - Evaluate

    public static func evaluate(_ x: LakeLevelInputs) -> LakeLevelStateRecord {
        let now = x.now
        let gen = BrainPlatform.iso(now)
        let tz = TimeZone(identifier: x.binding?.timeZone ?? "UTC") ?? TimeZone(identifier: "UTC")!
        var flags: [String] = []
        var facts: [String] = []
        let capability = x.binding?.capability ?? x.capabilityIfUnbound

        func provenance(_ readiness: LakeBrainReadiness, sources: [BrainSourceRef], inputAge: Double?) -> BrainProvenance {
            BrainProvenance(brainId: LakeBrainSpec.brainId, brainVersion: LakeBrainSpec.brainVersion,
                            modelVersion: LakeBrainSpec.modelVersion, processingVersion: x.processingVersion,
                            generatedAt: gen, sources: sources.isEmpty ? nil : sources, inputAgeHours: inputAge,
                            readiness: readiness.rawValue, qualityFlags: flags.isEmpty ? nil : flags,
                            validationRef: "/validation/\(LakeBrainSpec.brainId)")
        }

        for l in x.live where l.error != nil { flags.append("sourceError:\(l.ref.sourceId)") }

        guard x.binding?.status == .reviewed, let sel = select(x.live, now: now) else {
            if x.binding?.status != .reviewed { flags.append("bindingNotReviewed") } else { flags.append("noReading") }
            let readiness = readiness(binding: x.binding, kind: .unavailable, stale: true, hasGuide: false,
                                      baseline: x.baseline?.status ?? .none)
            return LakeLevelStateRecord(
                lakeId: x.lakeId, schemaVersion: LakeBrainSpec.stateSchemaVersion, kind: .unavailable,
                sourceCapability: capability, unit: nil, levelState: .unknown, trendState: .unknown,
                historicalState: .insufficientHistory, floodPoolState: .unknown,
                baselineStatus: x.baseline?.status ?? .none, historicalTier: x.baseline?.historicalTier ?? LakeHistoricalTier.none, facts: nil,
                freshness: LakeStateFreshness(generatedAt: gen, sourceObservationAt: nil, freshUntil: nil,
                                              nextCheckAt: BrainPlatform.iso(now.addingTimeInterval(3600)), stale: true,
                                              refreshReason: x.binding?.status == .reviewed ? "no reading from any bound source" : "no reviewed source binding"),
                provenance: provenance(readiness, sources: [], inputAge: nil))
        }

        let kind: LakeStateKind = sel.ref.capability == .nearbyGaugeProxy ? .proxy : .observed
        let current = r2(sel.latest.ft + sel.ref.datumOffsetFt)
        let ageH = r2(now.timeIntervalSince(sel.latest.at) / 3600)
        if sel.usedFallback, let p = x.live.first {
            flags.append("primarySourceStale:\(p.ref.sourceId)" + (p.readings.last.map { "@\(BrainPlatform.iso($0.at))" } ?? ""))
            flags.append("fallbackSource:\(sel.ref.sourceId)")
        }
        if sel.stale { flags.append("sourceStale:\(sel.ref.sourceId)") }

        // Cross-source datum check where a fallback and the primary overlap.
        if x.live.count > 1, let p = x.live.first, let f = x.live.dropFirst().first, !p.readings.isEmpty, !f.readings.isEmpty {
            var diffs: [Double] = []
            for o in p.readings {
                if let v = LakeLevelSeries.value(at: o.at, in: f.readings, tolerance: 15 * 60) { diffs.append(o.ft - (v + f.ref.datumOffsetFt)) }
            }
            if diffs.count >= 6 {
                let med = LakeBaselineBuilder.quantile(diffs.sorted(), 50)
                if abs(med) > 0.10 { flags.append("fallbackDatumDisagreement:\(String(format: "%.2f", med))ft") }
            }
        }

        var series = sel.series
        if !sel.usedFallback { series = LakeLevelSeries.merge(series + x.archivedHourly) }
        let change = changes(series, latest: sel.latest)
        let delta24 = change.h24
        let doy = LakeLevelCalendar.doy365(LakeLevelCalendar.dayString(now, timeZone: tz)) ?? 1
        let day = x.baseline?.day(doy)
        var (trendState, rapidAt, ratePct, trendFlags) = trend(delta24h: delta24, delta72h: change.d3, day: day,
                                                               regulated: x.poolBasisIsFullPool)
        if delta24 != nil, day?.rateQ != nil, x.baseline?.status != .sufficient { trendFlags.append("rateBaselineLimited") }
        flags += trendFlags

        let src = sel.ref
        var level: LakeLevelState = .unknown
        var hist: LakeHistoricalState = .insufficientHistory
        var pct: Double?
        var band: LakeSeasonalBand?
        var flood: LakeFloodPoolState = .unknown
        var poolDiff: Double?
        var poolRef: String?
        var guideFt: Double?
        var guideDiff: Double?

        facts.append("\(ft(current)) at \(localTime(sel.latest.at, tz: tz)) (\(src.providerName) \(src.station)).")

        if kind == .proxy {
            flags.append("proxyTrendOnly")
            ratePct = nil; rapidAt = nil
            if case .risingRapidly = trendState { trendState = .rising }
            if case .fallingRapidly = trendState { trendState = .falling }
            facts.append("This is a nearby gauge reading, not the lake's pool elevation.")
        } else {
            level = levelState(current: current, guide: x.guide)
            flood = floodPoolState(current: current, guide: x.guide)
            let h = historical(current: current, baseline: x.baseline, doy: doy)
            (hist, pct, band) = (h.0, h.percentile, h.band)
            flags += h.flags
            if let fp = x.fullPoolFt, x.poolBasisIsFullPool, !x.poolConfidenceLow {
                poolDiff = r2(current - fp)
                poolRef = "engine-directory:fullPoolFt"
                facts.append("\(signed(poolDiff!)) vs normal full pool (\(ft(fp))).")
            }
            if let g = x.guide?.guideFt {
                guideFt = g; guideDiff = r2(current - g)
                facts.append("\(signed(guideDiff!)) vs the operator guide curve for today (\(ft(g))).")
            }
            if let z = x.guide?.zone {
                let where_: String = level == .inZone ? "Inside" : (level == .belowZone ? "Below" : "Above")
                facts.append("\(where_) the operator zone for today (\(ft(z.bottomFt))–\(ft(z.topFt)), \(z.bottomLabel) to \(z.topLabel)).")
            } else if x.guide == nil {
                flags.append("noOperatorGuide")
            }
            if flood == .inFloodPool { facts.append("Above the top of conservation pool: water is in the flood-control pool.") }
            if x.guide?.floodPoolBottomFt == nil { flags.append("noOperatorFloodPoolThreshold") }
            if let p = pct, let b = band {
                facts.append("Near the \(ordinal(Int(p.rounded()))) percentile for this time of year (\(b.basisYears) years, ±\(b.windowDays) days).")
            } else {
                flags.append("historicalBaseline:\(x.baseline?.status.rawValue ?? LakeBaselineStatus.none.rawValue)")
            }
        }
        if let d = delta24 {
            facts.append(abs(d) < 0.005 ? "Unchanged over 24 h." : "\(d > 0 ? "Up" : "Down") \(ft(abs(d))) over 24 h.")
        }

        // Freshness
        let freshUntil = sel.latest.at.addingTimeInterval(Double(src.cadenceMin + src.lagMin) * 60)
        let stale = sel.stale
        let cadence = Double(src.cadenceMin) * 60
        let rapid = trendState == .risingRapidly || trendState == .fallingRapidly
        let next: Date
        let reason: String
        if stale { next = now.addingTimeInterval(cadence); reason = "source stale: check again after one source cadence" }
        else if rapid { next = max(freshUntil, now.addingTimeInterval(cadence)); reason = "rapid change: next source observation" }
        else { next = max(freshUntil, now.addingTimeInterval(max(cadence, 2 * 3600))); reason = "scheduled: stable lake, 2 h" }

        let baselineStatus = x.baseline?.status ?? .none
        let readiness = readiness(binding: x.binding, kind: kind, stale: stale, hasGuide: x.guide != nil, baseline: baselineStatus)
        var sources = [BrainSourceRef(sourceType: src.capability.rawValue, sourceId: src.sourceId,
                                      lastObservationAt: BrainPlatform.iso(sel.latest.at))]
        if let g = x.guide { sources.append(BrainSourceRef(sourceType: "operatorGuide", sourceId: g.source, lastObservationAt: nil)) }
        if let b = x.baseline, b.status != .none {
            sources.append(BrainSourceRef(sourceType: "baseline", sourceId: b.baselineVersion, lastObservationAt: b.historyEnd))
        }
        return LakeLevelStateRecord(
            lakeId: x.lakeId, schemaVersion: LakeBrainSpec.stateSchemaVersion, kind: kind, sourceCapability: capability,
            currentElevationFt: current, unit: "ft", datum: x.binding?.datum, observationTime: BrainPlatform.iso(sel.latest.at),
            sourceAgeHours: ageH, differenceFromNormalPoolFt: poolDiff, normalPoolRef: poolRef,
            guideFt: guideFt, differenceFromGuideFt: guideDiff, operatingZone: kind == .proxy ? nil : x.guide?.zone,
            operatorLevels: kind == .proxy || (x.guide?.levels.isEmpty ?? true) ? nil : x.guide?.levels,
            change: change, levelState: level, trendState: trendState, historicalState: hist, floodPoolState: flood,
            seasonalPercentile: pct, rateOfChangePercentile: ratePct, rapidChangeThresholdFt: rapidAt.map(r2),
            seasonalBand: band, baselineStatus: baselineStatus, historicalTier: x.baseline?.historicalTier ?? LakeHistoricalTier.none, facts: facts,
            freshness: LakeStateFreshness(generatedAt: gen, sourceObservationAt: BrainPlatform.iso(sel.latest.at),
                                          freshUntil: BrainPlatform.iso(freshUntil), nextCheckAt: BrainPlatform.iso(next),
                                          stale: stale, refreshReason: reason),
            provenance: provenance(readiness, sources: sources, inputAge: ageH))
    }
}
