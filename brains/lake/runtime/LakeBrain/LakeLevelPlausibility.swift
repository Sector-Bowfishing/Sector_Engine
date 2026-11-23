//
//  LakeLevelPlausibility.swift
//  Sector — Lake Brain: physically plausible level readings (pure; no I/O)
//
//  Why (Sector_Ops #51, 2026-11-23): Lake Tahoe's newest USACE manual reading was 6,226,054 ft (a decimal slip; the lake is at
//  about 6,226.05 ft) and the Brain published it as the current level, "+6.2 million ft vs full pool, rising rapidly". Its daily
//  history also holds about a dozen older slips (622.83 ft, 62,223.31 ft, 2014–2016). Nothing checked that a reading could be water.
//
//  0. Anywhere: a lake surface in the US lies between −300 ft (below Death Valley, −282 ft, the lowest land) and 14,505 ft (the
//     summit of Mount Whitney). A reading outside that is not a level on any datum. This is a backstop for the case rule 1
//     cannot judge (a series whose readings are ALL wrong looks like a series on another datum); it is not the per-lake rule.
//
//  Two per-lake rules, data-driven. A reading that fails either is REJECTED: it is never published, never used for a
//  change window, a trend or a baseline. The raw value is reported as a warning. The archive itself is never edited.
//
//  1. Level band. The lake's own record sets it:
//       lo, hi  = p01 and p99 of the lake's daily history (≥ 30 days; robust to a minority of slips, which is what the record holds),
//                 widened to include the directory full pool when that full pool is itself inside the band below.
//                 No usable history → the directory full pool alone (lo = hi = full pool).
//       margin  = max(hi − lo, 50 ft): the lake's own recorded range again, on each side, and never less than 50 ft.
//       band    = [lo − margin, hi + margin].
//     A reading outside the band is implausible. A decimal slip moves a value by 90 % (÷10) or 900 % (×10), so at any lake above
//     ~60 ft of elevation it lands far outside; a real drawdown or flood that is new to the record moves the level by a fraction of
//     the lake's range. The 50 ft floor is there for lakes with a narrow record (Tahoe's p01–p99 is ~6 ft): a level 50 ft beyond
//     anything the lake has recorded is not a level the lake can reach between two runs.
//     The band must describe the series it judges. When fewer than half of a live series' readings are inside it (the history
//     is on another datum: the `historyLiveMismatch` lakes), the band is re-centred on that series' own median with the same
//     width. A live series with no reference at all is judged against its own median ± 50 ft, and only with ≥ 3 readings
//     (fewer cannot say which reading is the odd one out; rules 0 and 2 still apply).
//
//  2. Step. Between consecutive accepted readings of one series, a change of more than
//       stepToleranceFt + maxRateFtPerHour × hours apart     (10 ft + 2 ft/h)
//     is impossible. 2 ft/h (48 ft/day) is eight times the Brain's own FAST tier (1 ft in 6 h, LakeLevelValidity) and above any
//     reservoir change in the committed fixtures and goldens (checked when this rule was set: see the PR). 10 ft is the
//     baseline's existing spike tolerance (LakeLevelBaseline.spikeToleranceFt): it absorbs a single noisy reading at any gap.
//     The walk starts from the reading closest to the series median (the older on a tie), so one bad reading cannot make the
//     good ones look like steps.
//
//  History (LakeBaselineBuilder): rule 1 with the history's own band leaves slip days out of both climatologies, before the
//  neighbour spike filter runs; both kinds are listed in the baseline's `excludedSpikeDays` (the #218 field, extended). The
//  neighbour filter (`spikeDays`) keeps catching isolated errors that are inside the band.
//

import Foundation

public enum LakeLevelPlausibility {

    /// Rule 0: no lake surface in the US is outside these elevations, on any datum (Death Valley −282 ft; Mount Whitney 14,505 ft).
    public static let absoluteMinFt = -300.0
    public static let absoluteMaxFt = 14_505.0
    static func physicallyPossible(_ ft: Double) -> Bool { ft.isFinite && ft >= absoluteMinFt && ft <= absoluteMaxFt }

    /// Quantiles of the daily history that bound the lake's recorded range (robust to a minority of slips).
    public static let rangeLowQ = 1.0
    public static let rangeHighQ = 99.0
    /// Minimum margin, ft, added on each side of the recorded range.
    public static let minMarginFt = 50.0
    /// Daily history rows needed before the history sets the band.
    public static let minHistoryDays = 30
    /// A series with no reference is judged against its own median only with at least this many readings.
    public static let minSeriesForSelfBand = 3
    /// Step rule: tolerance at any gap (== LakeLevelBaseline.spikeToleranceFt) plus a maximum sustained rate.
    public static let stepToleranceFt = LakeLevelBaseline.spikeToleranceFt
    public static let maxRateFtPerHour = 2.0

    /// The lake's reference: the recorded range [lo, hi] and the margin on each side.
    public struct Reference: Equatable, Sendable {
        public var lo: Double
        public var hi: Double
        public var marginFt: Double
        public var basis: String
        public var lowFt: Double { lo - marginFt }
        public var highFt: Double { hi + marginFt }
        public func contains(_ ft: Double) -> Bool { ft >= lowFt && ft <= highFt }
    }

    public struct Rejection: Equatable, Sendable {
        public var sourceId: String
        public var at: Date
        /// The reading as published by the source (before the binding's datum offset).
        public var rawFt: Double
        public var reason: String
    }

    static func median(_ xs: [Double]) -> Double? {
        guard !xs.isEmpty else { return nil }
        let s = xs.sorted()
        return s.count % 2 == 1 ? s[s.count / 2] : (s[s.count / 2 - 1] + s[s.count / 2]) / 2
    }

