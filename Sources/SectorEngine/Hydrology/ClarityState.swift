//
//  ClarityState.swift
//  Sector — what Sector believes each arm's water clarity is now, and why
//  (Clarity Fusion Stage 2)
//
//  ONE STATE PER HYDROLOGIC ARM, AND ONE FOR THE MAIN STEM. Each fuses the
//  latest satellite scene of that arm's own water with what has happened to
//  that arm's own drainage since the scene: rain over its catchment (MRMS),
//  its own creek's flow (measured, modeled, or neither — never merged), and
//  how wet the ground was when the scene was taken. Nothing crosses from one
//  arm to another: Town Creek's storm is Town Creek's.
//
//  AUTHORITY IS LOST TO EVIDENCE, NOT TO AGE. A scene keeps its authority for
//  as long as the drainage stays as it was when the scene was taken. It loses
//  it when rain falls on the catchment or the creek rises — by how much, not
//  by how many days. An old scene of a dry week outranks a new one taken
//  before a storm.
//
//  DIRECTION IS NOT MAGNITUDE. The runoff state says which way the water has
//  most likely moved since the scene. It never moves the visibility feet:
//  Stage 2 has no calibrated size for a storm's effect (see the Stage 2
//  hand-off, pass-pair analysis), so where the scene no longer holds, the
//  magnitude is the baseline, labelled, with the direction as a warning.
//
//  NOT SCORED. /conditions and every Fish Intelligence output are unchanged;
//  this is read-only until it is reviewed and adopted.
//

import Foundation

// MARK: - Inputs

public enum CatchmentCompleteness: String, Codable, Equatable {
    /// The NHDPlus basin at the arm's mouth: all the land that drains to it.
    case complete
    /// Only the basin above the embayment's head; the land around the
    /// embayment itself is missing.
    case partial
    /// No drainage area could be resolved.
    case unavailable

    public init(basis: String?) {
        switch basis {
        case "nhdplusBasinAtMouth", "lakeSurface": self = .complete
        case "nhdplusBasinAboveHead": self = .partial
        default: self = .unavailable
        }
    }
}

/// Rain over one catchment in one interval (hourly from the hydrology job,
/// daily in the historical replay). nil inches = the interval was not read.
public struct RainStep: Codable, Equatable {
    public let start: Date
    public let end: Date
    public let inches: Double?
    public init(start: Date, end: Date, inches: Double?) {
        self.start = start; self.end = end; self.inches = inches
    }
}

public struct RainRecord: Codable, Equatable {
    /// nhdplusBasinAtMouth | nhdplusBasinAboveHead | lakeSurface | unavailable
    public let basis: String
    public let drainageKm2: Double?
    public let source: String
    /// Sorted by start; gaps allowed (they reduce coverage, never read as dry).
    public let steps: [RainStep]
    public init(basis: String, drainageKm2: Double?, source: String, steps: [RainStep]) {
        self.basis = basis; self.drainageKm2 = drainageKm2; self.source = source
        self.steps = steps.sorted { $0.start < $1.start }
    }
    public var completeness: CatchmentCompleteness { CatchmentCompleteness(basis: basis) }

    public struct Total: Equatable {
        public let inches: Double
        /// Share of the interval covered by read steps.
        public let coverage: Double
    }

    /// Rain in (from, to]. nil when less than 90% of the interval was read:
    /// an unread hour is unknown, not dry.
    public func total(from: Date, to: Date) -> Total? {
        guard to > from, completeness != .unavailable else { return nil }
        var inches = 0.0, covered = 0.0
        for s in steps where s.end > from && s.start < to {
            guard let v = s.inches else { continue }
            let span = s.end.timeIntervalSince(s.start)
            guard span > 0 else { continue }
            let lo = max(s.start, from), hi = min(s.end, to)
            let part = hi.timeIntervalSince(lo) / span
            inches += v * part
            covered += hi.timeIntervalSince(lo)
        }
        let coverage = covered / to.timeIntervalSince(from)
        return coverage >= 0.9 ? Total(inches: inches, coverage: min(1, coverage)) : nil
    }

    /// The end of the newest read step at or before `now`, if the record
    /// reaches within `maxLagHours` of now (the hourly job runs at T−2 h).
    public func validThrough(_ now: Date, maxLagHours: Double = 30) -> Date? {
        guard let last = steps.last(where: { $0.end <= now && $0.inches != nil }),
              now.timeIntervalSince(last.end) <= maxLagHours * 3600 else { return nil }
        return last.end
    }

    /// Rain in the `hours` ending where the record ends.
    public func window(hours: Double, now: Date) -> Double? {
        guard let t = validThrough(now) else { return nil }
        return total(from: t.addingTimeInterval(-hours * 3600), to: t)?.inches
    }

    /// The storm under way: back from the record's end until `dryHours` in a
    /// row with under 0.01 in/h. nil when the record runs out first.
    public func currentStorm(at now: Date, dryHours: Double = 6) -> (start: Date?, inches: Double)? {
        guard let end = validThrough(now) else { return nil }
        let past = steps.filter { $0.end <= end }.reversed()
        var total = 0.0, dry = 0.0, start: Date?
        var t = end
        for s in past {
            guard abs(s.end.timeIntervalSince(t)) < 1, let v = s.inches else { return nil }   // a gap: unknown
            let hours = s.end.timeIntervalSince(s.start) / 3600
            if v < 0.01 * hours {
                dry += hours
                if dry >= dryHours { return (start, total) }
            } else {
                dry = 0; total += v; start = s.start
            }
            t = s.start
        }
        return nil
    }
}

