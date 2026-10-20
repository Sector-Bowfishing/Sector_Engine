//
//  LakePredictionLedger.swift
//  Sector — Lake Brain: the PROSPECTIVE PREDICTION LEDGER (internal; never customer-facing)
//
//  Each time the Lake Brain publishes a lake state it makes testable claims. This file turns a published
//  result into one immutable JSON line per lake (`lake-prediction-ledger-v1`) and one JSONL object per run:
//
//    gs://sector-lake-brain/predictions/{yyyy}/{MM}/{dd}/{HHmmss}Z-{runId}.jsonl     (UTC of the run)
//
//  The record stores the labels, the effective thresholds and, for +1 d / +7 d / +30 d, the baseline band
//  edges for THAT day of year as the baseline grid held them at run time, so a later scorer re-scores
//  without recomputing anything (no hindsight). See docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md.
//
//  Guarantees: append-only (an object is never overwritten); a ledger failure NEVER fails or alters the
//  Brain publish (it is reported as a warning); nothing here changes lifecycle, readiness, the score
//  rubric or `/validation/lake-brain` (stays NOT_VALIDATED). The ledger existing is not validation.
//

import Foundation

// MARK: - Record

public struct LakePredictionRecord: Codable, Equatable, Sendable {
    public struct Observation: Codable, Equatable, Sendable { public var at: String; public var ft: Double }
    public struct Labels: Codable, Equatable, Sendable {
        public var levelState: String
        public var historicalState: String
        public var trendState: String
        public var floodPoolState: String
    }
    /// Observed level changes (ft) behind the trend label.
    public struct Change: Codable, Equatable, Sendable { public var h24: Double?; public var d3: Double? }
    /// Baseline band edges for the target day of year, straight from the baseline grid (3 decimals).
    public struct Band: Codable, Equatable, Sendable {
        public var p02: Double
        public var p10: Double
        public var p50: Double
        public var p90: Double
        public var p98: Double
    }
    public struct Horizon: Codable, Equatable, Sendable {
        /// Horizon in days (1, 7, 30).
        public var days: Int
        /// Lake-local target date = observation date + `days`.
        public var targetDate: String
        /// Day of year on the 365-day calendar (Feb 29 shares Feb 28).
        public var doy: Int
        /// Level band for the target day. Absent when the lake's history tier is NONE or the day has no level climatology.
        public var band: Band?
        /// Level samples behind the band (window ±7 d).
        public var bandN: Int?
        /// Seasonal p95 of |Δ24h| on the target day (absent without a rate climatology).
        public var rateP95: Double?
        public var rateN: Int?
    }

    public var ledgerVersion: String
    public var runId: String
    public var generatedAt: String
    public var lakeId: String
    public var rulesVersion: String
    public var brainVersion: String
    public var baselineMethod: String
    /// Absent when no baseline existed at run time.
    public var baselineVersion: String?
    public var historicalTier: String
    public var baselineStatus: String
    public var bindingVersion: String
    public var bindingStatus: String
    public var sourceId: String
    /// tva | cwms | usgs (the provider of `sourceId`).
    public var provider: String
    /// OBSERVED | PROXY
    public var kind: String
    /// fullPool (regulated) | naturalSurface, from the directory; absent when the directory has none.
    public var poolBasis: String?
    public var timeZone: String
    /// Lake-local date of the observation (the base date the horizons count from).
    public var baseDate: String
    public var observation: Observation
    public var labels: Labels
    public var change: Change?
    /// The effective RAPID threshold stored with the label (ft per 24 h); absent for a PROXY.
    public var rapidThresholdFt: Double?
    /// The STABLE floor applied to the 72 h mean rate (ft per day).
    public var stableFloorFt: Double
    public var flags: [String]
    public var horizons: [Horizon]
}

// MARK: - Ledger

public enum LakePredictionLedger {

