//
//  LakeBindingTypes.swift
//  Sector — Lake Brain: shapes shared by the hand-written pilots, the generated bindings table and the profiles
//
//  Operator levels (plan / flood evidence), context features and the machine
//  verification record. All values here come from a source named next to them;
//  nothing is inferred.
//

import Foundation

// MARK: - Operator levels (plan / flood evidence)

/// One operator-published level, and where its value is read.
public struct OperatorLevelRef: Codable, Equatable, Sendable {
    public enum Kind: String, Codable, Sendable {
        /// A constant published by the operator, embedded (`ft`).
        case staticFt = "static"
        /// USACE Access2Water `levels[]` entry of a project (read from the district listing, so seasonal levels are today's value).
        case a2w
        /// CWMS `/levels/{id}/timeseries` (a seasonal level, e.g. Top of Conservation).
        case cwmsLevel
        /// A CWMS daily time series (e.g. `Elev-Guide Curve`).
        case cwmsSeries
    }
    public var kind: Kind
    /// Operator's own label, e.g. "Top of Normal".
    public var name: String
    /// `staticFt` only.
    public var ft: Double?
    /// A2W district (e.g. `SWL`) or CWMS office.
    public var office: String?
    /// A2W location code.
    public var location: String?
    /// A2W level tsid, CWMS level id or CWMS series id.
    public var id: String?
    /// Human-readable origin for provenance.
    public var source: String
    public var seasonal: Bool

    public init(kind: Kind, name: String, ft: Double? = nil, office: String? = nil, location: String? = nil,
                id: String? = nil, source: String, seasonal: Bool) {
        self.kind = kind; self.name = name; self.ft = ft; self.office = office; self.location = location
        self.id = id; self.source = source; self.seasonal = seasonal
    }
}

/// The operator plan of a lake as verified levels. `guide` is a seasonal guide / rule curve; a zone needs a top AND a bottom;
/// `floodPoolBottom` is the operator's bottom of flood pool (top of conservation).
public struct OperatorLevels: Codable, Equatable, Sendable {
    public var guide: OperatorLevelRef?
    public var zoneTop: OperatorLevelRef?
    public var zoneBottom: OperatorLevelRef?
    public var floodPoolBottom: OperatorLevelRef?
    /// Research project the levels were matched to, and how (`binding-review-v1` plan/flood join, STRICT columns).
    public var matchedProject: String?
    public var matchBasis: String?
    public var verifiedMatch: Bool
    public init(guide: OperatorLevelRef? = nil, zoneTop: OperatorLevelRef? = nil, zoneBottom: OperatorLevelRef? = nil,
                floodPoolBottom: OperatorLevelRef? = nil, matchedProject: String? = nil, matchBasis: String? = nil,
                verifiedMatch: Bool = true) {
        self.guide = guide; self.zoneTop = zoneTop; self.zoneBottom = zoneBottom; self.floodPoolBottom = floodPoolBottom
        self.matchedProject = matchedProject; self.matchBasis = matchBasis; self.verifiedMatch = verifiedMatch
    }
    /// A zone is only a zone with both edges.
    public var hasZone: Bool { zoneTop != nil && zoneBottom != nil }
    public var all: [OperatorLevelRef] { [guide, zoneTop, zoneBottom, floodPoolBottom].compactMap { $0 } }
}

// MARK: - Profile shapes

/// Profile `operatingPools.floodPoolBottom`.
public struct FloodPoolBottomRef: Codable, Equatable, Sendable {
    public var available: Bool
    public var name: String?
    public var source: String?
    public var seasonal: Bool?
    /// Present for constants only.
    public var valueFt: Double?
}

/// Profile `operatingPools.planEvidence`: what the operator plan rests on.
public struct PlanEvidenceRef: Codable, Equatable, Sendable {
    public var matchedProject: String?
    public var matchBasis: String?
    public var verifiedMatch: Bool
    public var criteria: String
}

/// Profile `identity.geometry`: a pointer to the shoreline registry, never the polygon.
public struct LakeGeometryRef: Codable, Equatable, Sendable {
    public var registryRef: String
    public var lakeKey: String
    public static let registryURL = "https://storage.googleapis.com/sector-lake-registry/registry/lakes.v1.json"
}

// MARK: - Context features (profile `characteristics.context`)

public struct LakeContextFeatures: Codable, Equatable, Sendable {
    public struct Chain: Codable, Equatable, Sendable {
        public var upLakes: Int?
        public var downLakes: Int?
        public var nearestDown: String?
        public var chainId: String?
        public var source: String
        public var quality: String
    }
    public struct ShorelineSlope: Codable, Equatable, Sendable {
        public var medianSlopeDeg: Double
        public var shareUnder2Deg: Double
        public var runPerVerticalFtMedian: Double
        public var source: String
        public var quality: String
    }
    public struct GrassPct: Codable, Equatable, Sendable {
        public var value: Double
        public var asOf: String?
        public var source: String
        public var quality: String
    }
    public var lakeClass: KnownValue<String>?
    public var regime: KnownValue<String>?
    public var region: KnownValue<String>?
    public var residenceTimeDays: KnownValue<Double>?
    public var shorelineSlope: ShorelineSlope?
    public var chainPosition: Chain?
    public var grassPct: GrassPct?
}

// MARK: - Machine verification record

/// What the research probe established for a generated binding. Not a review.
public struct MachineVerification: Codable, Equatable, Sendable {
    public var criteriaVersion: String
    public var researchStatus: String
    public var wave: String
    public var checksPassed: String
    public var probedAt: String
    public var lastObservationAt: String?
    public var ageHours: Double?
    public var historyCompleteYears: Int
    public var historyClass: String
}