public struct FlowSeries: Codable, Equatable {
    public let provenance: FlowProvenance
    /// "USGS 03572900" | "NWM reach 19649040"
    public let source: String
    public let points: [FlowPoint]
    public init(provenance: FlowProvenance, source: String, points: [FlowPoint]) {
        self.provenance = provenance; self.source = source
        self.points = points.sorted { $0.validTime < $1.validTime }
    }

    /// The point nearest `t` within `toleranceHours`.
    public func value(at t: Date, toleranceHours: Double) -> FlowPoint? {
        points.min { abs($0.validTime.timeIntervalSince(t)) < abs($1.validTime.timeIntervalSince(t)) }
            .flatMap { abs($0.validTime.timeIntervalSince(t)) <= toleranceHours * 3600 ? $0 : nil }
    }

    public func latest(atOrBefore t: Date) -> FlowPoint? { points.last { $0.validTime <= t } }

    public func peak(from: Date, to: Date) -> FlowPoint? {
        points.filter { $0.validTime >= from && $0.validTime <= to }.max { $0.cfs < $1.cfs }
    }
}

/// An arm's flow: its own gauge and its own reach, kept apart.
public struct FlowRecord: Codable, Equatable {
    public let measured: FlowSeries?
    public let modeled: FlowSeries?
    public init(measured: FlowSeries?, modeled: FlowSeries?) {
        self.measured = measured; self.modeled = modeled
    }
    public static let none = FlowRecord(measured: nil, modeled: nil)
}

/// TVA's hourly release at a dam.
public struct ReleaseSeries: Codable, Equatable {
    public let dam: String
    public let tva: String
    public let points: [FlowPoint]
    public init(dam: String, tva: String, points: [FlowPoint]) {
        self.dam = dam; self.tva = tva; self.points = points.sorted { $0.validTime < $1.validTime }
    }
    /// Mean release over the 24 h ending at `t` (dams peak within a day, so
    /// a single hour says little). nil when fewer than 12 hours are recorded.
    public func mean24h(endingAt t: Date) -> Double? {
        let xs = points.filter { $0.validTime > t.addingTimeInterval(-86_400) && $0.validTime <= t }.map(\.cfs)
        return xs.count >= 12 ? xs.reduce(0, +) / Double(xs.count) : nil
    }
}

/// What Sector says about the water without the fusion: the engine's own
/// clarity estimate (ConditionsResponse.clarityVisibility). No range where
/// that estimate has none.
public struct BaselineVisibility: Codable, Equatable {
    public let centralFt: Double
    public let lowFt: Double?
    public let highFt: Double?
    public let model: String
    public let source: String
    public init(centralFt: Double, lowFt: Double?, highFt: Double?, model: String, source: String) {
        self.centralFt = centralFt; self.lowFt = lowFt; self.highFt = highFt; self.model = model; self.source = source
    }
}

// MARK: - The satellite anchor

public struct Distribution: Codable, Equatable {
    public let n: Int
    public let p25: Double
    public let p50: Double
    public let p75: Double
    public init(n: Int, p25: Double, p50: Double, p75: Double) {
        self.n = n; self.p25 = p25; self.p50 = p50; self.p75 = p75
    }
}

public enum AnchorStrength: String, Codable, Equatable, Comparable {
    case none, weak, moderate, strong
    var rank: Int { ["none": 0, "weak": 1, "moderate": 2, "strong": 3][rawValue]! }
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }
}

/// One scene's evidence for one arm (scripts/hydrology/arm_anchor.py from the
/// published Water Clarity product, or pass_history.py in the replay).
public struct SatelliteAnchor: Codable, Equatable {
    public let sceneDate: String
    public let sceneTime: Date
    public let platform: String?
    /// The arm's lake cells the clarity layer can colour (grass excluded).
    public let waterCells: Int
    public let observedCells: Int
    /// Estimated from readings elsewhere (cloud hid it, or the satellite cannot read there).
    public let filledCells: Int
    public let filledWithin500mCells: Int?
    public let medianFillDistanceM: Double?
    public let observedFNU: Distribution?
    /// Observed and filled together.
    public let allFNU: Distribution?
    /// Where the anchor came from.
    public let source: String

    public init(sceneDate: String, sceneTime: Date, platform: String?, waterCells: Int, observedCells: Int,
                filledCells: Int, filledWithin500mCells: Int?, medianFillDistanceM: Double?,
                observedFNU: Distribution?, allFNU: Distribution?, source: String) {
        self.sceneDate = sceneDate; self.sceneTime = sceneTime; self.platform = platform
        self.waterCells = waterCells; self.observedCells = observedCells; self.filledCells = filledCells
        self.filledWithin500mCells = filledWithin500mCells; self.medianFillDistanceM = medianFillDistanceM
        self.observedFNU = observedFNU; self.allFNU = allFNU; self.source = source
    }

    public var observedPct: Double { waterCells > 0 ? 100 * Double(observedCells) / Double(waterCells) : 0 }
    public var filledPct: Double { waterCells > 0 ? 100 * Double(filledCells) / Double(waterCells) : 0 }

    /// How far the scene can speak for this arm.
    ///   strong    the satellite read at least half the arm (and 25+ cells)
    ///   moderate  read or filled from within 500 m over at least half (10+ read)
    ///   weak      something read, but most of the arm is distant fill
    ///   none      nothing of this arm was read
    /// Thresholds are rules, not fits: the fill's own held-out error is
    /// already ±0.45 ft at 500 m (fill_lake.CLARITY_ERROR_BY_DISTANCE_FT).
    public var strength: (AnchorStrength, String) {
        guard waterCells > 0, observedCells > 0 else { return (.none, "nothing of this arm was read") }
        let obs = Double(observedCells) / Double(waterCells)
        if obs >= 0.5 && observedCells >= 25 {
            return (.strong, String(format: "%.0f%% of the arm read directly", 100 * obs))
        }
        let near = Double(observedCells + (filledWithin500mCells ?? 0)) / Double(waterCells)
        if near >= 0.5 && observedCells >= 10 {
            return (.moderate, String(format: "%.0f%% read, %.0f%% read or within 500 m of a reading", 100 * obs, 100 * near))
        }
        return (.weak, String(format: "only %.0f%% read; most of the arm is filled from readings further away", 100 * obs))
    }