    public static let version = "lake-prediction-ledger-v1"
    public static let horizonDays = [1, 7, 30]

    public struct Outcome: Equatable, Sendable {
        public var path: String?
        public var records: Int
        public var warning: String?
    }

    // MARK: calendar

    /// `day` + `n` calendar days (Gregorian, date arithmetic on the day string; handles month/year wrap and leap years).
    static func addDays(_ day: String, _ n: Int) -> String? {
        let p = day.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        let utc = TimeZone(identifier: "UTC")!
        var cal = Calendar(identifier: .gregorian); cal.timeZone = utc
        let start = LakeLevelCalendar.date(year: p[0], month: p[1], day: p[2], timeZone: utc)
        guard let d = cal.date(byAdding: .day, value: n, to: start) else { return nil }
        return LakeLevelCalendar.dayString(d, timeZone: utc)
    }

    // MARK: path

    /// Keep a run id safe for an object name: [A-Za-z0-9_-], at most 40 characters, never empty.
    public static func sanitizeRunId(_ s: String) -> String {
        let ok = s.unicodeScalars.filter { ($0.value >= 48 && $0.value <= 57) || ($0.value >= 65 && $0.value <= 90)
            || ($0.value >= 97 && $0.value <= 122) || $0 == "-" || $0 == "_" }
        let t = String(String.UnicodeScalarView(ok).prefix(40))
        return t.isEmpty ? "run" : t
    }

    /// `predictions/{yyyy}/{MM}/{dd}/{HHmmss}Z-{runId}.jsonl`, UTC.
    public static func path(generatedAt: Date, runId: String) -> String {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
        let c = cal.dateComponents([.year, .month, .day, .hour, .minute, .second], from: generatedAt)
        return String(format: "predictions/%04d/%02d/%02d/%02d%02d%02dZ-%@.jsonl",
                      c.year!, c.month!, c.day!, c.hour!, c.minute!, c.second!, sanitizeRunId(runId))
    }

    // MARK: build

    static func qualifies(_ r: LakeBrainLakeResult) -> Bool {
        // Recomputed this run (baseline is only built on the publish path), reviewed binding, with an observation.
        guard r.baseline != nil, let s = r.state, s.kind != .unavailable, s.currentElevationFt != nil, s.observationTime != nil else { return false }
        return r.profile.sourceCapability.bindingStatus == .reviewed
    }