    static func margin(_ lo: Double, _ hi: Double) -> Double { max(hi - lo, minMarginFt) }

    /// The lake's reference from its daily history (binding datum) and the directory full pool. nil when there is neither.
    public static func reference(historyFt: [Double], fullPoolFt: Double?) -> Reference? {
        let xs = historyFt.filter(physicallyPossible).sorted()
        if xs.count >= minHistoryDays {
            var lo = LakeBaselineBuilder.quantile(xs, rangeLowQ), hi = LakeBaselineBuilder.quantile(xs, rangeHighQ)
            var basis = "history p01–p99 (\(xs.count) days)"
            if let fp = fullPoolFt, fp.isFinite, fp >= lo - margin(lo, hi), fp <= hi + margin(lo, hi) {
                lo = min(lo, fp); hi = max(hi, fp); basis += " + full pool"
            }
            return Reference(lo: lo, hi: hi, marginFt: margin(lo, hi), basis: basis)
        }
        if let fp = fullPoolFt, fp.isFinite { return Reference(lo: fp, hi: fp, marginFt: minMarginFt, basis: "full pool") }
        return nil
    }

    /// The reference this series is judged against: the lake's, if at least half of the series is inside it; otherwise the
    /// same width re-centred on the series' median (another datum). nil when the series cannot be judged.
    static func band(for values: [Double], reference: Reference?) -> Reference? {
        guard let med = median(values) else { return nil }
        if let r = reference {
            if values.filter(r.contains).count * 2 >= values.count { return r }
            let half = (r.hi - r.lo) / 2
            return Reference(lo: med - half, hi: med + half, marginFt: r.marginFt, basis: "series median (reference \(r.basis) is on another datum)")
        }
        guard values.count >= minSeriesForSelfBand else { return nil }
        return Reference(lo: med, hi: med, marginFt: minMarginFt, basis: "series median")
    }

    static func stepLimit(hours: Double) -> Double { stepToleranceFt + maxRateFtPerHour * abs(hours) }

    /// Splits one live series (oldest first) into accepted and rejected readings. `datumOffsetFt` puts a reading on the binding's
    /// datum, which is the datum of `reference`.
    public static func filter(_ readings: [LevelObservation], sourceId: String, datumOffsetFt: Double = 0,
                              reference: Reference?) -> (kept: [LevelObservation], rejected: [Rejection]) {
        guard !readings.isEmpty else { return ([], []) }
        let readings = readings.sorted { $0.at < $1.at }
        var rejected: [Rejection] = []
        func ft(_ o: LevelObservation) -> Double { o.ft + datumOffsetFt }
        func fmt(_ x: Double) -> String { String(format: "%.2f", x) }

        // 1. Level band.
        var inBand: [LevelObservation] = []
        let finite = readings.filter { physicallyPossible(ft($0)) }
        for o in readings where !physicallyPossible(ft(o)) {
            rejected.append(Rejection(sourceId: sourceId, at: o.at, rawFt: o.ft, reason: "not a lake level on any datum"))
        }
        if let b = band(for: finite.map(ft), reference: reference) {
            for o in finite {
                if b.contains(ft(o)) { inBand.append(o) } else {
                    rejected.append(Rejection(sourceId: sourceId, at: o.at, rawFt: o.ft,
                                              reason: "outside \(fmt(b.lowFt))–\(fmt(b.highFt)) ft (\(b.basis) ± \(fmt(b.marginFt)) ft)"))
                }
            }
        } else {
            inBand = finite
        }

        // 2. Step, walking out from the reading closest to the median.
        var kept = inBand
        if inBand.count >= 2, let med = median(inBand.map(ft)) {
            let seed = inBand.indices.min { abs(ft(inBand[$0]) - med) < abs(ft(inBand[$1]) - med) }!
            var ok = Array(repeating: false, count: inBand.count)
            ok[seed] = true
            for dir in [1, -1] {
                var last = seed, i = seed + dir
                while i >= 0, i < inBand.count {
                    let h = inBand[i].at.timeIntervalSince(inBand[last].at) / 3600
                    let d = ft(inBand[i]) - ft(inBand[last])
                    if abs(d) <= stepLimit(hours: h) { ok[i] = true; last = i } else {
                        rejected.append(Rejection(sourceId: sourceId, at: inBand[i].at, rawFt: inBand[i].ft,
                                                  reason: "step \(fmt(d)) ft in \(fmt(abs(h))) h from \(fmt(ft(inBand[last]))) ft (limit \(fmt(stepLimit(hours: h))) ft)"))
                    }
                    i += dir
                }
            }
            kept = inBand.indices.filter { ok[$0] }.map { inBand[$0] }
        }
        return (kept, rejected.sorted { $0.at < $1.at })
    }

    /// Daily history dates outside the history's own band (rule 1). History is already on the binding datum.
    public static func implausibleDays(_ daily: [DailyLevel], fullPoolFt: Double? = nil) -> Set<String> {
        let impossible = daily.filter { !physicallyPossible($0.ft) }.map(\.date)
        guard let r = reference(historyFt: daily.map(\.ft), fullPoolFt: fullPoolFt), daily.count >= minHistoryDays else { return Set(impossible) }
        return Set(daily.filter { !physicallyPossible($0.ft) || !r.contains($0.ft) }.map(\.date))
    }

    /// The quality flag for one rejection: `implausibleReading:<sourceId>@<iso>=<raw ft>`.
    public static func flag(_ r: Rejection) -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]       // == BrainPlatform.iso
        return "implausibleReading:\(r.sourceId)@\(f.string(from: r.at))=\(String(format: "%.2f", r.rawFt))"
    }

    /// Flags are capped so one broken series cannot flood a record; the rest are counted.
    public static let maxFlags = 5
}