    /// The scene's visibility for the arm, at the pass: the median observed
    /// cell when 10+ were read, else the median of everything, as an estimate.
    public func visibility(config: ConditionsConfig = .default) -> VisibilityEstimate? {
        if let o = observedFNU, observedCells >= 10 {
            return VisibilityModel.estimate(fnu: o.p50, source: .satelliteObserved, config: config)
        }
        if let a = allFNU {
            return VisibilityModel.estimate(fnu: a.p50, source: .satelliteEstimated,
                                            distanceToObservedM: medianFillDistanceM, config: config)
        }
        return nil
    }
}

// MARK: - The state

public struct Divergence: Codable, Equatable {
    public let passTime: Date?
    public let hoursSincePass: Double?
    /// Where the rain record ends (the hourly job lags ~2 h; the replay is daily).
    public let rainValidThrough: Date?
    /// Basin-mean rain over the arm's drainage since the pass. nil = unknown (never zero).
    public let rainSincePassIn: Double?
    public let rainSincePassCoverage: Double?
    public let currentStormIn: Double?
    /// The part of the storm under way that fell after the pass.
    public let currentStormSincePassIn: Double?
    public let rainLast24hIn: Double?
    public let rainLast72hIn: Double?
    /// Wetness when the scene was taken: the 7 days, and the 3 days, before it.
    public let antecedent7dBeforePassIn: Double?
    public let rain72hBeforePassIn: Double?
    public let dischargeProvenance: FlowProvenance
    public let dischargeSource: String?
    public let dischargeNowCfs: Double?
    public let dischargeNowAt: Date?
    /// Same provenance as now, or nil: a measured value is never compared with a modeled one.
    public let dischargeAtPassCfs: Double?
    public let dischargePeakSincePassCfs: Double?
    public let dischargeRatioToPass: Double?
    public let dischargePeakRatioToPass: Double?
    /// rising | falling | steady | unknown (12 h change, ±10%).
    public let dischargeTrend: String
    public let dischargeNote: String?
}

public enum RunoffClass: String, Codable, Equatable, Comparable {
    case stable, minorChange, moderateRunoff, majorRunoff, recovering, unknown
    var rank: Int {
        ["stable": 0, "minorChange": 1, "moderateRunoff": 2, "majorRunoff": 3, "recovering": 2, "unknown": -1][rawValue]!
    }
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }
}

/// The arm's water relative to the scene. Direction and magnitude apart.
public struct RunoffState: Codable, Equatable {
    public let state: RunoffClass
    /// murkierThanPass | sameAsPass | clearerThanPass | unknown — what the
    /// hydrology implies, NOT a validated clarity claim: in the 2025–26 replay
    /// "murkier" held at the next clear pass 15% of the time against an 11%
    /// base rate (hand-off §12).
    public let expectedDirection: String
    /// Always "uncalibrated" in Stage 2: no size is attached to the direction.
    public let magnitude: String
    /// Each piece of evidence and the level it indicates.
    public let evidence: [String]
}

public struct RunoffAnomaly: Codable, Equatable {
    public let rainSincePassIn: Double?
    public let dischargeRatioToPass: Double?
    public let dischargePeakRatioToPass: Double?
    public let provenance: FlowProvenance
}

public enum AuthorityLevel: String, Codable, Equatable, Comparable {
    case none, low, moderate, high
    var rank: Int { ["none": 0, "low": 1, "moderate": 2, "high": 3][rawValue]! }
    public static func < (a: Self, b: Self) -> Bool { a.rank < b.rank }
}

public struct SatelliteAuthority: Codable, Equatable {
    public let level: AuthorityLevel
    /// What held it at this level. Never the scene's age.
    public let reason: String
}

public struct CurrentVisibility: Codable, Equatable {
    /// satelliteAnchor — the scene still holds; its numbers are the answer.
    /// baseline — the scene no longer holds (or there is none); the numbers
    ///            are the baseline's, unadjusted, with `warning`.
    /// none — neither exists.
    public let basis: String
    public let centralFt: Double?
    public let lowFt: Double?
    public let highFt: Double?
    public let magnitudeSupported: Bool
    public let warning: String?
    /// What the baseline is when basis == baseline.
    public let baselineSource: String?
    /// The scene's own numbers, for reference, whenever there is a scene.
    public let atPass: VisibilityEstimate?
    public let model: String
}

public struct StateConfidence: Codable, Equatable {
    /// medium | low | veryLow — ordinal, not a probability; nothing converted
    /// from turbidity is high (VisibilityModel).
    public let level: String
    public let reasons: [String]
}

public struct ProvenanceItem: Codable, Equatable {
    public let input: String
    public let value: String
    public let source: String
}

