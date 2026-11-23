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
//  Per-lake rules, data-driven. A reading that fails one is REJECTED: it is never published, never used for a change window,
//  a trend or a baseline. The raw value is reported as a run warning (never in the published flag). The archive is never edited.
//
//  D. Decade slip, whatever the band says, and ONLY against a real lake reference (history range or directory full pool).
//     W = that range [lo, hi] (below) widened by 15 % of each end. A positive reading outside W whose ×10 or ÷10 lands inside
//     W is a misplaced decimal point (Tahoe 622.83 → 6,228.3; Okeechobee 1.5 → 15). This catches what the band cannot:
//     low-elevation lakes (< ~60 ft, where ÷10 moves a level by less than the 50 ft margin), single readings, and a series
//     whose MAJORITY is slipped. Only ×10 / ÷10 are tested (×100 and beyond is outside rule 0 at any real lake above 145 ft,
//     and 0.01 is a common stage/elevation ratio). Never against a series' own median (a river gauge can rise 10× in a
//     flood: 2 ft → 20 ft is water), so never on a nearby-gauge proxy (the classifier passes it no reference) or on a series
//     with no reference. A decade reading is REJECTED when a history range or an anchor (a decade of the anchor too) confirms
//     the slip; against a directory full pool alone it is only suspect: kept, and the source marked unverified (a gauge ~10×
//     off its full pool may be a datum, and rejecting would blank the lake).
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
//     The band must describe the series it judges, but a short or inconsistent series never moves it. It is re-centred (same
//     width, on the median of the readings outside it) only when ALL hold: the newest reading is outside it, at least 6
//     readings are outside it, they span ≥ 24 h, and they fit in one band width. That is a series on another datum (the
//     `historyLiveMismatch` lakes, a gauge re-datumed); one slip, or a day of them, never qualifies. A live series with no
//     reference is judged against its own median ± 50 ft, and only with ≥ 3 readings (rules 0 and 2 still apply).
//     Continuity: a reading outside the band is still ACCEPTED when it continues the accepted series smoothly (within
//     1 ft + the rule-2 allowance of its accepted neighbour, no 10 ft jump allowance). A real drawdown or flood that walks past the band edge is
//     water; a slip is a jump. (Owner rule: never an older or "unknown" value when a real newer one exists.)
//     Anchor: the lake's last published VERIFIED value (`anchor`; the runner refuses a published state whose CURRENT value was
//     flagged: levelUnverified / implausibleLatestRejected / allReadingsImplausible, so an unverified value never verifies itself and stays flagged
//     run after run until the band, history or a verified anchor confirms it), ≤ 7 days old, passing rules 0 and D, and
//     inside the band when the band comes from history. A reading outside the band within the STEP limit of the anchor over
//     the gap is accepted (Ross Lake after a 2-day outage, 70 ft below full pool).
//     Unverified, never blanked: (a) no in-band reading and no usable anchor: the series is accepted as far as it is
//     internally consistent (the step walk from its own median); (b) the anchor rejected every reading but ≥ 2 of them agree
//     within the step rule (a datum change or a new level after an outage); a lone reading stays rejected; (c) no lake
//     reference at all and < 3 readings; (d) a kept decade-suspect reading (full pool only); (e) a band re-centred on the
//     series (with or without history; with history the runner also flags historyLiveMismatch), UNLESS every accepted reading since a verified anchor follows
//     the previous one within the continuity rule: a consistent wrong-datum or wrong-unit feed (feet vs metres) re-centres
//     just as well as a real drawdown, but only the drawdown links back to a verified value without a jump. Verification
//     therefore carries forward by continuity; it never depends on the history source being available (TVA's operating
//     guide may be removed). In each case the source is
//     marked `unverified` (classifier flag `levelUnverified:<sourceId>`). Only when some readings ARE in the band are the
//     out-of-band ones that do not continue them rejected (one slip among good readings; or the first hours of a datum
//     change, which shows the last old-datum reading until the new series has 6 readings over 24 h).
//
//  2. Step. Between consecutive accepted readings of one series, a change of more than
//       min(stepToleranceFt + allowance(h), maxStepFt)        allowance(h) = 2 ft/h × min(h, 24) + 3 ft/day × max(h − 24, 0)
//     is impossible (continuity uses 1 ft instead of 10 ft, same allowance and ceiling). 2 ft/h (48 ft in a day) is eight
//     times the Brain's own FAST tier (1 ft in 6 h, LakeLevelValidity) and above any reservoir change in the committed
//     fixtures (max 1.0 ft/h). It is a burst rate: no reservoir sustains it, so past the first 24 h of a gap the allowance
//     grows by 3 ft/day, about 3× the steepest sustained change in the bound lakes' committed 30-day probes (27.3 ft in 30
//     days ≈ 0.9 ft/day). No single step, at any gap, may exceed 60 ft (the 24 h limit, 58 ft, rounded up): after a long
//     outage a wrong-unit or wrong-datum feed (a metres feed at ~91 ft against a 299 ft anchor after 108 h) is a jump, not
//     water. 10 ft is the baseline's existing spike tolerance (LakeLevelBaseline.spikeToleranceFt).
//     The walk starts from the in-band reading closest to the in-band median (the older on a tie), so one bad reading cannot make the
//     good ones look like steps.
//
//  Re-centring never verifies by itself, with or without history: a re-centred series (the history- or full-pool band no
//  longer describes it; with history that is also the runner's `historyLiveMismatch`) is verified only when it links back to
//  a verified anchor by continuity; otherwise it stays `levelUnverified` (a steady wrong-unit or wrong-datum feed).
//
//  Known limit (no rule): a digit transposition (6,226.05 ↔ 6,262.05) or a single wrong digit moves a reading by less than
//  the band margin and is not a decade, so it is caught only by the step rule (when it is a jump from its neighbours).
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
    /// Rule D: decade slips (×10, ÷10) against the recorded range widened by this fraction.
    public static let decadeFactors: [Double] = [10, 0.1]
    public static let decadeTolerance = 0.15
    /// Re-centring needs this many readings outside the reference, spanning at least this long, newest included.
    public static let minRecentreReadings = 6
    public static let minRecentreHours = 24.0
    /// Continuity rescue for a reading outside the band: no jump allowance, only sustained movement.
    public static let continuityToleranceFt = 1.0
    /// The last published accepted value counts as an anchor only this long after its observation.
    public static let maxAnchorAgeHours = 168.0
    /// Step rule: tolerance at any gap (== LakeLevelBaseline.spikeToleranceFt) plus a maximum sustained rate.
    public static let stepToleranceFt = LakeLevelBaseline.spikeToleranceFt
    public static let maxRateFtPerHour = 2.0
    /// The burst rate applies to the first `burstHours` of a gap; after that the allowance grows by `sustainedRateFtPerDay`.
    public static let burstHours = 24.0
    public static let sustainedRateFtPerDay = 3.0
    /// No single step, at any gap, may exceed this.
    public static let maxStepFt = 60.0

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

    /// Rule D: `ft` is outside the recorded range (±15 %) and its ×10 or ÷10 is inside it. Positive ranges only.
    static func isDecadeSlip(_ ft: Double, lo: Double, hi: Double) -> Bool {
        guard ft > 0, lo > 0, hi >= lo else { return false }
        let wLo = lo * (1 - decadeTolerance), wHi = hi * (1 + decadeTolerance)
        func inW(_ x: Double) -> Bool { x >= wLo && x <= wHi }
        return !inW(ft) && decadeFactors.contains { inW(ft * $0) }
    }

    /// The band a series (oldest first, binding datum) is judged against. The lake's reference unless the series is
    /// consistently elsewhere (see the header: newest outside, ≥ 6 readings outside spanning ≥ 24 h, within one band width);
    /// then the same width re-centred on those readings. No reference: the series' own median ± 50 ft with ≥ 3 readings.
    static func band(for series: [(at: Date, ft: Double)], reference: Reference?) -> Reference? {
        bandDecision(for: series, reference: reference).band
    }

    /// `band(for:)` and whether it was re-centred on the series (i.e. the series, not the lake's reference, set it).
    static func bandDecision(for series: [(at: Date, ft: Double)], reference: Reference?) -> (band: Reference?, recentred: Bool) {
        guard let newest = series.last else { return (nil, false) }
        if let r = reference {
            if r.contains(newest.ft) { return (r, false) }
            let outside = series.filter { !r.contains($0.ft) }
            let width = (r.hi - r.lo) + 2 * r.marginFt
            guard outside.count >= minRecentreReadings, let first = outside.first,
                  newest.at.timeIntervalSince(first.at) >= minRecentreHours * 3600,
                  let mx = outside.map(\.ft).max(), let mn = outside.map(\.ft).min(), mx - mn <= width,
                  let med = median(outside.map(\.ft)) else { return (r, false) }
            let half = (r.hi - r.lo) / 2
            return (Reference(lo: med - half, hi: med + half, marginFt: r.marginFt, basis: "series median (reference \(r.basis) is on another datum)"), true)
        }
        guard series.count >= minSeriesForSelfBand, let med = median(series.map(\.ft)) else { return (nil, false) }
        return (Reference(lo: med, hi: med, marginFt: minMarginFt, basis: "series median"), false)
    }

    /// Every accepted reading at or after the anchor follows the previous one (the anchor first) within `continuityLimit`.
    static func continuouslyLinked(_ kept: [(at: Date, ft: Double)], to anchor: LevelObservation?) -> Bool {
        guard let a = anchor else { return false }
        let after = kept.filter { $0.at >= a.at }.sorted { $0.at < $1.at }
        guard !after.isEmpty else { return false }
        var prev = (at: a.at, ft: a.ft)
        for o in after {
            if abs(o.ft - prev.ft) > continuityLimit(hours: o.at.timeIntervalSince(prev.at) / 3600) { return false }
            prev = o
        }
        return true
    }

    /// Movement a lake can make in `hours`: the burst rate for the first day of a gap, the sustained daily rate after it.
    static func allowance(hours: Double) -> Double {
        let h = abs(hours)
        return maxRateFtPerHour * min(h, burstHours) + sustainedRateFtPerDay / 24 * max(h - burstHours, 0)
    }
    static func stepLimit(hours: Double) -> Double { min(stepToleranceFt + allowance(hours: hours), maxStepFt) }
    static func continuityLimit(hours: Double) -> Double { min(continuityToleranceFt + allowance(hours: hours), maxStepFt) }

    /// Splits one live series into accepted and rejected readings. `datumOffsetFt` puts a reading on the binding's datum,
    /// which is the datum of `reference` and `anchor`. `reference` nil = no lake reference (a proxy, or a lake with neither
    /// history nor full pool): rule D is then not applied. `unverified`: nothing in the series was in the band or tied to the
    /// anchor, so what was kept is only internally consistent (see the header).
    public static func filter(_ readings: [LevelObservation], sourceId: String, datumOffsetFt: Double = 0,
                              reference: Reference?, anchor: LevelObservation? = nil)
        -> (kept: [LevelObservation], rejected: [Rejection], unverified: Bool) {
        guard !readings.isEmpty else { return ([], [], false) }
        let readings = readings.sorted { $0.at < $1.at }
        var rejected: [Rejection] = []
        func ft(_ o: LevelObservation) -> Double { o.ft + datumOffsetFt }
        func fmt(_ x: Double) -> String { String(format: "%.2f", x) }

        // 0. Absolute.
        let possible = readings.filter { physicallyPossible(ft($0)) }
        for o in readings where !physicallyPossible(ft(o)) {
            rejected.append(Rejection(sourceId: sourceId, at: o.at, rawFt: o.ft, reason: "not a lake level on any datum"))
        }
        let historyBand = reference.map { $0.hi > $0.lo } ?? false
        // The anchor (binding datum already; the runner passes only a VERIFIED published value): usable when recent, possible,
        // not a decade slip of the reference and, against a history band, inside it (checked once the band is known).
        let anchorCandidate: LevelObservation? = anchor.flatMap { a in
            guard let newest = possible.last, physicallyPossible(a.ft), a.at <= newest.at,
                  newest.at.timeIntervalSince(a.at) <= maxAnchorAgeHours * 3600 else { return nil }
            if let r = reference, isDecadeSlip(a.ft, lo: r.lo, hi: r.hi) { return nil }
            return a
        }

        // D. Decade slips, against a real lake reference only. Rejected when the history range, or an anchor, confirms the slip;
        //    against a full pool alone (no history, no anchor confirming it) a decade reading is only SUSPECT: kept, and the
        //    source marked unverified (a gauge ~10× off its full pool is a datum question, not proof of a slip).
        var candidates: [LevelObservation] = []
        var suspect: Set<Date> = []
        for o in possible {
            guard let r = reference, isDecadeSlip(ft(o), lo: r.lo, hi: r.hi) else { candidates.append(o); continue }
            let confirmed = historyBand || anchorCandidate.map { isDecadeSlip(ft(o), lo: $0.ft, hi: $0.ft) } == true
            if confirmed {
                rejected.append(Rejection(sourceId: sourceId, at: o.at, rawFt: o.ft, reason: "decade slip (×10 or ÷10 of \(fmt(r.lo))–\(fmt(r.hi)) ft)"))
            } else { candidates.append(o); suspect.insert(o.at) }
        }
        guard !candidates.isEmpty else { return ([], rejected.sorted { $0.at < $1.at }, false) }

        // 1. Band (nil: the series cannot be judged by level, every candidate counts as inside).
        let (b, recentred) = bandDecision(for: candidates.map { (at: $0.at, ft: ft($0)) }, reference: reference)
        var inside = candidates.map { b?.contains(ft($0)) ?? true }
        let usableAnchor: LevelObservation? = anchorCandidate.flatMap { a in (historyBand && !(b?.contains(a.ft) ?? true)) ? nil : a }

        // Unverified: no lake reference and too few readings for a self band; or no in-band reading and no anchor. The lake is
        // never blanked for it: the series is judged by its own consistency and published with `levelUnverified`.
        var unverified = reference == nil && b == nil
        if !inside.contains(true), usableAnchor == nil {
            unverified = true
            inside = Array(repeating: true, count: candidates.count)
        }

        // 2. Step walk. Nodes are the candidates plus the anchor (never output). Seed: the in-band candidate closest to the
        //    in-band median; else the anchor. An out-of-band candidate is accepted as a smooth continuation of its accepted
        //    neighbour (continuityLimit), or within the step limit when that neighbour is the anchor.
        struct Node { var at: Date; var ft: Double; var inside: Bool; var candidate: Int? }
        var nodes = candidates.enumerated().map { Node(at: $0.element.at, ft: ft($0.element), inside: inside[$0.offset], candidate: $0.offset) }
        if let a = usableAnchor {
            nodes.append(Node(at: a.at, ft: a.ft, inside: true, candidate: nil))
            nodes.sort { $0.at < $1.at || ($0.at == $1.at && $0.candidate == nil) }
        }
        var ok = Array(repeating: false, count: nodes.count)
        let inBand = nodes.indices.filter { nodes[$0].inside && nodes[$0].candidate != nil }
        let seed: Int?
        if let med = median(inBand.map { nodes[$0].ft }) {
            seed = inBand.min { abs(nodes[$0].ft - med) < abs(nodes[$1].ft - med) }
        } else {
            seed = nodes.firstIndex { $0.candidate == nil }
        }
        if let seed {
            ok[seed] = true
            for dir in [1, -1] {
                var last = seed, i = seed + dir
                while i >= 0, i < nodes.count {
                    let h = nodes[i].at.timeIntervalSince(nodes[last].at) / 3600
                    let d = abs(nodes[i].ft - nodes[last].ft)
                    let limit = nodes[i].inside || nodes[last].candidate == nil ? stepLimit(hours: h) : continuityLimit(hours: h)
                    if d <= limit { ok[i] = true; last = i }
                    i += dir
                }
            }
        }
        var accepted = Array(repeating: false, count: candidates.count)
        for (i, n) in nodes.enumerated() { if let c = n.candidate, ok[i] { accepted[c] = true } }
        // The anchor (or band) rejected every reading, but ≥ 2 of them agree with each other within the step rule: the series
        // moved (a datum change, a new level after an outage). Publish it unverified rather than leave the lake UNAVAILABLE.
        // A lone reading cannot show that and stays rejected.
        if !accepted.contains(true), candidates.count >= 2 {
            let all = candidates.map(ft)
            if let med = median(all), let seed = all.indices.min(by: { abs(all[$0] - med) < abs(all[$1] - med) }) {
                var self_ = Array(repeating: false, count: all.count)
                self_[seed] = true
                for dir in [1, -1] {
                    var last = seed, i = seed + dir
                    while i >= 0, i < all.count {
                        let h = candidates[i].at.timeIntervalSince(candidates[last].at) / 3600
                        if abs(all[i] - all[last]) <= stepLimit(hours: h) { self_[i] = true; last = i }
                        i += dir
                    }
                }
                if self_.filter({ $0 }).count >= 2 { accepted = self_; unverified = true; inside = Array(repeating: true, count: candidates.count) }
            }
        }
        var kept: [LevelObservation] = []
        for (i, o) in candidates.enumerated() {
            if accepted[i] { kept.append(o); continue }
            let why: String
            if !inside[i], let b {
                why = "outside \(fmt(b.lowFt))–\(fmt(b.highFt)) ft (\(b.basis) ± \(fmt(b.marginFt)) ft) and not a smooth continuation"
            } else {
                why = "impossible step from the accepted series (limit \(fmt(stepToleranceFt)) ft + \(fmt(maxRateFtPerHour)) ft/h for a day, then \(fmt(sustainedRateFtPerDay)) ft/day, at most \(fmt(maxStepFt)) ft)"
            }
            rejected.append(Rejection(sourceId: sourceId, at: o.at, rawFt: o.ft, reason: why))
        }
        if kept.contains(where: { suspect.contains($0.at) }) { unverified = true }
        // A band re-centred on the series is only as good as the series: a consistent wrong-datum or wrong-unit feed re-centres
        // as well as a real drawdown, with or without history (with history it is also the runner's historyLiveMismatch).
        // Verification then carries forward by continuity alone: the source is verified only when every accepted reading since
        // a VERIFIED anchor follows the one before it within the continuity rule. A real drawdown walked out of the band from a
        // verified value stays verified run after run (Ross Lake in winter); a jump (wrong datum, metres) or no anchor leaves it
        // unverified.
        if recentred, !continuouslyLinked(kept.map { (at: $0.at, ft: ft($0)) }, to: usableAnchor) { unverified = true }
        return (kept, rejected.sorted { $0.at < $1.at }, unverified && !kept.isEmpty)
    }

    /// Daily history dates outside the history's own band (rule 1) or decade slips of it (rule D). History is already on the
    /// binding datum. `fullPoolFt` widens the band only where it agrees with the history (as on the live path).
    public static func implausibleDays(_ daily: [DailyLevel], fullPoolFt: Double? = nil) -> Set<String> {
        let impossible = daily.filter { !physicallyPossible($0.ft) }.map(\.date)
        guard let r = reference(historyFt: daily.map(\.ft), fullPoolFt: fullPoolFt), daily.count >= minHistoryDays else { return Set(impossible) }
        return Set(daily.filter { !physicallyPossible($0.ft) || !r.contains($0.ft) || isDecadeSlip($0.ft, lo: r.lo, hi: r.hi) }.map(\.date))
    }

    static func iso(_ d: Date) -> String {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime]       // == BrainPlatform.iso
        return f.string(from: d)
    }

    /// The published quality flag for one rejection: `implausibleReading:<sourceId>@<iso>`. No raw value (a slip is not a fact
    /// about the lake); the raw value is in the run warning (`warning`).
    public static func flag(_ r: Rejection) -> String { "implausibleReading:\(r.sourceId)@\(iso(r.at))" }

    /// The run warning for one rejection, with the raw value and the reason.
    public static func warning(_ r: Rejection) -> String {
        "implausible level reading rejected: \(r.sourceId) @ \(iso(r.at)) raw \(String(format: "%.2f", r.rawFt)) ft (\(r.reason))"
    }

    /// Flags are capped so one broken series cannot flood a record; the rest are counted.
    public static let maxFlags = 5
}