    /// One record per qualifying lake result, or nil (skipped lake, unavailable state, unreviewed binding).
    static func record(for r: LakeBrainLakeResult, binding: LakeSourceBinding?, regulated: Bool?, poolBasis: String?,
                       runId: String, generatedAt: Date) -> LakePredictionRecord? {
        guard qualifies(r), let s = r.state, let ft = s.currentElevationFt, let obsISO = s.observationTime,
              let obsAt = BrainPlatform.parseTime(obsISO) else { return nil }
        let tzId = binding?.timeZone ?? "UTC"
        let tz = TimeZone(identifier: tzId) ?? TimeZone(identifier: "UTC")!
        let base = LakeLevelCalendar.dayString(obsAt, timeZone: tz)
        let sourceId = s.provenance.sources?.first?.sourceId ?? ""
        let isObserved = s.kind == .observed
        let tier = s.historicalTier ?? LakeHistoricalTier.none
        let baseline = r.baseline

        var horizons: [LakePredictionRecord.Horizon] = []
        for h in horizonDays {
            guard let target = addDays(base, h), let doy = LakeLevelCalendar.doy365(target) else { continue }
            var band: LakePredictionRecord.Band?
            var bandN: Int?
            var rateP95: Double?
            var rateN: Int?
            if isObserved, let b = baseline, let day = b.day(doy) {
                if tier != .none, let q = day.levelQ,
                   let p02 = LakeBaselineBuilder.at(2, q), let p10 = LakeBaselineBuilder.at(10, q), let p50 = LakeBaselineBuilder.at(50, q),
                   let p90 = LakeBaselineBuilder.at(90, q), let p98 = LakeBaselineBuilder.at(98, q) {
                    band = .init(p02: p02, p10: p10, p50: p50, p90: p90, p98: p98)
                    bandN = day.n
                }
                if let q = day.rateQ, let p95 = LakeBaselineBuilder.at(95, q) { rateP95 = p95; rateN = day.rateN }
            }
            horizons.append(.init(days: h, targetDate: target, doy: doy, band: band, bandN: bandN, rateP95: rateP95, rateN: rateN))
        }

        let floor = (regulated ?? false) ? LakeLevelClassifier.stableFloorRegulatedFt : LakeLevelClassifier.stableFloorNaturalFt
        let change = s.change.map { LakePredictionRecord.Change(h24: $0.h24, d3: $0.d3) }
        return LakePredictionRecord(
            ledgerVersion: version, runId: sanitizeRunId(runId), generatedAt: BrainPlatform.iso(generatedAt), lakeId: r.lakeId,
            rulesVersion: s.provenance.modelVersion ?? LakeBrainSpec.modelVersion, brainVersion: s.provenance.brainVersion ?? LakeBrainSpec.brainVersion,
            baselineMethod: baseline?.method ?? LakeBrainSpec.baselineMethod, baselineVersion: baseline?.baselineVersion,
            historicalTier: tier.rawValue, baselineStatus: s.baselineStatus.rawValue,
            bindingVersion: r.profile.sourceCapability.bindingVersion, bindingStatus: r.profile.sourceCapability.bindingStatus.rawValue,
            sourceId: sourceId, provider: String(sourceId.split(separator: ":").first ?? ""), kind: s.kind.rawValue,
            poolBasis: poolBasis, timeZone: tz.identifier, baseDate: base,
            observation: .init(at: obsISO, ft: ft),
            labels: .init(levelState: s.levelState.rawValue, historicalState: s.historicalState.rawValue,
                          trendState: s.trendState.rawValue, floodPoolState: s.floodPoolState.rawValue),
            change: change, rapidThresholdFt: s.rapidChangeThresholdFt, stableFloorFt: floor,
            flags: s.provenance.qualityFlags ?? [], horizons: horizons)
    }

    /// JSON Lines, UTF-8: keys sorted, one record per line, newline-terminated, records in the given order.
    public static func encode(_ records: [LakePredictionRecord]) throws -> Data {
        var out = Data()
        for r in records {
            out.append(try BrainJSON.encode(r))
            out.append(0x0A)
        }
        return out
    }

    // MARK: write

    /// Builds the run's records and appends ONE object. Never throws: every failure becomes `warning`.
    /// A pure skip run (nothing recomputed and published) writes nothing and has no warning.
    static func append(results: [LakeBrainLakeResult], regulated: [String: (Bool?, String?)], archive: LakeBrainArchive,
                       runId: String, now: Date) async -> Outcome {
        let records = results
            .sorted { $0.lakeId < $1.lakeId }
            .compactMap { record(for: $0, binding: LakeSourceBindings.binding(for: $0.lakeId),
                                 regulated: regulated[$0.lakeId]?.0, poolBasis: regulated[$0.lakeId]?.1,
                                 runId: runId, generatedAt: now) }
        guard !records.isEmpty else { return Outcome(path: nil, records: 0, warning: nil) }
        let path = path(generatedAt: now, runId: runId)
        do {
            // Immutable: an existing object is never replaced.
            if try await archive.read(path) != nil {
                return Outcome(path: nil, records: 0, warning: "ledger: \(path) already exists; not overwritten")
            }
            try await archive.write(path, try encode(records), contentType: "application/x-ndjson")
            return Outcome(path: path, records: records.count, warning: nil)
        } catch {
            return Outcome(path: nil, records: 0, warning: "ledger: \(error)")
        }
    }
}