public struct ArmClarityState: Codable, Equatable {
    public let lakeId: String
    public let armId: String
    public let armName: String
    public let timestamp: Date
    public let satelliteSceneDate: String?
    public let satelliteAnchorFNU: Double?
    public let satelliteAnchorVisibility: VisibilityEstimate?
    public let satelliteAnchorStrength: AnchorStrength
    public let satelliteAnchorReason: String
    public let satelliteObservedPct: Double?
    public let satelliteFilledPct: Double?
    public let medianFillDistanceM: Double?
    public let rain1hIn: Double?
    public let rain6hIn: Double?
    public let rain12hIn: Double?
    public let rain24hIn: Double?
    public let rain48hIn: Double?
    public let rain72hIn: Double?
    public let currentStormTotalIn: Double?
    public let antecedent7dIn: Double?
    public let dischargeCurrentCfs: Double?
    public let dischargeAtSatellitePassCfs: Double?
    public let dischargeTrend: String
    public let dischargeProvenance: FlowProvenance
    public let catchmentCompleteness: CatchmentCompleteness
    public let divergence: Divergence
    public let runoffAnomaly: RunoffAnomaly
    public let runoff: RunoffState
    public let satelliteAuthority: SatelliteAuthority
    public let currentVisibility: CurrentVisibility
    public let confidence: StateConfidence
    public let limitations: [String]
    public let provenance: [ProvenanceItem]
}

public struct MainStemClarityState: Codable, Equatable {
    public let lakeId: String
    public let river: String
    public let timestamp: Date
    public let satelliteSceneDate: String?
    public let satelliteAnchorFNU: Double?
    public let satelliteAnchorVisibility: VisibilityEstimate?
    public let satelliteAnchorStrength: AnchorStrength
    public let satelliteAnchorReason: String
    public let satelliteObservedPct: Double?
    /// Rain on the reservoir's own surface (the main stem has no creek of its own).
    public let directRainSincePassIn: Double?
    public let directRain72hIn: Double?
    public let inflowDam: String
    public let inflowNow24hMeanCfs: Double?
    public let inflowAtPass24hMeanCfs: Double?
    public let inflowTrend: String
    public let outflowDam: String
    public let outflowNow24hMeanCfs: Double?
    public let outflowTrend: String
    /// "measuredTVA" | "unavailable"
    public let releaseProvenance: String
    /// Stated so no reader mistakes a release for a current.
    public let currentVelocity: String
    public let runoff: RunoffState
    public let satelliteAuthority: SatelliteAuthority
    public let currentVisibility: CurrentVisibility
    public let confidence: StateConfidence
    public let limitations: [String]
    public let provenance: [ProvenanceItem]
}

// MARK: - The engine (pure)

public struct ArmClarityInputs: Equatable {
    public let lakeId: String
    public let armId: String
    public let armName: String
    public let anchor: SatelliteAnchor?
    public let rain: RainRecord
    public let flow: FlowRecord
    /// The estimate Sector gives without the fusion (the engine's existing
    /// clarity path), used — unadjusted — when the scene cannot carry a magnitude.
    public let baseline: BaselineVisibility?
    /// Arms nested in another arm's embayment: named so the limitation can say
    /// that water arriving from it is not modelled (no transport in Stage 2).
    public let parentArmName: String?

    public init(lakeId: String, armId: String, armName: String, anchor: SatelliteAnchor?, rain: RainRecord,
                flow: FlowRecord, baseline: BaselineVisibility?, parentArmName: String? = nil) {
        self.lakeId = lakeId; self.armId = armId; self.armName = armName; self.anchor = anchor
        self.rain = rain; self.flow = flow; self.baseline = baseline
        self.parentArmName = parentArmName
    }
}

public struct MainStemClarityInputs: Equatable {
    public let lakeId: String
    public let river: String
    public let anchor: SatelliteAnchor?
    /// The reservoir surface.
    public let directRain: RainRecord
    public let inflow: ReleaseSeries?
    public let outflow: ReleaseSeries?
    public let inflowDamName: String
    public let outflowDamName: String
    public let baseline: BaselineVisibility?

    public init(lakeId: String, river: String, anchor: SatelliteAnchor?, directRain: RainRecord,
                inflow: ReleaseSeries?, outflow: ReleaseSeries?, inflowDamName: String, outflowDamName: String,
                baseline: BaselineVisibility?) {
        self.lakeId = lakeId; self.river = river; self.anchor = anchor; self.directRain = directRain
        self.inflow = inflow; self.outflow = outflow; self.inflowDamName = inflowDamName
        self.outflowDamName = outflowDamName; self.baseline = baseline
    }
}

public enum ClarityStateEngine {

    /// The runoff levels' thresholds. PROVISIONAL RULES, not fits: the
    /// pass-pair analysis (hand-off §5) found no rain amount, and no timing,
    /// at which arm median turbidity reliably changes — the response is real
    /// on some arms after some storms, but 2025 and 2026 disagree on when and
    /// how much. So these mark HYDROLOGIC change — how different the drainage
    /// is from the scene's — and nothing about feet of visibility.
    public enum Rules {
        /// Catchment-mean inches since the pass: minor, moderate, major.
        public static let rainIn: (minor: Double, moderate: Double, major: Double) = (0.10, 0.50, 1.00)
        /// Peak flow since the pass over flow at the pass.
        public static let flowRatio: (minor: Double, moderate: Double, major: Double) = (1.5, 2.0, 5.0)
        /// A modeled rise alone indicates at most this.
        public static let modeledCap: RunoffClass = .moderateRunoff
        /// Recovering: the storm is over (< this in 24 h) and flow is back under this share of its peak.
        public static let dryLast24hIn = 0.05
        public static let recededShareOfPeak = 0.5
        /// Without any flow, a storm this long over counts as receding.
        public static let recededHoursWithoutFlow = 72.0
        /// The scene itself caught a storm: this much rain in the 72 h before it.
        public static let plumeSnapshotRainIn = 0.50
        /// Dam release, 24 h mean now over 24 h mean at the pass.
        public static let releaseRatio: (minor: Double, moderate: Double, major: Double) = (1.5, 2.0, 3.0)
        public static let gaugeNowMaxAgeHours = 6.0
        public static let atPassToleranceHours = 3.0
        public static let modeledAtPassToleranceHours = 13.0
    }

