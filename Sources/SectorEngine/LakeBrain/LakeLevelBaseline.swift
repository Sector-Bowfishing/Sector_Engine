//
//  LakeLevelBaseline.swift
//  Sector — Lake Brain: explainable day-of-year baselines (no ML)
//
//  From a lake's daily history (`doy15-percentile-v2`):
//    • level climatology — for each day of year, the levels on that day ± 7 days
//      in the basis years (the most recent 30 complete years for regulated
//      `fullPool` lakes; all complete years, capped at 60, for `naturalSurface` lakes);
//    • rate climatology  — the same window over |Δ24h| between consecutive days,
//      from every year in the last 30 (partial years included).
//  Stored as a quantile grid so a value's percentile can be read back without
//  the raw samples. Cut points and rules are explicit and versioned
//  (LakeBrainSpec.baselineMethod); see the spec §6.
//

import Foundation

public struct LakeBaselineDay: Codable, Equatable, Sendable {
    public var doy: Int
    /// Level samples in the window; 0 when the lake has < 2 basis years.
    public var n: Int
    /// Quantiles at `LakeLevelBaseline.grid`.
    public var levelQ: [Double]?
    public var rateN: Int
    public var rateQ: [Double]?
}

public struct LakeLevelBaseline: Codable, Equatable, Sendable {
    public static let windowDays = 7
    /// Regulated (`poolBasis == fullPool`) lakes: the most recent 30 complete years.
    public static let maxBasisYears = 30
    /// `naturalSurface` lakes: every complete year, capped here (rules v2 R1).
    public static let maxBasisYearsNatural = 60
    /// A calendar year counts as complete with ≥ 90 % of its days (329).
    public static let completeYearDays = 329
    public static let sufficientYears = 5
    public static let limitedYears = 2
    /// Rules v2 R1 history tiers, by complete basis years (`baselineStatus` keeps its v1 meaning).
    public static let provisionalYears = 5
    public static let standardYears = 10
    public static let fullYears = 15
    /// A rate threshold needs at least this many |Δ24h| samples in the window.
    public static let minRateSamples = 20
    /// History rows whose `sourceId` starts with this are low-resolution (0.1 ft, non-midnight) archive values: used for the level
    /// climatology, never for the |Δ24h| rate climatology.
    public static let lowResolutionSourcePrefix = "nws:rvd"
    public static let grid: [Double] = [0, 2, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 98, 100]

    public var lakeId: String
    public var method: String
    public var baselineVersion: String
    public var historyStart: String?
    public var historyEnd: String?
    public var observationCount: Int
    public var coveragePct: Double?
    public var completeYears: [Int]
    public var basisYears: [Int]
    public var status: LakeBaselineStatus
    /// What the history may be used for (rules v2 R1). Separate from `status`.
    public var historicalTier: LakeHistoricalTier
    public var windowDays: Int
    public var days: [LakeBaselineDay]

    public func day(_ doy: Int) -> LakeBaselineDay? { days.first { $0.doy == doy } }

    /// R1: NONE < 5, PROVISIONAL 5–9, STANDARD 10–14, FULL ≥ 15 complete basis years.
    public static func tier(basisYears n: Int) -> LakeHistoricalTier {
        n >= fullYears ? .full : n >= standardYears ? .standard : n >= provisionalYears ? .provisional : .none
    }
}

public enum LakeBaselineBuilder {

    /// Type-7 (linear) quantile of sorted `xs` at percentile `p` (0–100).
    static func quantile(_ xs: [Double], _ p: Double) -> Double {
        guard !xs.isEmpty else { return .nan }
        if xs.count == 1 { return xs[0] }
        let h = (Double(xs.count) - 1) * p / 100
        let lo = Int(h.rounded(.down)), hi = min(lo + 1, xs.count - 1)
        return xs[lo] + (h - Double(lo)) * (xs[hi] - xs[lo])
    }

    static func grid(_ samples: [Double]) -> [Double] {
        let s = samples.sorted()
        return LakeLevelBaseline.grid.map { (quantile(s, $0) * 1000).rounded() / 1000 }
    }

    /// Percentile (0–100) of `x` against a quantile grid, by linear interpolation between grid points.
    public static func percentile(of x: Double, grid q: [Double]) -> Double {
        let g = LakeLevelBaseline.grid
        guard q.count == g.count else { return .nan }
        if x <= q[0] { return 0 }
        if x >= q[q.count - 1] { return 100 }
        for i in 1..<q.count where x <= q[i] {
            let span = q[i] - q[i - 1]
            let f = span > 0 ? (x - q[i - 1]) / span : 0.5
            return g[i - 1] + f * (g[i] - g[i - 1])
        }
        return 100
    }

    /// Value of a grid at a grid percentile (must be one of `LakeLevelBaseline.grid`).
    public static func at(_ p: Double, _ q: [Double]) -> Double? {
        guard let i = LakeLevelBaseline.grid.firstIndex(of: p), i < q.count else { return nil }
        return q[i]
    }

    static func circularDistance(_ a: Int, _ b: Int) -> Int {
        let d = abs(a - b) % 365
        return min(d, 365 - d)
    }

