//
//  EnvironmentProvenance.swift
//  SectorEngine
//
//  Where every environmental number came from.
//
//  `ConditionsInput` carries bare `Double`s. That is fine for scoring — the
//  aggregator only needs values — but it means nothing downstream can tell a
//  five-minute-old gage reading from a modelled estimate from a value that was
//  never available at all. `waterTempEstimated: Bool` is the whole of the
//  existing provenance system.
//
//  The spatial engine cannot work that way: it has to know that weather is one
//  lake-wide grid cell while a tributary gage describes one point, and it has to
//  degrade confidence for a stale vegetation survey differently from a stale
//  discharge reading.
//
//  So this is emitted ALONGSIDE `ConditionsInput`, by the same builder pass, from
//  decisions the builder already makes and currently throws away. Nothing in the
//  scoring path reads it, which is what makes adding it safe: it cannot move a
//  score.
//

import Foundation

public struct EnvironmentProvenance: Equatable, Sendable {

    /// How a value came to exist. The distinction the scoring engine needs is
    /// not "is it good" but "what KIND of claim is this".
    public enum Origin: Equatable, Sendable {
        /// An instrument read the water. `siteCode` identifies which.
        case measured(siteCode: String?)
        /// A model produced it. The string names the model, so a later
        /// calibration pass can tell which one to blame.
        case modelled(String)
        /// Computed from other values in this snapshot (a trend, a window max).
        case derived(String)
        /// A person reported it.
        case userReported
        /// Nothing answered. The reason matters — "no gage exists here" and
        /// "the gage is 40 miles away" degrade confidence differently.
        case unavailable(Reason)

        public enum Reason: Equatable, Sendable {
            case noSourceExists
            case fetchFailed
            case tooOld(hours: Double)
            case tooFar(miles: Double)
            case notApplicableHere
        }
    }

    /// What geography the value actually describes. Without this a caller cannot
    /// tell that a watershed rainfall total covers a ~50 mile box while a stage
    /// reading covers one gage.
    public enum Coverage: Equatable, Sendable {
        case point(latitude: Double, longitude: Double, radiusMiles: Double?)
        /// True of the whole waterbody — which for weather at 200 m spacing is a
        /// measured fact, not a convenient assumption.
        case lakeWide
        case watershed(approxMiles: Double)
        case grid(approxKm: Double)
        case unknown
    }

    public struct Entry: Equatable, Sendable {
        /// The `ConditionsInput` field this describes, e.g. "waterTempF".
        public let variable: String
        public let origin: Origin
        /// When the observation was taken. nil for a model with no single time.
        public let observedAt: Date?
        /// When this process obtained it.
        public let ingestedAt: Date
        public let coverage: Coverage
        /// 0…1. Not a confidence score — an input TO one.
        public let quality: Double

        public init(variable: String, origin: Origin, observedAt: Date? = nil,
                    ingestedAt: Date, coverage: Coverage = .unknown, quality: Double) {
            self.variable = variable
            self.origin = origin
            self.observedAt = observedAt
            self.ingestedAt = ingestedAt
            self.coverage = coverage
            self.quality = quality
        }

        /// Age at `now`, in hours. nil when the value has no observation time.
        public func ageHours(at now: Date = Date()) -> Double? {
            observedAt.map { now.timeIntervalSince($0) / 3600 }
        }

        public var isMeasured: Bool {
            if case .measured = origin { return true }
            return false
        }

        public var isAvailable: Bool {
            if case .unavailable = origin { return false }
            return true
        }
    }

    public let entries: [String: Entry]

    public init(entries: [String: Entry] = [:]) {
        self.entries = entries
    }

    public subscript(_ variable: String) -> Entry? { entries[variable] }

    /// Variables that had no usable source — the honest answer to "what don't we
    /// know here", and the list a confidence model should be reading.
    public var unavailable: [Entry] {
        entries.values.filter { !$0.isAvailable }.sorted { $0.variable < $1.variable }
    }

    public var measuredCount: Int { entries.values.filter(\.isMeasured).count }
}