    // MARK: Divergence

    static func divergence(anchor: SatelliteAnchor?, rain: RainRecord, flow: FlowRecord, now: Date) -> Divergence {
        let pass = anchor?.sceneTime
        let through = rain.validThrough(now)
        let sincePass: RainRecord.Total? = {
            guard let pass, let through else { return nil }
            return through <= pass ? RainRecord.Total(inches: 0, coverage: 1) : rain.total(from: pass, to: through)
        }()
        let storm = rain.currentStorm(at: now)
        let stormSince: Double? = {
            guard let storm, let pass else { return nil }
            guard let s = storm.start else { return 0 }
            guard let through, through > max(s, pass) else { return 0 }
            return rain.total(from: max(s, pass), to: through)?.inches
        }()
        let last24 = rain.window(hours: 24, now: now)
        let last72 = rain.window(hours: 72, now: now)
        let ante = pass.flatMap { rain.total(from: $0.addingTimeInterval(-7 * 86_400), to: $0)?.inches }
        let before72 = pass.flatMap { rain.total(from: $0.addingTimeInterval(-3 * 86_400), to: $0)?.inches }

        // Pick ONE series: the arm's own gauge if it reads now, else its model.
        var series: FlowSeries?
        var note: String?
        if let m = flow.measured, let last = m.latest(atOrBefore: now),
           now.timeIntervalSince(last.validTime) <= Rules.gaugeNowMaxAgeHours * 3600 {
            series = m
        } else if let m = flow.modeled, m.latest(atOrBefore: now) != nil {
            series = m
            if flow.measured != nil { note = "the gauge has no reading in the last \(Int(Rules.gaugeNowMaxAgeHours)) h; the model stands in" }
        }
        let nowPt = series?.latest(atOrBefore: now)
        var atPass: FlowPoint?, peak: FlowPoint?
        if let s = series, let pass {
            let tol = s.provenance == .measuredUSGS ? Rules.atPassToleranceHours : Rules.modeledAtPassToleranceHours
            atPass = s.value(at: pass, toleranceHours: tol)
            peak = s.peak(from: pass, to: now)
            if atPass == nil {
                note = (note.map { $0 + "; " } ?? "") + "no \(s.provenance.rawValue) value within \(Int(tol)) h of the pass"
            }
        }
        let trend: String = {
            guard let s = series, let n = nowPt,
                  let b = s.value(at: n.validTime.addingTimeInterval(-12 * 3600), toleranceHours: 3) else { return "unknown" }
            let d = n.cfs - b.cfs
            if abs(d) <= max(0.1 * b.cfs, 0.5) { return "steady" }
            return d > 0 ? "rising" : "falling"
        }()
        let ratio = (atPass != nil && nowPt != nil) ? nowPt!.cfs / max(atPass!.cfs, 0.1) : nil
        let peakRatio = (atPass != nil && peak != nil) ? max(peak!.cfs, nowPt?.cfs ?? 0) / max(atPass!.cfs, 0.1) : nil
        return Divergence(passTime: pass,
                          hoursSincePass: pass.map { now.timeIntervalSince($0) / 3600 },
                          rainValidThrough: through,
                          rainSincePassIn: sincePass?.inches, rainSincePassCoverage: sincePass?.coverage,
                          currentStormIn: storm?.inches, currentStormSincePassIn: stormSince,
                          rainLast24hIn: last24, rainLast72hIn: last72,
                          antecedent7dBeforePassIn: ante, rain72hBeforePassIn: before72,
                          dischargeProvenance: series?.provenance ?? .unavailable,
                          dischargeSource: series?.source,
                          dischargeNowCfs: nowPt?.cfs, dischargeNowAt: nowPt?.validTime,
                          dischargeAtPassCfs: atPass?.cfs, dischargePeakSincePassCfs: peak?.cfs,
                          dischargeRatioToPass: ratio, dischargePeakRatioToPass: peakRatio,
                          dischargeTrend: trend, dischargeNote: note)
    }

    // MARK: Runoff

    static func level(_ x: Double, _ t: (minor: Double, moderate: Double, major: Double)) -> RunoffClass {
        x >= t.major ? .majorRunoff : x >= t.moderate ? .moderateRunoff : x >= t.minor ? .minorChange : .stable
    }