    /// FNV-1a 64 — a content fingerprint for versioning, not security.
    static func fingerprint(_ s: String) -> String {
        var h: UInt64 = 0xcbf2_9ce4_8422_2325
        for b in s.utf8 { h ^= UInt64(b); h = h &* 0x100_0000_01b3 }
        return String(format: "%016llx", h)
    }

    /// `poolBasisIsFullPool`: regulated lakes use the 30 most recent complete years; anything else
    /// (`naturalSurface`) uses all complete years up to 60. The rate climatology keeps the last-30-years rule.
    public static func build(lakeId: String, daily raw: [DailyLevel], today: String,
                             poolBasisIsFullPool: Bool = true) -> LakeLevelBaseline {
        let daily = LakeDailyHistory.dedupe(raw).filter { $0.date <= today }
        let currentYear = Int(today.prefix(4)) ?? 0
        var perYear: [Int: Int] = [:]
        for d in daily { if let y = Int(d.date.prefix(4)) { perYear[y, default: 0] += 1 } }
        let complete = perYear.filter { $0.key < currentYear && $0.value >= LakeLevelBaseline.completeYearDays }.keys.sorted()
        let cap = poolBasisIsFullPool ? LakeLevelBaseline.maxBasisYears : LakeLevelBaseline.maxBasisYearsNatural
        let basis = Array(complete.suffix(cap))
        let status: LakeBaselineStatus = basis.count >= LakeLevelBaseline.sufficientYears ? .sufficient
            : basis.count >= LakeLevelBaseline.limitedYears ? .limited : (daily.isEmpty ? .none : .insufficient)

        // Level samples by doy, basis years only (needs ≥ 2 years to say anything).
        let basisSet = Set(basis)
        var levelByDoy: [Int: [Double]] = [:]
        if basis.count >= LakeLevelBaseline.limitedYears {
            for d in daily {
                guard let y = Int(d.date.prefix(4)), basisSet.contains(y), let doy = LakeLevelCalendar.doy365(d.date) else { continue }
                levelByDoy[doy, default: []].append(d.ft)
            }
        }
        // |Δ24h| samples by doy, every year in the last 30.
        // Day pairs where either day came from a low-resolution archive (`LakeLevelBaseline.lowResolutionSourcePrefix`: NWS RVD text
        // products, 0.1 ft and a 06-07 h stamp rather than midnight) are skipped: their quantisation inflates the p50/p95 of |Δ24h|
        // (Wilson, Jun 15: p95 0.64 ft with them, 0.48 ft without). The LEVEL climatology keeps those days (the shift is 0.03-0.10 ft).
        let byDate = Dictionary(daily.map { ($0.date, $0) }, uniquingKeysWith: { _, b in b })
        var rateByDoy: [Int: [Double]] = [:]
        for d in daily {
            guard let y = Int(d.date.prefix(4)), y > currentYear - LakeLevelBaseline.maxBasisYears,
                  let prev = LakeLevelCalendar.previousDay(d.date), let pv = byDate[prev],
                  !d.sourceId.hasPrefix(LakeLevelBaseline.lowResolutionSourcePrefix),
                  !pv.sourceId.hasPrefix(LakeLevelBaseline.lowResolutionSourcePrefix),
                  let doy = LakeLevelCalendar.doy365(d.date) else { continue }
            rateByDoy[doy, default: []].append(abs(d.ft - pv.ft))
        }

        var days: [LakeBaselineDay] = []
        let w = LakeLevelBaseline.windowDays
        for doy in 1...365 {
            var lv: [Double] = [], rv: [Double] = []
            for off in -w...w {
                let k = ((doy - 1 + off) % 365 + 365) % 365 + 1
                lv += levelByDoy[k] ?? []
                rv += rateByDoy[k] ?? []
            }
            days.append(LakeBaselineDay(doy: doy, n: lv.count, levelQ: lv.isEmpty ? nil : grid(lv),
                                        rateN: rv.count, rateQ: rv.count >= LakeLevelBaseline.minRateSamples ? grid(rv) : nil))
        }

        var coverage: Double?
        if let s = daily.first?.date, let e = daily.last?.date,
           let sd = LakeLevelCalendar.utcBounds(day: s, timeZone: TimeZone(identifier: "UTC")!)?.0,
           let ed = LakeLevelCalendar.utcBounds(day: e, timeZone: TimeZone(identifier: "UTC")!)?.0 {
            let span = ed.timeIntervalSince(sd) / 86_400 + 1
            coverage = (Double(daily.count) / span * 1000).rounded() / 10
        }
        let csv = String(decoding: LakeDailyHistory.encode(daily), as: UTF8.self)
        let version = "\(LakeBrainSpec.baselineMethod)@\(daily.last?.date ?? "none")#\(fingerprint(csv).prefix(8))"
        return LakeLevelBaseline(lakeId: lakeId, method: LakeBrainSpec.baselineMethod, baselineVersion: version,
                                 historyStart: daily.first?.date, historyEnd: daily.last?.date, observationCount: daily.count,
                                 coveragePct: coverage, completeYears: complete, basisYears: basis, status: status,
                                 historicalTier: LakeLevelBaseline.tier(basisYears: basis.count), windowDays: w, days: days)
    }

    public static func path(_ b: LakeLevelBaseline) -> String {
        "baselines/\(BrainPlatform.lakeKey(b.lakeId))/\(BrainPlatform.lakeKey(b.baselineVersion)).json"
    }
}