    static func runoff(_ d: Divergence, hasAnchor: Bool) -> RunoffState {
        var evidence: [String] = []
        var levels: [RunoffClass] = []
        if let r = d.rainSincePassIn {
            let l = level(r, Rules.rainIn)
            levels.append(l); evidence.append(String(format: "%.2f in on the drainage since the pass → %@", r, l.rawValue))
        } else if hasAnchor {
            evidence.append("rain since the pass unknown")
        }
        if let p = d.dischargePeakRatioToPass {
            var l = level(p, Rules.flowRatio)
            if d.dischargeProvenance == .modeledNWM && l > Rules.modeledCap {
                l = Rules.modeledCap
                evidence.append(String(format: "modeled (NWM) flow peak ×%.1f the pass → capped at %@ (a model rise alone)", p, l.rawValue))
            } else {
                evidence.append(String(format: "%@ flow peak ×%.1f the pass → %@",
                                       d.dischargeProvenance == .measuredUSGS ? "measured" : "modeled (NWM)", p, l.rawValue))
            }
            levels.append(l)
        }
        guard hasAnchor else {
            return RunoffState(state: .unknown, expectedDirection: "unknown", magnitude: "uncalibrated",
                               evidence: ["no satellite scene of this arm to compare against"] + evidence)
        }
        guard var state = levels.max() else {
            return RunoffState(state: .unknown, expectedDirection: "unknown", magnitude: "uncalibrated",
                               evidence: evidence + ["no rain or flow record for this arm's drainage"])
        }
        var direction = state >= .moderateRunoff ? "murkierThanPass" : "sameAsPass"
        // Receding: a real event since the pass, now over and falling away.
        if state >= .moderateRunoff, let l24 = d.rainLast24hIn, l24 < Rules.dryLast24hIn {
            if let now = d.dischargeNowCfs, let peak = d.dischargePeakSincePassCfs, peak > 0,
               now <= Rules.recededShareOfPeak * peak, d.dischargeTrend != "rising" {
                state = .recovering
                evidence.append(String(format: "storm over; flow back to %.0f%% of its peak and not rising → recovering", 100 * now / peak))
            } else if d.dischargeNowCfs == nil, let storm = d.currentStormIn, storm == 0,
                      let l72 = d.rainLast72hIn, l72 < Rules.dryLast24hIn {
                state = .recovering
                evidence.append("no flow record; dry for 72 h → recovering")
            }
        }
        // The scene itself caught a storm, and the drainage has since calmed.
        if state <= .minorChange, let b = d.rain72hBeforePassIn, b >= Rules.plumeSnapshotRainIn,
           let ratio = d.dischargeRatioToPass, ratio < 1 / Rules.flowRatio.minor {
            state = .recovering
            direction = "clearerThanPass"
            evidence.append(String(format: "%.2f in fell in the 72 h before the scene and flow has since fallen to ×%.2f → the scene caught runoff that is now receding", b, ratio))
        }
        return RunoffState(state: state, expectedDirection: direction, magnitude: "uncalibrated", evidence: evidence)
    }

    // MARK: Authority

    static func authority(strength: AnchorStrength, runoff: RunoffState) -> SatelliteAuthority {
        guard strength > .none else { return SatelliteAuthority(level: .none, reason: "no scene of this arm") }
        let cap: AuthorityLevel
        let why: String
        switch runoff.state {
        case .stable: cap = .high; why = "the drainage is as it was when the scene was taken"
        case .minorChange: cap = .moderate; why = "some rain or flow change since the scene"
        case .moderateRunoff: cap = .low; why = "runoff since the scene"
        case .majorRunoff: cap = .none; why = "major runoff since the scene: it no longer describes this water"
        case .recovering: cap = .low; why = runoff.expectedDirection == "clearerThanPass"
            ? "the scene caught runoff that has since receded" : "runoff since the scene, now receding"
        case .unknown: cap = .moderate; why = "no record to show the drainage has stayed the same"
        }
        let fromAnchor: AuthorityLevel = [.strong: .high, .moderate: .moderate, .weak: .low][strength] ?? .none
        if fromAnchor < cap {
            return SatelliteAuthority(level: fromAnchor, reason: "the scene read too little of the arm (\(strength.rawValue) anchor); \(why)")
        }
        return SatelliteAuthority(level: cap, reason: why)
    }

    // MARK: Visibility

    static func visibility(anchor: SatelliteAnchor?, authority: SatelliteAuthority, runoff: RunoffState,
                           baseline: BaselineVisibility?) -> CurrentVisibility {
        let atPass = anchor?.visibility()
        if authority.level >= .moderate, let v = atPass {
            return CurrentVisibility(basis: "satelliteAnchor", centralFt: v.centralFt, lowFt: v.lowFt, highFt: v.highFt,
                                     magnitudeSupported: true, warning: nil, baselineSource: nil,
                                     atPass: v, model: VisibilityModel.modelId)
        }
        let warning: String? = {
            switch runoff.expectedDirection {
            case "murkierThanPass":
                return runoff.state == .recovering
                    ? "Runoff since the satellite scene, now receding: the water may still be murkier than the scene showed. Sector has no calibrated size or timing for it."
                    : "Runoff since the satellite scene: the water may be murkier than it showed. Historically this appeared at the next clear pass in a minority of cases; Sector has no calibrated size for it."
            case "clearerThanPass":
                return "The satellite scene caught runoff that has since receded: the water may be clearer than it showed. Sector has no calibrated size for it."
            default:
                return atPass == nil ? "No satellite scene of this water." : "The satellite scene reads too little of this arm to stand alone."
            }
        }()
        if let b = baseline {
            return CurrentVisibility(basis: "baseline", centralFt: b.centralFt, lowFt: b.lowFt, highFt: b.highFt,
                                     magnitudeSupported: false, warning: warning, baselineSource: "\(b.model): \(b.source)",
                                     atPass: atPass, model: VisibilityModel.modelId)
        }
        return CurrentVisibility(basis: "none", centralFt: nil, lowFt: nil, highFt: nil, magnitudeSupported: false,
                                 warning: warning, baselineSource: nil, atPass: atPass, model: VisibilityModel.modelId)
    }

    // MARK: Confidence

    /// An ordinal ladder: each weakness costs a step.
    enum FlowKind { case measured, modeled, none }

    static func confidence(strength: AnchorStrength, runoff: RunoffState, completeness: CatchmentCompleteness,
                           rainKnown: Bool, flow: FlowKind) -> StateConfidence {
        var steps = 0
        var why: [String] = []
        switch strength {
        case .strong: break
        case .moderate: steps += 1; why.append("moderate satellite anchor")
        case .weak: steps += 2; why.append("weak satellite anchor")
        case .none: steps += 3; why.append("no satellite anchor")
        }
        switch runoff.state {
        case .stable: break
        case .minorChange, .unknown: steps += 1; why.append("runoff \(runoff.state.rawValue)")
        case .moderateRunoff, .recovering: steps += 2; why.append("runoff \(runoff.state.rawValue): direction only")
        case .majorRunoff: steps += 3; why.append("major runoff: direction only")
        }
        switch completeness {
        case .complete: break
        case .partial: steps += 1; why.append("partial catchment: rain around the embayment itself is missing")
        case .unavailable: steps += 2; why.append("no catchment: rain unknown")
        }
        if completeness != .unavailable && !rainKnown { steps += 1; why.append("rain record incomplete") }
        switch flow {
        case .measured: break
        case .modeled: why.append("flow is modeled (NWM), not measured")
        case .none: steps += 1; why.append("no flow record")
        }
        let level = steps <= 1 ? "medium" : steps <= 3 ? "low" : "veryLow"
        return StateConfidence(level: level, reasons: why.isEmpty ? ["strong scene, stable drainage, complete catchment, measured flow"] : why)
    }

    // MARK: Arm state

    public static func armState(_ x: ArmClarityInputs, now: Date) -> ArmClarityState {
        let d = divergence(anchor: x.anchor, rain: x.rain, flow: x.flow, now: now)
        let (strength, strengthWhy) = x.anchor?.strength ?? (.none, "no scene of this arm")
        let r = runoff(d, hasAnchor: x.anchor != nil && strength > .none)
        let a = authority(strength: strength, runoff: r)
        let v = visibility(anchor: x.anchor, authority: a, runoff: r, baseline: x.baseline)
        let completeness = x.rain.completeness
        let c = confidence(strength: strength, runoff: r, completeness: completeness,
                           rainKnown: d.rainSincePassIn != nil || x.anchor == nil,
                           flow: [.measuredUSGS: .measured, .modeledNWM: .modeled][d.dischargeProvenance] ?? .none)
        func win(_ h: Double) -> Double? { x.rain.window(hours: h, now: now) }
        var lim: [String] = []
        switch completeness {
        case .partial: lim.append("Rain is over the drainage above the embayment's head only; the land around the embayment is missing.")
        case .unavailable: lim.append("No drainage area was resolved for this creek: rain is unknown, not zero.")
        case .complete: break
        }
        switch d.dischargeProvenance {
        case .modeledNWM: lim.append("Flow is the National Water Model's analysis, not a measurement.")
        case .unavailable: lim.append("No gauge and no model reach for this creek: flow unknown.")
        case .measuredUSGS: break
        }
        if let n = d.dischargeNote { lim.append("Flow: \(n).") }
        if let a = x.anchor, strength < .strong {
            lim.append(String(format: "The scene read %.0f%% of this arm; %.0f%% is filled", a.observedPct, a.filledPct)
                       + (a.medianFillDistanceM.map { String(format: " (median %.0f m from a reading).", $0) } ?? "."))
        }
        if let p = x.parentArmName {
            lim.append("Water arriving from \(p) through this arm's mouth is not modelled (no transport in Stage 2).")
        }
        lim.append("One state for the whole arm: a plume at the creek's head is not resolved from the rest of the arm.")
        lim.append("The runoff state is a hydrologic statement; its direction is not validated as a clarity change and it has no calibrated size.")
        let fmt: (Double?) -> String = { $0.map { String(format: "%.2f", $0) } ?? "unknown" }
        var prov: [ProvenanceItem] = []
        if let a = x.anchor {
            prov.append(.init(input: "satellite scene", value: "\(a.sceneDate) \(a.platform ?? "")", source: a.source))
        }
        prov.append(.init(input: "rain since pass (in)", value: fmt(d.rainSincePassIn),
                          source: "\(x.rain.source) over \(x.rain.basis)" + (x.rain.drainageKm2.map { String(format: ", %.0f km²", $0) } ?? "")))
        prov.append(.init(input: "discharge now (cfs)", value: fmt(d.dischargeNowCfs),
                          source: "\(d.dischargeProvenance.rawValue)" + (d.dischargeSource.map { " \($0)" } ?? "")))
        prov.append(.init(input: "discharge at pass (cfs)", value: fmt(d.dischargeAtPassCfs),
                          source: d.dischargeAtPassCfs == nil ? "not reconstructable" : d.dischargeProvenance.rawValue))
        if let b = x.baseline, v.basis == "baseline" {
            prov.append(.init(input: "baseline visibility (ft)", value: String(format: "%.1f", b.centralFt), source: "\(b.model): \(b.source)"))
        }
        return ArmClarityState(
            lakeId: x.lakeId, armId: x.armId, armName: x.armName, timestamp: now,
            satelliteSceneDate: x.anchor?.sceneDate,
            satelliteAnchorFNU: x.anchor.flatMap { ($0.observedCells >= 10 ? $0.observedFNU : $0.allFNU)?.p50 },
            satelliteAnchorVisibility: x.anchor?.visibility(),
            satelliteAnchorStrength: strength, satelliteAnchorReason: strengthWhy,
            satelliteObservedPct: x.anchor?.observedPct, satelliteFilledPct: x.anchor?.filledPct,
            medianFillDistanceM: x.anchor?.medianFillDistanceM,
            rain1hIn: win(1), rain6hIn: win(6), rain12hIn: win(12), rain24hIn: win(24), rain48hIn: win(48), rain72hIn: win(72),
            currentStormTotalIn: d.currentStormIn, antecedent7dIn: d.antecedent7dBeforePassIn,
            dischargeCurrentCfs: d.dischargeNowCfs, dischargeAtSatellitePassCfs: d.dischargeAtPassCfs,
            dischargeTrend: d.dischargeTrend, dischargeProvenance: d.dischargeProvenance,
            catchmentCompleteness: completeness, divergence: d,
            runoffAnomaly: RunoffAnomaly(rainSincePassIn: d.rainSincePassIn, dischargeRatioToPass: d.dischargeRatioToPass,
                                         dischargePeakRatioToPass: d.dischargePeakRatioToPass, provenance: d.dischargeProvenance),
            runoff: r, satelliteAuthority: a, currentVisibility: v, confidence: c, limitations: lim, provenance: prov)
    }

    // MARK: Main stem

    public static func mainStemState(_ x: MainStemClarityInputs, now: Date) -> MainStemClarityState {
        let pass = x.anchor?.sceneTime
        let (strength, strengthWhy) = x.anchor?.strength ?? (.none, "no scene of the main stem")
        let through = x.directRain.validThrough(now)
        let direct: Double? = {
            guard let pass, let through else { return nil }
            return through <= pass ? 0 : x.directRain.total(from: pass, to: through)?.inches
        }()
        let direct72 = x.directRain.window(hours: 72, now: now)
        let inNow = x.inflow?.mean24h(endingAt: now)
        let inPass = pass.flatMap { p in x.inflow?.mean24h(endingAt: p.addingTimeInterval(12 * 3600)) }
        let outNow = x.outflow?.mean24h(endingAt: now)
        func trend(_ s: ReleaseSeries?) -> String {
            guard let s, let a = s.mean24h(endingAt: now), let b = s.mean24h(endingAt: now.addingTimeInterval(-86_400)) else { return "unknown" }
            let d = a - b
            if abs(d) <= 0.1 * b { return "steady" }
            return d > 0 ? "rising" : "falling"
        }
        var evidence: [String] = []
        var levels: [RunoffClass] = []
        if let r = direct {
            let l = level(r, Rules.rainIn); levels.append(l)
            evidence.append(String(format: "%.2f in on the reservoir surface since the pass → %@", r, l.rawValue))
        }
        if let a = inNow, let b = inPass, b > 0 {
            let l = level(a / b, Rules.releaseRatio); levels.append(l)
            evidence.append(String(format: "%@ release (24 h mean) ×%.2f the pass → %@", x.inflowDamName, a / b, l.rawValue))
        } else {
            evidence.append("\(x.inflowDamName) release at the pass not in the record")
        }
        let r: RunoffState = {
            guard x.anchor != nil, strength > .none else {
                return RunoffState(state: .unknown, expectedDirection: "unknown", magnitude: "uncalibrated",
                                   evidence: ["no satellite scene of the main stem"] + evidence)
            }
            guard let s = levels.max() else {
                return RunoffState(state: .unknown, expectedDirection: "unknown", magnitude: "uncalibrated", evidence: evidence)
            }
            return RunoffState(state: s, expectedDirection: s >= .moderateRunoff ? "murkierThanPass" : "sameAsPass",
                               magnitude: "uncalibrated", evidence: evidence)
        }()
        let a = authority(strength: strength, runoff: r)
        let v = visibility(anchor: x.anchor, authority: a, runoff: r, baseline: x.baseline)
        let c = confidence(strength: strength, runoff: r, completeness: x.directRain.completeness,
                           rainKnown: direct != nil || x.anchor == nil,
                           flow: inNow != nil ? .measured : .none)
        let lim = [
            "No current: a dam's release is not a velocity, and Sector measures no velocity in the reservoir.",
            "No plume travel time: when water released at \(x.inflowDamName) reaches any point down the lake is not estimated.",
            "Rain over the Tennessee's basin above \(x.inflowDamName) is not included; its effect arrives only through the release.",
            "Direct rain is over the reservoir surface only.",
        ] + (inPass == nil ? ["\(x.inflowDamName)'s release at the pass is not in the record (TVA publishes 48 h)."] : [])
        let fmt: (Double?) -> String = { $0.map { String(format: "%.0f", $0) } ?? "unknown" }
        var prov: [ProvenanceItem] = []
        if let an = x.anchor { prov.append(.init(input: "satellite scene", value: an.sceneDate, source: an.source)) }
        prov.append(.init(input: "\(x.inflowDamName) release now (cfs, 24 h mean)", value: fmt(inNow), source: "measuredTVA \(x.inflow?.tva ?? "")"))
        prov.append(.init(input: "\(x.inflowDamName) release at pass (cfs, 24 h mean)", value: fmt(inPass),
                          source: inPass == nil ? "not in the record" : "measuredTVA"))
        prov.append(.init(input: "direct rain since pass (in)", value: direct.map { String(format: "%.2f", $0) } ?? "unknown",
                          source: x.directRain.source))
        return MainStemClarityState(
            lakeId: x.lakeId, river: x.river, timestamp: now, satelliteSceneDate: x.anchor?.sceneDate,
            satelliteAnchorFNU: x.anchor.flatMap { ($0.observedCells >= 10 ? $0.observedFNU : $0.allFNU)?.p50 },
            satelliteAnchorVisibility: x.anchor?.visibility(),
            satelliteAnchorStrength: strength, satelliteAnchorReason: strengthWhy,
            satelliteObservedPct: x.anchor?.observedPct,
            directRainSincePassIn: direct, directRain72hIn: direct72,
            inflowDam: x.inflowDamName, inflowNow24hMeanCfs: inNow, inflowAtPass24hMeanCfs: inPass,
            inflowTrend: trend(x.inflow), outflowDam: x.outflowDamName, outflowNow24hMeanCfs: outNow,
            outflowTrend: trend(x.outflow), releaseProvenance: inNow != nil ? "measuredTVA" : "unavailable",
            currentVelocity: "unknown: not measured anywhere in the reservoir",
            runoff: r, satelliteAuthority: a, currentVisibility: v, confidence: c, limitations: lim, provenance: prov)
    }
}
